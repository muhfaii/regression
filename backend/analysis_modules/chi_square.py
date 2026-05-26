"""Chi-square test of independence with Cramér's V."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    col_a = config.get("col_a")
    col_b = config.get("col_b")
    if not col_a or not col_b:
        raise ValueError("col_a and col_b are required.")

    valid = df[[col_a, col_b]].dropna()
    n = len(valid)
    if n < 5:
        raise ValueError("At least 5 observations are required.")

    ct = pd.crosstab(valid[col_a], valid[col_b])
    chi2, p_val, dof, expected = stats.chi2_contingency(ct)

    # Cramér's V
    r, c = ct.shape
    cramers_v = float(np.sqrt(chi2 / (n * (min(r, c) - 1)))) if min(r, c) > 1 else 0.0

    low_expected = int((expected < 5).sum())
    low_expected_pct = round(low_expected / expected.size * 100, 1)

    statistics = {
        "chi2": round(float(chi2), 4),
        "p_value": round(float(p_val), 4),
        "df": dof,
        "n": n,
        "cramers_v": round(cramers_v, 4),
        "contingency_table": ct.to_dict(),
        "low_expected_cells": low_expected,
        "low_expected_pct": low_expected_pct,
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        checks.append(AssumptionCheck(
            name="Expected cell counts ≥ 5",
            status="pass" if low_expected_pct == 0 else ("amber" if low_expected_pct < 20 else "fail"),
            detail=f"{low_expected} cells ({low_expected_pct}%) have expected count < 5.",
            fix_suggestion="Consider Fisher's exact test or collapsing categories." if low_expected_pct > 0 else None,
        ))

    effect = None
    if options.effect_size:
        effect = EffectSize(
            name="Cramér's V",
            value=round(cramers_v, 4),
            interpretation=_cramers_v_interp(cramers_v, min(r, c) - 1),
        )

    sig = "statistically significant" if p_val < 0.05 else "not statistically significant"
    plain = (
        f"A chi-square test found a {sig} association between {col_a} and {col_b}, "
        f"χ²({dof}) = {chi2:.2f}, p = {p_val:.3f}."
    )
    apa = (
        f"A chi-square test of independence was performed to examine the relationship between "
        f"{col_a} and {col_b}. The relationship was "
        f"{'statistically significant' if p_val < 0.05 else 'not statistically significant'}, "
        f"χ²({dof}, N = {n}) = {chi2:.2f}, p {'< .001' if p_val < 0.001 else f'= {p_val:.3f}'}, "
        f"V = {cramers_v:.3f}."
    )
    technical = (
        f"χ²({dof}) = {chi2:.4f}, p = {p_val:.4f}, V = {cramers_v:.4f}, N = {n}, "
        f"low expected cells = {low_expected_pct}%"
    )

    return AnalysisResult(
        test_key="chi_square",
        test_name="Chi-square",
        n_obs=n,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )


def _cramers_v_interp(v: float, df_min: int) -> str:
    # Cohen (1988) benchmarks adjusted for df
    if df_min == 1:
        thresholds = (0.10, 0.30, 0.50)
    elif df_min == 2:
        thresholds = (0.07, 0.21, 0.35)
    else:
        thresholds = (0.06, 0.17, 0.29)
    if v < thresholds[0]:
        return "negligible"
    if v < thresholds[1]:
        return "small"
    if v < thresholds[2]:
        return "medium"
    return "large"
