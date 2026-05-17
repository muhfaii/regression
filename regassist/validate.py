"""
Model specification validation.

Covers: FR-3.4 (dep var must be numeric), FR-3.5 (near-zero variance warning).
Returns structured results so the UI can display them and tests can assert on them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# A column is "near-zero variance" when its std is effectively zero.
# We use an absolute floor and a relative floor (CV) to catch both
# near-constant columns and columns centred at zero.
_ABS_STD_FLOOR = 1e-8
_CV_FLOOR = 1e-3  # std / |mean| < 0.1%


@dataclass
class SpecValidationResult:
    errors: list[str] = field(default_factory=list)      # block estimation
    warnings: list[str] = field(default_factory=list)    # show but allow

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def validate_spec(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
) -> SpecValidationResult:
    """Validate the variable selection before estimation.

    Args:
        df:         DataFrame after missing-data strategy has been applied.
        dep_var:    Name of the dependent variable column.
        indep_vars: Names of the independent variable columns.

    Returns:
        SpecValidationResult with lists of blocking errors and non-blocking warnings.
    """
    result = SpecValidationResult()

    # --- basic selection checks -----------------------------------------
    if not dep_var:
        result.errors.append("No dependent variable selected.")
        return result  # nothing more to check

    if not indep_vars:
        result.errors.append("Select at least one independent variable.")

    if dep_var in indep_vars:
        result.errors.append(
            f"'{dep_var}' appears as both dependent and independent variable."
        )

    # --- FR-3.4: dependent variable must be numeric and continuous -------
    if dep_var in df.columns:
        if not pd.api.types.is_numeric_dtype(df[dep_var]):
            result.errors.append(
                f"Dependent variable '{dep_var}' is not numeric. "
                "OLS requires a continuous numeric outcome."
            )
        else:
            n_unique = df[dep_var].nunique()
            if n_unique <= 2:
                result.warnings.append(
                    f"'{dep_var}' has only {n_unique} unique value(s). "
                    "If it is binary, OLS is technically applicable but "
                    "a logistic model would be more appropriate (Phase 2)."
                )

    # --- FR-3.5: near-zero variance in independent variables -------------
    for var in indep_vars:
        if var not in df.columns:
            continue
        series = df[var].dropna()
        if not pd.api.types.is_numeric_dtype(series):
            result.errors.append(
                f"Independent variable '{var}' is not numeric."
            )
            continue
        if _is_near_zero_variance(series):
            result.warnings.append(
                f"'{var}' has near-zero variance (almost constant). "
                "Its coefficient will be unreliable or unidentified."
            )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_near_zero_variance(series: pd.Series) -> bool:
    std = float(series.std())
    if std < _ABS_STD_FLOOR:
        return True
    mean = float(series.mean())
    if mean != 0 and (std / abs(mean)) < _CV_FLOOR:
        return True
    return False
