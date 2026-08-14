"""Correlation matrix — Pearson, Spearman, and Kendall for 2+ variables."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation, r_interpretation
from .multicomp import adjust_pvalues


def _adjust_p_matrix(p_matrix: np.ndarray, method: str) -> list[list[float]]:
    n = p_matrix.shape[0]
    tri = np.triu_indices(n, k=1)
    p_flat = p_matrix[tri]
    p_adj_flat = adjust_pvalues(p_flat, method)
    mat = np.zeros((n, n))
    mat[tri] = p_adj_flat
    mat = mat + mat.T
    np.fill_diagonal(mat, 1.0)
    return [[round(float(v), 4) for v in row] for row in mat]


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

    p_adjust_method = getattr(options, "p_adjust", "none")
    if p_adjust_method and p_adjust_method != "none":
        statistics["p_adjust_method"] = p_adjust_method
        statistics["matrix_p_pearson_adj"] = _adjust_p_matrix(mat_pp, p_adjust_method)
        statistics["matrix_p_spearman_adj"] = _adjust_p_matrix(mat_sp, p_adjust_method)
        statistics["matrix_p_kendall_adj"] = _adjust_p_matrix(mat_kp, p_adjust_method)

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

    interp = _build_interpretation(variables, n, mat_p, mat_pp)

    return AnalysisResult(
        test_key="correlation",
        test_name="Correlation",
        n_obs=n,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=interp,
        effect_size=effect,
    )


def _p_str(p: float) -> str:
    return "< .001" if p < 0.001 else f"= {p:.3f}"


def _strength(r: float) -> str:
    a = abs(r)
    if a < 0.1:
        return "negligible"
    if a < 0.3:
        return "weak"
    if a < 0.5:
        return "moderate"
    if a < 0.7:
        return "strong"
    return "very strong"


def _build_interpretation(
    variables: list[str], n: int, mat_p: np.ndarray, mat_pp: np.ndarray
) -> Interpretation:
    n_vars = len(variables)
    dof = n - 2
    var_list = ", ".join(variables)

    if n_vars == 2:
        r = float(mat_p[0, 1])
        p = float(mat_pp[0, 1])
        direction = "positive" if r >= 0 else "negative"
        strength = _strength(r)
        sig = p < 0.05

        plain = (
            f"There was a {strength} {direction} correlation between {variables[0]} and {variables[1]}, "
            f"r({dof}) = {r:.3f}, p {_p_str(p)}"
            f"{', which is statistically significant.' if sig else ', which is not statistically significant.'} "
            f"Spearman and Kendall coefficients are also reported for comparison."
        )
        apa = (
            f"A Pearson correlation was conducted to examine the relationship between "
            f"{variables[0]} and {variables[1]}. There was a {strength} {direction} correlation "
            f"between the two variables, r({dof}) = {r:.2f}, "
            f"p {_p_str(p)}, N = {n}."
        )
        technical = f"Pearson r = {r:.4f} (p = {p:.4f}), N = {n}, df = {dof}"
        return Interpretation(plain=plain, apa=apa, technical=technical)

    # 3+ variables: highlight the strongest pairwise relationship
    best_i, best_j, best_r = 0, 1, 0.0
    n_sig = 0
    for i in range(n_vars):
        for j in range(i + 1, n_vars):
            if abs(float(mat_p[i, j])) > abs(best_r):
                best_i, best_j, best_r = i, j, float(mat_p[i, j])
            if float(mat_pp[i, j]) < 0.05:
                n_sig += 1
    best_p = float(mat_pp[best_i, best_j])
    n_pairs = n_vars * (n_vars - 1) // 2

    plain = (
        f"A correlation matrix was computed among {n_vars} variables ({var_list}), N = {n}. "
        f"The strongest relationship was between {variables[best_i]} and {variables[best_j]} "
        f"({_strength(best_r)} {'positive' if best_r >= 0 else 'negative'}, "
        f"r({dof}) = {best_r:.3f}, p {_p_str(best_p)}). "
        f"{n_sig} of {n_pairs} pairwise correlations were statistically significant (p < .05)."
    )
    apa = (
        f"Pearson correlation coefficients were computed among {n_vars} variables ({var_list}), N = {n}. "
        f"The strongest correlation was observed between {variables[best_i]} and {variables[best_j]}, "
        f"r({dof}) = {best_r:.2f}, p {_p_str(best_p)}."
    )
    technical = (
        f"N = {n}, {n_vars} variables, {n_pairs} pairs, {n_sig} significant (p < .05) | "
        f"Strongest: {variables[best_i]}–{variables[best_j]}, r = {best_r:.4f}, p = {best_p:.4f}"
    )
    return Interpretation(plain=plain, apa=apa, technical=technical)
