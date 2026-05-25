"""Infer semantic column types from a DataFrame.

Extends regassist.detect heuristics with Likert detection for ordinal columns.
"""
from __future__ import annotations

import pandas as pd
from regassist.ingest import ColumnInfo as IngestColumnInfo

from backend.schemas.data import ColumnInfo, ColumnType


def infer_columns(df: pd.DataFrame, ingest_cols: list[IngestColumnInfo]) -> list[ColumnInfo]:
    return [_infer_column(df[col.name], col) for col in ingest_cols]


def _infer_column(series: pd.Series, ingest_col: IngestColumnInfo) -> ColumnInfo:
    return ColumnInfo(
        name=ingest_col.name,
        raw_dtype=ingest_col.dtype,
        inferred_type=_classify_type(series),
        missing_count=ingest_col.missing_count,
        missing_pct=ingest_col.missing_pct,
        has_masked_numeric=ingest_col.has_masked_numeric,
    )


def _classify_type(series: pd.Series) -> ColumnType:
    import pandas as pd

    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"

    if pd.api.types.is_numeric_dtype(series):
        if _is_likert(series):
            return "ordinal"
        nunique = series.nunique()
        # Low-cardinality integers likely categorical (e.g. binary 0/1)
        if nunique <= 10 and _all_integers(series):
            return "categorical"
        return "continuous"

    # Object/string → categorical
    return "categorical"


def _is_likert(series: pd.Series) -> bool:
    """True if a numeric column looks like a Likert scale (1–5 or 1–7, all integers)."""
    if not _all_integers(series):
        return False
    vals = set(series.dropna().astype(int).unique())
    return vals <= {1, 2, 3, 4, 5} or vals <= {1, 2, 3, 4, 5, 6, 7}


def _all_integers(series: pd.Series) -> bool:
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    try:
        return (non_null == non_null.astype(int)).all()
    except (ValueError, TypeError):
        return False
