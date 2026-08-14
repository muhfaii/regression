"""Tests for data prep operations: missing data, recode, compute, reverse-score, merge."""
import numpy as np
import pandas as pd
import pytest

from backend.services import dataprep


@pytest.fixture
def df():
    return pd.DataFrame({
        "age": [25.0, np.nan, 35.0, 40.0],
        "group": ["A", "B", np.nan, "A"],
        "item1": [1, 2, 3, 4],
        "item2": [5, 4, 3, 2],
        "id": [1, 2, 3, 4],
    })


# ---------------------------------------------------------------------------
# Missing data
# ---------------------------------------------------------------------------

def test_listwise_deletion(df):
    result, msg = dataprep.apply_missing_strategy(df, ["age"], "listwise")
    assert len(result) == 3
    assert result["age"].isna().sum() == 0
    assert "Removed 1 row" in msg


def test_mean_imputation(df):
    result, _ = dataprep.apply_missing_strategy(df, ["age"], "mean")
    assert result["age"].isna().sum() == 0
    assert result["age"].iloc[1] == pytest.approx((25 + 35 + 40) / 3)


def test_median_imputation(df):
    result, _ = dataprep.apply_missing_strategy(df, ["age"], "median")
    assert result["age"].iloc[1] == pytest.approx(35.0)


def test_mean_imputation_rejects_non_numeric(df):
    with pytest.raises(ValueError, match="not numeric"):
        dataprep.apply_missing_strategy(df, ["group"], "mean")


def test_mode_imputation_categorical(df):
    result, _ = dataprep.apply_missing_strategy(df, ["group"], "mode")
    assert result["group"].isna().sum() == 0
    assert result["group"].iloc[2] == "A"


def test_constant_fill(df):
    result, _ = dataprep.apply_missing_strategy(df, ["group"], "constant", constant="Unknown")
    assert result["group"].iloc[2] == "Unknown"


def test_constant_requires_value(df):
    with pytest.raises(ValueError, match="constant value is required"):
        dataprep.apply_missing_strategy(df, ["group"], "constant")


def test_unknown_strategy_rejected(df):
    with pytest.raises(ValueError, match="Unknown strategy"):
        dataprep.apply_missing_strategy(df, ["age"], "bogus")


def test_missing_columns_defaults_to_all(df):
    result, msg = dataprep.apply_missing_strategy(df, None, "listwise")
    assert len(result) == 2  # rows without any nulls
    assert "age" in msg and "group" in msg


def test_unknown_column_raises(df):
    with pytest.raises(ValueError, match="not found"):
        dataprep.apply_missing_strategy(df, ["nope"], "listwise")


# ---------------------------------------------------------------------------
# Recode
# ---------------------------------------------------------------------------

def test_recode_basic(df):
    result, _ = dataprep.recode_column(df, "group", "group_num", {"A": 1, "B": 2})
    assert result["group_num"].tolist()[:2] == [1, 2]


def test_recode_with_default(df):
    result, _ = dataprep.recode_column(df, "group", "group_num", {"A": 1}, default=0)
    assert result["group_num"].iloc[1] == 0


def test_recode_existing_name_requires_overwrite(df):
    with pytest.raises(ValueError, match="already exists"):
        dataprep.recode_column(df, "group", "age", {"A": 1, "B": 2})


def test_recode_invalid_new_name(df):
    with pytest.raises(ValueError, match="not a valid column name"):
        dataprep.recode_column(df, "group", "bad name!", {"A": 1})


def test_recode_empty_mapping_rejected(df):
    with pytest.raises(ValueError, match="mapping entry is required"):
        dataprep.recode_column(df, "group", "group_num", {})


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

def test_compute_arithmetic(df):
    result, _ = dataprep.compute_column(df, "total", "item1 + item2")
    assert result["total"].tolist() == [6, 6, 6, 6]


def test_compute_with_functions(df):
    result, _ = dataprep.compute_column(df, "scaled", "(item1 - colmin(item1)) / (colmax(item1) - colmin(item1))")
    assert result["scaled"].iloc[0] == pytest.approx(0.0)
    assert result["scaled"].iloc[-1] == pytest.approx(1.0)


def test_compute_rejects_disallowed_syntax(df):
    with pytest.raises(ValueError):
        dataprep.compute_column(df, "bad", "__import__('os').system('echo hi')")


def test_compute_rejects_unknown_function(df):
    with pytest.raises(ValueError, match="not allowed"):
        dataprep.compute_column(df, "bad", "eval(item1)")


def test_compute_rejects_unknown_name(df):
    with pytest.raises(ValueError, match="Unknown column"):
        dataprep.compute_column(df, "bad", "nonexistent_col + 1")


def test_compute_existing_name_requires_overwrite(df):
    with pytest.raises(ValueError, match="already exists"):
        dataprep.compute_column(df, "item1", "item1 + 1")


def test_compute_overwrite_allowed(df):
    result, _ = dataprep.compute_column(df, "item1", "item1 * 2", overwrite=True)
    assert result["item1"].tolist() == [2, 4, 6, 8]


# ---------------------------------------------------------------------------
# Reverse-score
# ---------------------------------------------------------------------------

def test_reverse_score_basic(df):
    result, _ = dataprep.reverse_score(df, ["item1"], min_value=1, max_value=5)
    assert result["item1_r"].tolist() == [5, 4, 3, 2]
    assert "item1" in result.columns  # original untouched


def test_reverse_score_requires_numeric(df):
    with pytest.raises(ValueError, match="not numeric"):
        dataprep.reverse_score(df, ["group"], min_value=1, max_value=5)


def test_reverse_score_invalid_range(df):
    with pytest.raises(ValueError, match="min_value must be less"):
        dataprep.reverse_score(df, ["item1"], min_value=5, max_value=1)


def test_reverse_score_empty_columns(df):
    with pytest.raises(ValueError, match="At least one column"):
        dataprep.reverse_score(df, [], min_value=1, max_value=5)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def test_merge_left_join(df):
    other = pd.DataFrame({"id": [1, 2, 3], "extra": ["x", "y", "z"]})
    result, msg = dataprep.merge_datasets(df, other, left_on="id", right_on="id", how="left")
    assert len(result) == 4
    assert result["extra"].iloc[3] != result["extra"].iloc[3]  # NaN for id=4
    assert "left join" in msg


def test_merge_inner_join(df):
    other = pd.DataFrame({"id": [1, 2, 3], "extra": ["x", "y", "z"]})
    result, _ = dataprep.merge_datasets(df, other, left_on="id", right_on="id", how="inner")
    assert len(result) == 3


def test_merge_unknown_how_rejected(df):
    other = pd.DataFrame({"id": [1], "extra": ["x"]})
    with pytest.raises(ValueError, match="Unknown merge type"):
        dataprep.merge_datasets(df, other, left_on="id", right_on="id", how="bogus")


def test_merge_missing_right_column(df):
    other = pd.DataFrame({"other_id": [1], "extra": ["x"]})
    with pytest.raises(ValueError, match="not found in the second dataset"):
        dataprep.merge_datasets(df, other, left_on="id", right_on="other_id_typo", how="left")
