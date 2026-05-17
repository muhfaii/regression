"""Tests for regassist.validate (FR-3.4, FR-3.5)."""
import numpy as np
import pandas as pd
import pytest

from regassist.validate import validate_spec


@pytest.fixture
def df():
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "wage":      rng.normal(25, 5, 50),
        "education": rng.integers(8, 20, 50).astype(float),
        "age":       rng.normal(38, 10, 50),
        "constant":  np.ones(50),           # near-zero variance
        "label":     ["A"] * 50,            # non-numeric
    })


# ---------------------------------------------------------------------------
# Basic selection errors
# ---------------------------------------------------------------------------

def test_no_dep_var_is_error(df):
    r = validate_spec(df, "", ["education"])
    assert not r.ok
    assert any("dependent" in e.lower() for e in r.errors)


def test_no_indep_vars_is_error(df):
    r = validate_spec(df, "wage", [])
    assert not r.ok
    assert any("independent" in e.lower() for e in r.errors)


def test_dep_in_indep_is_error(df):
    r = validate_spec(df, "wage", ["wage", "education"])
    assert not r.ok
    assert any("both" in e.lower() for e in r.errors)


# ---------------------------------------------------------------------------
# FR-3.4: dependent variable must be numeric
# ---------------------------------------------------------------------------

def test_non_numeric_dep_var_is_error(df):
    r = validate_spec(df, "label", ["education"])
    assert not r.ok
    assert any("not numeric" in e.lower() for e in r.errors)


def test_numeric_dep_var_passes(df):
    r = validate_spec(df, "wage", ["education", "age"])
    assert r.ok
    assert r.errors == []


def test_binary_dep_var_warns(df):
    df2 = df.copy()
    df2["binary"] = [0, 1] * 25
    r = validate_spec(df2, "binary", ["education"])
    assert r.ok          # warning, not error
    assert any("binary" in w.lower() or "unique" in w.lower() for w in r.warnings)


# ---------------------------------------------------------------------------
# FR-3.5: near-zero variance warning
# ---------------------------------------------------------------------------

def test_constant_indep_var_warns(df):
    r = validate_spec(df, "wage", ["constant", "education"])
    assert r.ok                          # warning, not a blocking error
    assert any("constant" in w.lower() or "near-zero" in w.lower() for w in r.warnings)


def test_normal_indep_var_no_warning(df):
    r = validate_spec(df, "wage", ["education", "age"])
    assert r.ok
    assert r.warnings == []


def test_non_numeric_indep_var_is_error(df):
    r = validate_spec(df, "wage", ["label"])
    assert not r.ok
    assert any("not numeric" in e.lower() for e in r.errors)


# ---------------------------------------------------------------------------
# Clean path
# ---------------------------------------------------------------------------

def test_clean_spec_is_ok(df):
    r = validate_spec(df, "wage", ["education", "age"])
    assert r.ok
    assert r.errors == []
    assert r.warnings == []
