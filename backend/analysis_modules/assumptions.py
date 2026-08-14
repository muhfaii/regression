"""Shared assumption-check helpers for OLS-based analysis modules.

Modules that fit their own statsmodels OLS results (moderation, mediation)
use these instead of leaving assumption_checks empty, so users get the same
normality/heteroskedasticity feedback available in regression and ANOVA.
"""
from __future__ import annotations

import numpy as np
from scipy import stats
from statsmodels.stats.diagnostic import het_breuschpagan

from .base import AssumptionCheck

_SHAPIRO_MAX_N = 100


def residual_normality_check(residuals: np.ndarray) -> AssumptionCheck | None:
    """Shapiro-Wilk test on model residuals.

    Returns None for samples too small to test or too large for Shapiro-Wilk
    to remain reliable/performant — matches the threshold used elsewhere in
    this codebase (e.g. anova.py, mixed_anova.py).
    """
    n = len(residuals)
    if n < 3 or n > _SHAPIRO_MAX_N:
        return None
    sw_stat, sw_p = stats.shapiro(residuals)
    return AssumptionCheck(
        name="Normality of residuals (Shapiro-Wilk)",
        status="pass" if sw_p > 0.05 else "amber",
        detail=f"W = {sw_stat:.3f}, p = {sw_p:.3f}",
        fix_suggestion=(
            "Residuals deviate from normality; interpret p-values with caution "
            "or consider a bootstrap-based approach."
        ) if sw_p <= 0.05 else None,
    )


def heteroskedasticity_check(residuals: np.ndarray, exog: np.ndarray) -> AssumptionCheck | None:
    """Breusch-Pagan test for constant variance of residuals."""
    try:
        lm_stat, lm_p, _f_stat, _f_p = het_breuschpagan(residuals, exog)
    except (ValueError, np.linalg.LinAlgError):
        return None
    return AssumptionCheck(
        name="Homoscedasticity (Breusch-Pagan)",
        status="pass" if lm_p > 0.05 else "amber",
        detail=f"LM = {lm_stat:.3f}, p = {lm_p:.3f}",
        fix_suggestion=(
            "Variance of residuals is not constant; the heteroskedasticity-robust "
            "standard errors already used here help mitigate this."
        ) if lm_p <= 0.05 else None,
    )


def ols_assumption_checks(model, exog: np.ndarray) -> list[AssumptionCheck]:
    """Run the standard set of checks against a fitted statsmodels OLS result."""
    checks = [residual_normality_check(model.resid), heteroskedasticity_check(model.resid, exog)]
    return [c for c in checks if c is not None]
