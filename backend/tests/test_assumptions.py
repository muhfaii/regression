"""Tests for the shared OLS assumption-check helpers."""
import numpy as np
import statsmodels.api as sm

from backend.analysis_modules.assumptions import (
    heteroskedasticity_check,
    ols_assumption_checks,
    residual_normality_check,
)


def _fit_ols(n=60, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = 2 * x + rng.normal(size=n)
    X = sm.add_constant(x)
    return sm.OLS(y, X).fit(), X


def test_residual_normality_check_runs_for_normal_sample():
    model, _ = _fit_ols(n=60)
    check = residual_normality_check(model.resid)
    assert check is not None
    assert check.name == "Normality of residuals (Shapiro-Wilk)"
    assert check.status in ("pass", "amber")


def test_residual_normality_check_skips_small_samples():
    assert residual_normality_check(np.array([1.0, 2.0])) is None


def test_residual_normality_check_skips_large_samples():
    model, _ = _fit_ols(n=150)
    assert residual_normality_check(model.resid) is None


def test_heteroskedasticity_check_runs():
    model, X = _fit_ols(n=60)
    check = heteroskedasticity_check(model.resid, X)
    assert check is not None
    assert check.name == "Homoscedasticity (Breusch-Pagan)"
    assert check.status in ("pass", "amber")


def test_ols_assumption_checks_combines_both():
    model, X = _fit_ols(n=60)
    checks = ols_assumption_checks(model, X)
    names = [c.name for c in checks]
    assert "Normality of residuals (Shapiro-Wilk)" in names
    assert "Homoscedasticity (Breusch-Pagan)" in names


def test_ols_assumption_checks_omits_normality_for_large_n():
    model, X = _fit_ols(n=150)
    checks = ols_assumption_checks(model, X)
    names = [c.name for c in checks]
    assert "Normality of residuals (Shapiro-Wilk)" not in names
    assert "Homoscedasticity (Breusch-Pagan)" in names
