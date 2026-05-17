"""
File ingestion, validation, and missing-data handling.

Covers: FR-1.1–1.5, FR-2.1–2.3
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

MAX_BYTES = 100 * 1024 * 1024  # 100 MB (FR-1.5)
SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}

MissingStrategy = Literal["listwise", "mean", "abort"]


@dataclass
class ColumnInfo:
    name: str
    dtype: str          # pandas dtype string, e.g. "float64", "object"
    missing_count: int
    missing_pct: float  # 0.0–100.0
    # FR-2.2: object-typed column where ≥50% of non-null values parse as float
    has_masked_numeric: bool = False


@dataclass
class IngestResult:
    df: pd.DataFrame
    row_count: int
    columns: list[ColumnInfo]
    warnings: list[str] = field(default_factory=list)

    @property
    def has_missing(self) -> bool:
        return any(c.missing_count > 0 for c in self.columns)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_file(
    source: bytes | str,
    filename: str,
    max_bytes: int = MAX_BYTES,
) -> IngestResult:
    """Parse a CSV or XLSX file and return an IngestResult.

    Args:
        source: Raw bytes (from Streamlit uploader) or a file-system path.
        filename: Original filename; used to infer the format.
        max_bytes: Size limit in bytes.

    Raises:
        ValueError: On unsupported format, oversized file, or parse failure.
    """
    ext = _extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Please upload a .csv or .xlsx file."
        )

    raw = _to_bytes(source)

    if len(raw) > max_bytes:
        mb = len(raw) / (1024 * 1024)
        raise ValueError(
            f"File is {mb:.1f} MB, which exceeds the 100 MB limit. "
            "Please reduce the file size and try again."
        )

    try:
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(raw))
        else:
            df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Could not parse file: {exc}") from exc

    if df.empty:
        raise ValueError("The uploaded file contains no data rows.")

    columns = [_describe_column(df[col], len(df)) for col in df.columns]
    warnings = _collect_warnings(columns)

    return IngestResult(
        df=df,
        row_count=len(df),
        columns=columns,
        warnings=warnings,
    )


def apply_missing_strategy(df: pd.DataFrame, strategy: MissingStrategy) -> pd.DataFrame:
    """Apply the user-chosen missing-data strategy and return a new DataFrame.

    Args:
        df: Input DataFrame (not modified in place).
        strategy:
            "listwise" — drop all rows with any missing value (FR-2.3).
            "mean"     — fill numeric columns with their column mean (FR-2.3).
            "abort"    — raise ValueError so the caller can stop the pipeline.

    Raises:
        ValueError: If strategy is "abort" and missing values are present.
    """
    if not df.isnull().any(axis=None):
        return df.copy()

    if strategy == "abort":
        raise ValueError(
            "Missing values detected. Please clean your data and re-upload."
        )
    if strategy == "listwise":
        return df.dropna().reset_index(drop=True)
    if strategy == "mean":
        result = df.copy()
        numeric_cols = result.select_dtypes(include="number").columns
        result[numeric_cols] = result[numeric_cols].fillna(result[numeric_cols].mean())
        return result

    raise ValueError(f"Unknown strategy: {strategy!r}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extension(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _to_bytes(source: bytes | str) -> bytes:
    if isinstance(source, bytes):
        return source
    with open(source, "rb") as fh:
        return fh.read()


def _describe_column(series: pd.Series, n_rows: int) -> ColumnInfo:
    missing = int(series.isnull().sum())
    return ColumnInfo(
        name=series.name,
        dtype=str(series.dtype),
        missing_count=missing,
        missing_pct=round(missing / n_rows * 100, 2) if n_rows else 0.0,
        has_masked_numeric=_is_masked_numeric(series),
    )


def _is_masked_numeric(series: pd.Series) -> bool:
    """True if a non-numeric column looks like it should be numeric (FR-2.2).

    Heuristic: if ≥50% of non-null values can be coerced to float, flag it.
    Handles both legacy object dtype and pandas 2 StringDtype.
    """
    if pd.api.types.is_numeric_dtype(series):
        return False
    non_null = series.dropna()
    if non_null.empty:
        return False
    coerced = pd.to_numeric(non_null, errors="coerce")
    parseable_pct = coerced.notna().sum() / len(non_null)
    return parseable_pct >= 0.5


def _collect_warnings(columns: list[ColumnInfo]) -> list[str]:
    warnings = []
    for col in columns:
        if col.missing_count > 0:
            warnings.append(
                f"'{col.name}': {col.missing_count} missing value(s) "
                f"({col.missing_pct:.1f}%)."
            )
        if col.has_masked_numeric:
            warnings.append(
                f"'{col.name}': column is text-typed but most values look numeric. "
                "Check for stray characters or formatting issues."
            )
    return warnings
