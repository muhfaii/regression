"""Tests for regassist.ingest (FR-1.1–1.5, FR-2.1–2.3)."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest

from regassist.ingest import (
    IngestResult,
    apply_missing_strategy,
    load_file,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# load_file — format & size validation (FR-1.1, FR-1.2, FR-1.5)
# ---------------------------------------------------------------------------

def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_load_csv_clean():
    result = load_file(_read("clean.csv"), "clean.csv")
    assert isinstance(result, IngestResult)
    assert result.row_count == 5
    assert len(result.columns) == 4
    assert result.warnings == []
    assert not result.has_missing


def test_load_csv_first_ten_rows(tmp_path):
    """FR-1.3 — ingest doesn't truncate; UI slices. Full frame returned."""
    # build a 15-row file and confirm all rows come back
    df = pd.DataFrame({"x": range(15), "y": range(15, 30)})
    path = tmp_path / "big.csv"
    df.to_csv(path, index=False)
    result = load_file(path.read_bytes(), "big.csv")
    assert result.row_count == 15


def test_load_xlsx(tmp_path):
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})
    path = tmp_path / "data.xlsx"
    df.to_excel(path, index=False, engine="openpyxl")
    result = load_file(path.read_bytes(), "data.xlsx")
    assert result.row_count == 3
    assert {c.name for c in result.columns} == {"a", "b"}


def test_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_file(b"some,data\n1,2", "data.tsv")


def test_oversized_file():
    oversized = b"x,y\n" + b"1,2\n" * 1  # tiny content, small limit
    with pytest.raises(ValueError, match="exceeds the 100 MB limit"):
        load_file(oversized, "data.csv", max_bytes=4)


def test_empty_file():
    with pytest.raises(ValueError, match="no data rows"):
        load_file(b"col1,col2\n", "empty.csv")


def test_unparseable_csv():
    with pytest.raises(ValueError, match="Could not parse"):
        load_file(b"\x00\xff\xfe", "bad.csv")


# ---------------------------------------------------------------------------
# load_file — column metadata (FR-1.4, FR-2.1, FR-2.2)
# ---------------------------------------------------------------------------

def test_missing_values_reported():
    result = load_file(_read("missing_values.csv"), "missing_values.csv")
    assert result.has_missing
    missing_cols = {c.name for c in result.columns if c.missing_count > 0}
    assert missing_cols == {"education", "age", "wage"}
    # at least one warning per missing column
    assert len(result.warnings) >= 3


def test_missing_pct_calculation():
    result = load_file(_read("missing_values.csv"), "missing_values.csv")
    edu = next(c for c in result.columns if c.name == "education")
    assert edu.missing_count == 1
    assert edu.missing_pct == pytest.approx(20.0)


def test_masked_numeric_detected():
    """FR-2.2 — wage column has one 'n/a' string; should be flagged."""
    result = load_file(_read("masked_numeric.csv"), "masked_numeric.csv")
    wage = next(c for c in result.columns if c.name == "wage")
    assert wage.has_masked_numeric
    assert any("wage" in w and "numeric" in w for w in result.warnings)


def test_clean_column_not_flagged():
    result = load_file(_read("clean.csv"), "clean.csv")
    assert all(not c.has_masked_numeric for c in result.columns)


# ---------------------------------------------------------------------------
# apply_missing_strategy (FR-2.3)
# ---------------------------------------------------------------------------

@pytest.fixture
def df_with_missing() -> pd.DataFrame:
    return pd.DataFrame({
        "x": [1.0, 2.0, None, 4.0],
        "y": [10.0, None, 30.0, 40.0],
        "z": [100.0, 200.0, 300.0, 400.0],
    })


def test_strategy_listwise(df_with_missing):
    result = apply_missing_strategy(df_with_missing, "listwise")
    assert result.isnull().sum().sum() == 0
    assert len(result) == 2  # rows 0 and 3 are complete


def test_strategy_mean(df_with_missing):
    result = apply_missing_strategy(df_with_missing, "mean")
    assert result.isnull().sum().sum() == 0
    assert result.loc[2, "x"] == pytest.approx((1 + 2 + 4) / 3)
    assert result.loc[1, "y"] == pytest.approx((10 + 30 + 40) / 3)


def test_strategy_abort(df_with_missing):
    with pytest.raises(ValueError, match="Missing values detected"):
        apply_missing_strategy(df_with_missing, "abort")


def test_strategy_no_missing_is_noop():
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    for strategy in ("listwise", "mean", "abort"):
        result = apply_missing_strategy(df, strategy)
        assert result.equals(df)


def test_strategy_mean_leaves_non_numeric_untouched():
    df = pd.DataFrame({
        "num": [1.0, None, 3.0],
        "cat": ["a", "b", None],
    })
    result = apply_missing_strategy(df, "mean")
    # numeric column filled; non-numeric left alone (no crash)
    assert result["num"].isnull().sum() == 0
    assert result["cat"].isnull().sum() == 1  # unchanged
