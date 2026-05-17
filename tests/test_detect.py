"""Tests for regassist.detect (spec §5.1–5.2)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from regassist.detect import DetectionResult, detect_structure


# ---------------------------------------------------------------------------
# Dataset factories
# ---------------------------------------------------------------------------

def _cross_sectional(n=150, seed=0) -> pd.DataFrame:
    """150 firms, each observed once. No entity or time column."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "firm_id":   range(1, n + 1),          # all unique → not an entity ID
        "revenue":   rng.normal(500, 100, n),
        "employees": rng.integers(10, 500, n).astype(float),
        "profit":    rng.normal(50, 20, n),
    })


def _panel(n_entities=30, n_periods=10, seed=1) -> pd.DataFrame:
    """30 countries × 10 years = 300 observations."""
    rng = np.random.default_rng(seed)
    entities = [f"C{i:02d}" for i in range(n_entities)]
    years    = list(range(2010, 2010 + n_periods))
    rows = [(e, y) for e in entities for y in years]
    df = pd.DataFrame(rows, columns=["country", "year"])
    df["gdp"]   = rng.normal(50_000, 10_000, len(df))
    df["trade"] = rng.normal(20_000, 5_000, len(df))
    return df


def _panel_with_dates(n_entities=20, n_periods=8, seed=2) -> pd.DataFrame:
    """Panel where the time column contains actual date strings."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2015-01-01", periods=n_periods, freq="QS").strftime("%Y-%m-%d").tolist()
    firms = [f"F{i:02d}" for i in range(n_entities)]
    rows = [(f, d) for f in firms for d in dates]
    df = pd.DataFrame(rows, columns=["firm_id", "quarter"])
    df["revenue"] = rng.normal(1000, 200, len(df))
    return df


def _time_series(n=120, seed=3) -> pd.DataFrame:
    """120 monthly observations, single series — no entity column."""
    dates = pd.date_range("2010-01-01", periods=n, freq="MS").strftime("%Y-%m-%d")
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "date":   dates,
        "gdp":    rng.normal(1000, 50, n).cumsum(),
        "cpi":    rng.normal(100, 2, n),
    })


def _unbalanced_panel(seed=4) -> pd.DataFrame:
    """Unbalanced panel: not all entities observed in all periods."""
    rng = np.random.default_rng(seed)
    rows = []
    for entity in range(10):
        n_obs = rng.integers(4, 12)
        for t in range(int(n_obs)):
            rows.append({"entity": entity, "year": 2010 + t, "y": rng.normal()})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Returns DetectionResult
# ---------------------------------------------------------------------------

def test_returns_detection_result():
    assert isinstance(detect_structure(_cross_sectional()), DetectionResult)


def test_structure_values_are_valid():
    valid = {"cross_sectional", "panel", "time_series", "ambiguous"}
    for factory in [_cross_sectional, _panel, _time_series]:
        r = detect_structure(factory())
        assert r.structure in valid, f"Got structure={r.structure!r}"


def test_confidence_values_are_valid():
    for factory in [_cross_sectional, _panel, _time_series]:
        r = detect_structure(factory())
        assert r.confidence in {"high", "medium", "low"}


def test_reasoning_is_non_empty():
    for factory in [_cross_sectional, _panel, _time_series]:
        r = detect_structure(factory())
        assert len(r.reasoning) > 0


# ---------------------------------------------------------------------------
# Cross-sectional detection
# ---------------------------------------------------------------------------

def test_cross_sectional_detected():
    r = detect_structure(_cross_sectional())
    assert r.structure == "cross_sectional", f"Got {r.structure}"


def test_cross_sectional_no_entity_col():
    r = detect_structure(_cross_sectional())
    assert r.entity_col is None


def test_cross_sectional_high_confidence():
    r = detect_structure(_cross_sectional())
    assert r.confidence in ("high", "medium")


# ---------------------------------------------------------------------------
# Panel detection (integer year column)
# ---------------------------------------------------------------------------

def test_panel_detected_with_year_column():
    r = detect_structure(_panel())
    assert r.structure == "panel", f"Got {r.structure}"


def test_panel_entity_col_identified():
    r = detect_structure(_panel())
    assert r.entity_col == "country"


def test_panel_time_col_identified():
    r = detect_structure(_panel())
    assert r.time_col == "year"


def test_panel_n_entities_correct():
    r = detect_structure(_panel(n_entities=30))
    assert r.n_entities == 30


def test_panel_n_periods_correct():
    r = detect_structure(_panel(n_periods=10))
    assert r.n_periods == 10


def test_panel_high_confidence_for_balanced():
    r = detect_structure(_panel(n_entities=30, n_periods=10))
    assert r.confidence == "high"


# ---------------------------------------------------------------------------
# Panel detection (date-string time column)
# ---------------------------------------------------------------------------

def test_panel_detected_with_date_string_column():
    r = detect_structure(_panel_with_dates())
    assert r.structure == "panel", f"Got {r.structure}"


def test_panel_date_time_col_identified():
    r = detect_structure(_panel_with_dates())
    assert r.time_col == "quarter"


# ---------------------------------------------------------------------------
# Time-series detection
# ---------------------------------------------------------------------------

def test_time_series_detected():
    r = detect_structure(_time_series())
    assert r.structure == "time_series", f"Got {r.structure}"


def test_time_series_time_col_identified():
    r = detect_structure(_time_series())
    assert r.time_col == "date"


def test_time_series_no_entity_col():
    r = detect_structure(_time_series())
    assert r.entity_col is None


def test_time_series_n_periods_correct():
    r = detect_structure(_time_series(n=120))
    assert r.n_periods == 120


# ---------------------------------------------------------------------------
# Unbalanced panel still detected as panel
# ---------------------------------------------------------------------------

def test_unbalanced_panel_detected_as_panel():
    r = detect_structure(_unbalanced_panel())
    assert r.structure == "panel"


# ---------------------------------------------------------------------------
# Candidate lists
# ---------------------------------------------------------------------------

def test_panel_entity_in_candidates():
    r = detect_structure(_panel())
    assert "country" in r.entity_candidates


def test_panel_time_in_candidates():
    r = detect_structure(_panel())
    assert "year" in r.time_candidates


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_single_column_does_not_crash():
    df = pd.DataFrame({"x": range(50)})
    r = detect_structure(df)
    assert r.structure in {"cross_sectional", "time_series", "ambiguous"}


def test_all_unique_numeric_id_is_not_entity():
    """A column with all-unique numeric values should not be flagged as entity."""
    df = pd.DataFrame({
        "id":  range(100),
        "y":   np.random.default_rng(0).normal(0, 1, 100),
        "x":   np.random.default_rng(1).normal(0, 1, 100),
    })
    r = detect_structure(df)
    assert r.entity_col != "id"
