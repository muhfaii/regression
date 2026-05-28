"""Correlation matrix — Pearson, Spearman, and Kendall for 2+ variables."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation, r_interpretation


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    variables: list[str] = config.get("variables", [])
    if len(variables) < 2:
        raise ValueError("At least two variables are required for correlation.")

    valid = df[variables].dropna()
    n = len(valid)
    if n < 3:
        raise ValueError("At least 3 observations are required for correlation.")

    n_vars = len(variables)
    mat_p = np.full((n_vars, n_vars), 1.0)
    mat_s = np.full((n_vars, n_vars), 1.0)
    mat_k = np.full((n_vars, n_vars), 1.0)
    mat_pp = np.full((n_vars, n_vars), 0.0)
    mat_sp = np.full((n_vars, n_vars), 0.0)
    mat_kp = np.full((n_vars, n_vars), 0.0)

    for i in range(n_vars):
        for j in range(i + 1, n_vars):
            a = valid[variables[i]].astype(float)
            b = valid[variables[j]].astype(float)

            r_p, p_p = stats.pearsonr(a, b)
            r_s, p_s = stats.spearmanr(a, b)
            r_k, p_k = stats.kendalltau(a, b)

            mat_p[i, j] = mat_p[j, i] = round(float(r_p), 4)
            mat_s[i, j] = mat_s[j, i] = round(float(r_s), 4)
            mat_k[i, j] = mat_k[j, i] = round(float(r_k), 4)
            mat_pp[i, j] = mat_pp[j, i] = round(float(p_p), 4)
            mat_sp[i, j] = mat_sp[j, i] = round(float(p_s), 4)
            mat_kp[i, j] = mat_kp[j, i] = round(float(p_k), 4)

    statistics = {
        "n": n,
        "n_vars": n_vars,
        "variable_names": variables,
        "matrix_pearson": mat_p.tolist(),
        "matrix_spearman": mat_s.tolist(),
        "matrix_kendall": mat_k.tolist(),
        "matrix_p_pearson": mat_pp.tolist(),
        "matrix_p_spearman": mat_sp.tolist(),
        "matrix_p_kendall": mat_kp.tolist(),
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks and n <= 50:
        for var in variables:
            sw_s, sw_p = stats.shapiro(valid[var].astype(float))
            checks.append(AssumptionCheck(
                name=f"Normality — {var} (Shapiro-Wilk)",
                status="pass" if sw_p > 0.05 else "amber",
                detail=f"W = {sw_s:.3f}, p = {sw_p:.3f}",
                fix_suggestion="Use Spearman or Kendall for non-normal variables." if sw_p <= 0.05 else None,
            ))

    effect = None
    if options.effect_size and n_vars == 2:
        r_pearson = mat_p[0, 1]
        effect = EffectSize(
            name="Pearson r",
            value=r_pearson,
            interpretation=r_interpretation(r_pearson),
        )

    var_list = ", ".join(variables)
    plain = f"A correlation matrix was computed for: {var_list} (N = {n})."
    apa = f"Pearson, Spearman, and Kendall correlation coefficients were computed for {var_list}."
    technical = f"Correlation matrix — N = {n}, {n_vars} variables"

    return AnalysisResult(
        test_key="correlation",
        test_name="Correlation",
        n_obs=n,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )
