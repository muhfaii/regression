from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ColumnType = Literal["continuous", "categorical", "ordinal", "date"]


class ColumnInfo(BaseModel):
    name: str
    raw_dtype: str
    inferred_type: ColumnType
    missing_count: int
    missing_pct: float
    has_masked_numeric: bool


class DatasetPreview(BaseModel):
    session_id: str
    filename: str
    row_count: int
    columns: list[ColumnInfo]
    dataset_context: Literal["survey", "generic"]
    warnings: list[str]
