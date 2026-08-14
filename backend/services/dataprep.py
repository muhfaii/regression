"""Data preparation operations: missing-value handling, recode/compute,
reverse-scoring, and dataset merges.

Each function takes a DataFrame (and operation-specific args), returns a new
DataFrame plus a human-readable summary message, and raises ValueError on
invalid input so routers can turn it into a 422 response.
"""
from __future__ import annotations

import ast
import operator
import re

import numpy as np
import pandas as pd

_VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_columns_exist(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Column(s) not found: {', '.join(missing)}")


def _check_new_name(df: pd.DataFrame, name: str, overwrite: bool) -> None:
    if not _VALID_NAME.match(name):
        raise ValueError(f"'{name}' is not a valid column name.")
    if name in df.columns and not overwrite:
        raise ValueError(f"Column '{name}' already exists. Choose a different name or enable overwrite.")


# ---------------------------------------------------------------------------
# Missing data
# ---------------------------------------------------------------------------

MISSING_STRATEGIES = {"listwise", "mean", "median", "mode", "constant"}


def apply_missing_strategy(
    df: pd.DataFrame,
    columns: list[str] | None,
    strategy: str,
    constant: object | None = None,
) -> tuple[pd.DataFrame, str]:
    if strategy not in MISSING_STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy!r}")
    target_cols = columns or list(df.columns)
    _check_columns_exist(df, target_cols)

    result = df.copy()

    if strategy == "listwise":
        before = len(result)
        result = result.dropna(subset=target_cols).reset_index(drop=True)
        removed = before - len(result)
        return result, f"Removed {removed} row(s) with missing values in {', '.join(target_cols)}."

    if strategy == "constant":
        if constant is None:
            raise ValueError("A constant value is required for the 'constant' strategy.")
        result[target_cols] = result[target_cols].fillna(constant)
        return result, f"Filled missing values in {', '.join(target_cols)} with '{constant}'."

    filled: list[str] = []
    for col in target_cols:
        series = result[col]
        if strategy in ("mean", "median"):
            if not pd.api.types.is_numeric_dtype(series):
                raise ValueError(f"Column '{col}' is not numeric; '{strategy}' imputation requires numeric data.")
            value = series.mean() if strategy == "mean" else series.median()
        else:  # mode
            modes = series.mode(dropna=True)
            if modes.empty:
                continue
            value = modes.iloc[0]
        result[col] = series.fillna(value)
        filled.append(col)

    return result, f"Imputed missing values in {', '.join(filled)} using column {strategy}."


# ---------------------------------------------------------------------------
# Recode
# ---------------------------------------------------------------------------

def recode_column(
    df: pd.DataFrame,
    source_column: str,
    new_column_name: str,
    mapping: dict[str, object],
    default: object | None = None,
    overwrite: bool = False,
) -> tuple[pd.DataFrame, str]:
    _check_columns_exist(df, [source_column])
    _check_new_name(df, new_column_name, overwrite or new_column_name == source_column)
    if not mapping:
        raise ValueError("At least one mapping entry is required.")

    result = df.copy()
    source = result[source_column]

    def _map_value(v):
        if pd.isna(v):
            return v
        key = str(v)
        if key in mapping:
            return mapping[key]
        try:
            f = float(key)
            if f.is_integer() and str(int(f)) in mapping:
                return mapping[str(int(f))]
        except ValueError:
            pass
        return default if default is not None else v

    result[new_column_name] = source.map(_map_value)
    return result, f"Recoded '{source_column}' into '{new_column_name}' ({len(mapping)} mapping(s) applied)."


# ---------------------------------------------------------------------------
# Compute (safe expression evaluator)
# ---------------------------------------------------------------------------

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_ALLOWED_COMPARE = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}
_ALLOWED_FUNCS = {
    "abs": np.abs,
    "round": np.round,
    "min": np.minimum,
    "max": np.maximum,
    "sqrt": np.sqrt,
    "log": np.log,
    "log10": np.log10,
    "exp": np.exp,
    "colmin": lambda s: s.min(),
    "colmax": lambda s: s.max(),
    "colmean": lambda s: s.mean(),
    "colstd": lambda s: s.std(),
}


class _ExpressionError(ValueError):
    pass


class _SafeEval(ast.NodeVisitor):
    """Evaluates a restricted arithmetic expression AST against a column namespace.

    Only literals, arithmetic/comparison operators, column-name lookups, and a
    fixed whitelist of numpy/pandas functions are permitted — no attribute
    access, subscripts, comprehensions, or calls to arbitrary names.
    """

    def __init__(self, columns: dict[str, pd.Series]):
        self.columns = columns

    def visit(self, node):
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            return _ALLOWED_BINOPS[type(node.op)](self.visit(node.left), self.visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
            return _ALLOWED_UNARYOPS[type(node.op)](self.visit(node.operand))
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _ALLOWED_COMPARE:
            return _ALLOWED_COMPARE[type(node.ops[0])](self.visit(node.left), self.visit(node.comparators[0]))
        if isinstance(node, ast.Name):
            if node.id in self.columns:
                return self.columns[node.id]
            raise _ExpressionError(f"Unknown column or name: '{node.id}'")
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Call):
            fname = node.func.id if isinstance(node.func, ast.Name) else None
            if fname not in _ALLOWED_FUNCS or node.keywords:
                raise _ExpressionError(f"Function '{fname}' is not allowed.")
            args = [self.visit(a) for a in node.args]
            return _ALLOWED_FUNCS[fname](*args)
        raise _ExpressionError("Expression contains disallowed syntax.")


def compute_column(
    df: pd.DataFrame,
    new_column_name: str,
    expression: str,
    overwrite: bool = False,
) -> tuple[pd.DataFrame, str]:
    _check_new_name(df, new_column_name, overwrite)
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression: {exc}") from exc

    result = df.copy()
    columns_ns = {col: result[col] for col in result.columns}
    evaluator = _SafeEval(columns_ns)
    try:
        value = evaluator.visit(tree)
    except _ExpressionError as exc:
        raise ValueError(str(exc)) from exc
    except ZeroDivisionError:
        raise ValueError("Expression caused a division by zero.")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Could not evaluate expression: {exc}") from exc

    if np.isscalar(value):
        value = pd.Series(value, index=result.index)
    result[new_column_name] = value
    return result, f"Computed new column '{new_column_name}' from expression."


# ---------------------------------------------------------------------------
# Reverse-scoring
# ---------------------------------------------------------------------------

def reverse_score(
    df: pd.DataFrame,
    columns: list[str],
    min_value: float,
    max_value: float,
    suffix: str = "_r",
    overwrite: bool = False,
) -> tuple[pd.DataFrame, str]:
    if not columns:
        raise ValueError("At least one column is required.")
    _check_columns_exist(df, columns)
    if min_value >= max_value:
        raise ValueError("min_value must be less than max_value.")

    result = df.copy()
    created: list[str] = []
    for col in columns:
        series = result[col]
        if not pd.api.types.is_numeric_dtype(series):
            raise ValueError(f"Column '{col}' is not numeric; cannot reverse-score.")
        new_name = col if suffix == "" else f"{col}{suffix}"
        _check_new_name(result, new_name, overwrite or new_name == col)
        result[new_name] = (min_value + max_value) - series
        created.append(new_name)

    return result, f"Reverse-scored {len(created)} column(s): {', '.join(created)}."


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

MERGE_HOW = {"inner", "left", "right", "outer"}


def merge_datasets(
    df: pd.DataFrame,
    other_df: pd.DataFrame,
    left_on: str,
    right_on: str,
    how: str = "left",
) -> tuple[pd.DataFrame, str]:
    if how not in MERGE_HOW:
        raise ValueError(f"Unknown merge type: {how!r}")
    _check_columns_exist(df, [left_on])
    if right_on not in other_df.columns:
        raise ValueError(f"Column '{right_on}' not found in the second dataset.")

    before = len(df)
    result = df.merge(other_df, how=how, left_on=left_on, right_on=right_on, suffixes=("", "_2"))
    return result, f"Merged datasets on '{left_on}' = '{right_on}' ({how} join): {before} → {len(result)} row(s)."
