from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class MissingDataRequest(BaseModel):
    session_id: str
    columns: list[str] = []
    strategy: Literal["listwise", "mean", "median", "mode", "constant"]
    constant: str | float | int | None = None


class RecodeRequest(BaseModel):
    session_id: str
    source_column: str
    new_column_name: str
    mapping: dict[str, str | float | int]
    default: str | float | int | None = None
    overwrite: bool = False


class ComputeRequest(BaseModel):
    session_id: str
    new_column_name: str
    expression: str
    overwrite: bool = False


class ReverseScoreRequest(BaseModel):
    session_id: str
    columns: list[str]
    min_value: float
    max_value: float
    suffix: str = "_r"
    overwrite: bool = False
