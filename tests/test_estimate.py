"""Tests for regassist.estimate (FR-4.1).

The 'reference' values are computed once from the same seeded data with
a plain statsmodels call so we can detect any regression in our wrapper.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from regassist.estimate import FittedModel, estimate_ols


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def clean_df() -> pd.DataFrame:
    """50-row synthetic dataset with a known DGP.

    wage = 5 + 1.5*education + 0.3*age + N(0,3)
    Seed is fixed so coefficients are deterministic.
    """
    rng = np.random.default_rng(0)
    n = 50
    education = rng.integers(8, 20, n).astype(float)
    age = rng.normal(38, 10, n)
    wage = 5 + 1.5 * education + 0.3 * age + rng.normal(0, 3, n)
    return pd.DataFrame({"wage": wage, "education": education, "age": age})


@pytest.fixture(scope="module")
def fitted(clean_df) -> FittedModel:
    return estimate_ols(clean_df, "wage", ["education", "age"])


@pytest.fixture(scope="module")
def reference(clean_df) -> sm.regression.linear_model.RegressionResultsWrapper:
    """Direct statsmodels fit used as ground truth."""
    y = clean_df["wage"]
    X = sm.add_constant(clean_df[["education", "age"]])
    return sm.OLS(y, X).fit()


# ---------------------------------------------------------------------------
# FittedModel structure
# ---------------------------------------------------------------------------

def test_returns_fitted_model(fitted):
    assert isinstance(fitted, FittedModel)


def test_model_type(fitted):
    assert fitted.model_type == "ols"


def test_dep_indep_vars(fitted):
    assert fitted.dep_var == "wage"
    assert fitted.indep_vars == ["education", "age"]


def test_n_obs(fitted, clean_df):
    assert fitted.n_obs == len(clean_df)


def test_n_params(fitted):
    # 2 regressors + 1 constant
    assert fitted.n_params == 3


# ---------------------------------------------------------------------------
# Coefficients match reference (NFR-3: reproducible)
# ---------------------------------------------------------------------------

def test_params_match_reference(fitted, reference):
    pd.testing.assert_series_equal(fitted.params, reference.params, rtol=1e-6)


def test_bse_match_reference(fitted, reference):
    pd.testing.assert_series_equal(fitted.bse, reference.bse, rtol=1e-6)


def test_pvalues_match_reference(fitted, reference):
    pd.testing.assert_series_equal(fitted.pvalues, reference.pvalues, rtol=1e-6)


def test_conf_int_columns(fitted):
    assert list(fitted.conf_int.columns) == ["lower_95", "upper_95"]


def test_conf_int_values_match_reference(fitted, reference):
    ref_ci = reference.conf_int()
    assert fitted.conf_int["lower_95"].values == pytest.approx(ref_ci.iloc[:, 0].values, rel=1e-6)
    assert fitted.conf_int["upper_95"].values == pytest.approx(ref_ci.iloc[:, 1].values, rel=1e-6)


# ---------------------------------------------------------------------------
# Model fit statistics
# ---------------------------------------------------------------------------

def test_rsquared_in_unit_interval(fitted):
    assert 0.0 <= fitted.rsquared <= 1.0


def test_rsquared_adj_in_unit_interval(fitted):
    assert 0.0 <= fitted.rsquared_adj <= 1.0


def test_rsquared_matches_reference(fitted, reference):
    assert fitted.rsquared == pytest.approx(reference.rsquared, rel=1e-6)


def test_fvalue_positive(fitted):
    assert fitted.fvalue > 0


def test_f_pvalue_in_unit_interval(fitted):
    assert 0.0 <= fitted.f_pvalue <= 1.0


# ---------------------------------------------------------------------------
# Residuals and fitted values (OLS properties)
# ---------------------------------------------------------------------------

def test_residuals_sum_near_zero(fitted):
    """OLS residuals always sum to zero (with a constant)."""
    assert float(fitted.residuals.sum()) == pytest.approx(0.0, abs=1e-8)


def test_residuals_plus_fitted_equal_y(fitted):
    pd.testing.assert_series_equal(
        fitted.residuals + fitted.fitted,
        fitted.y,
        rtol=1e-8,
        check_names=False,  # arithmetic drops the Series name; values are what matter
    )


def test_residuals_length(fitted, clean_df):
    assert len(fitted.residuals) == len(clean_df)


def test_fitted_length(fitted, clean_df):
    assert len(fitted.fitted) == len(clean_df)


# ---------------------------------------------------------------------------
# Design matrix
# ---------------------------------------------------------------------------

def test_X_has_const_column(fitted):
    assert "const" in fitted.X.columns


def test_X_columns(fitted):
    assert list(fitted.X.columns) == ["const", "education", "age"]


def test_X_shape(fitted, clean_df):
    assert fitted.X.shape == (len(clean_df), 3)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_too_few_observations():
    df = pd.DataFrame({"y": [1.0, 2.0], "x": [1.0, 2.0]})
    with pytest.raises(ValueError, match="Too few"):
        estimate_ols(df, "y", ["x"])


def test_missing_rows_dropped():
    """Rows with NaN are dropped; estimation still works on complete cases."""
    rng = np.random.default_rng(1)
    df = pd.DataFrame({
        "y": rng.normal(0, 1, 30),
        "x": rng.normal(0, 1, 30),
    })
    df.loc[5, "x"] = float("nan")
    fitted = estimate_ols(df, "y", ["x"])
    assert fitted.n_obs == 29
