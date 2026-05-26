"""Pearson, Spearman, and Kendall correlation."""
from __future__ import annotations

import pandas as pd
from scipy import stats

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation, r_interpretation


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    col_a = config.get("col_a")
    col_b = config.get("col_b")
    if not col_a or not col_b:
        raise ValueError("col_a and col_b are required.")

    valid = df[[col_a, col_b]].dropna()
    a = valid[col_a].astype(float)
    b = valid[col_b].astype(float)
    n = len(valid)
    if n < 3:
        raise ValueError("At least 3 observations are required for correlation.")

    r_p, p_p = stats.pearsonr(a, b)
    r_s, p_s = stats.spearmanr(a, b)
    r_k, p_k = stats.kendalltau(a, b)

    statistics = {
        "n": n,
        "pearson": {"r": round(float(r_p), 4), "p": round(float(p_p), 4)},
        "spearman": {"r": round(float(r_s), 4), "p": round(float(p_s), 4)},
        "kendall": {"tau": round(float(r_k), 4), "p": round(float(p_k), 4)},
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        if n <= 50:
            sw_a, sw_p_a = stats.shapiro(a)
            sw_b, sw_p_b = stats.shapiro(b)
            checks.append(AssumptionCheck(
                name=f"Normality — {col_a} (Shapiro-Wilk)",
                status="pass" if sw_p_a > 0.05 else "amber",
                detail=f"W = {sw_a:.3f}, p = {sw_p_a:.3f}",
                fix_suggestion="Use Spearman or Kendall for non-normal variables." if sw_p_a <= 0.05 else None,
            ))
            checks.append(AssumptionCheck(
                name=f"Normality — {col_b} (Shapiro-Wilk)",
                status="pass" if sw_p_b > 0.05 else "amber",
                detail=f"W = {sw_b:.3f}, p = {sw_p_b:.3f}",
                fix_suggestion="Use Spearman or Kendall for non-normal variables." if sw_p_b <= 0.05 else None,
            ))

    effect = None
    if options.effect_size:
        effect = EffectSize(
            name="Pearson r",
            value=round(float(r_p), 4),
            interpretation=r_interpretation(r_p),
        )

    direction = "positive" if r_p > 0 else "negative"
    sig = "statistically significant" if p_p < 0.05 else "not statistically significant"
    plain = (
        f"There was a {r_interpretation(r_p)} {direction} correlation between {col_a} and {col_b}, "
        f"r = {r_p:.2f}, p = {p_p:.3f} ({sig})."
    )
    apa = (
        f"A Pearson correlation was computed to assess the relationship between {col_a} and {col_b}. "
        f"There was a {'significant' if p_p < 0.05 else 'non-significant'} "
        f"{direction} correlation between the two variables, "
        f"r({n - 2}) = {r_p:.2f}, p {'< .001' if p_p < 0.001 else f'= {p_p:.3f}'}."
    )
    technical = (
        f"Pearson r({n - 2}) = {r_p:.4f}, p = {p_p:.4f} | "
        f"Spearman ρ = {r_s:.4f}, p = {p_s:.4f} | "
        f"Kendall τ = {r_k:.4f}, p = {p_k:.4f} | N = {n}"
    )

    return AnalysisResult(
        test_key="correlation",
        test_name="Correlation",
        n_obs=n,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )
