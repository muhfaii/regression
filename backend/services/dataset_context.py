"""Silent dataset context inference.

Never surfaced to the user as a required step — used only to pre-suggest
relevant analyses on the Home screen.
"""
from __future__ import annotations

from typing import Literal

from backend.schemas.data import ColumnInfo

DatasetContext = Literal["survey", "generic"]


def infer_context(columns: list[ColumnInfo]) -> DatasetContext:
    """Return 'survey' if >50% of columns are ordinal (Likert-scale), else 'generic'."""
    if not columns:
        return "generic"
    ordinal_count = sum(1 for c in columns if c.inferred_type == "ordinal")
    if ordinal_count / len(columns) > 0.5:
        return "survey"
    return "generic"
