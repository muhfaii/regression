"""One-way ANOVA with optional Tukey post-hoc."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    outcome = config.get("outcome")
    group = config.get("group")
    if not outcome or not group:
        raise ValueError("outcome and group are required.")

    valid = df[[outcome, group]].dropna()
    groups = valid[group].unique()
    if len(groups) < 3:
        raise ValueError(f"One-way ANOVA requires at least 3 groups; found {len(groups)}.")

    group_arrays = [valid[valid[group] == g][outcome].values.astype(float) for g in groups]
    f_stat, p_val = stats.f_oneway(*group_arrays)
    n_total = len(valid)

    grand_mean = float(valid[outcome].mean())
    ss_between = float(sum(len(g) * (g.mean() - grand_mean) ** 2 for g in group_arrays))
    ss_total = float(sum((valid[outcome] - grand_mean) ** 2))
    ss_within = ss_total - ss_between
    k = len(groups)
    df_between = k - 1
    df_within = n_total - k
    ms_within = ss_within / df_within if df_within > 0 else 0.0

    eta_sq = ss_between / ss_total if ss_total > 0 else 0.0
    omega_sq = (ss_between - df_between * ms_within) / (ss_total + ms_within) if (ss_total + ms_within) > 0 else 0.0

    group_stats = {
        str(g): {"n": len(gd), "mean": round(float(gd.mean()), 4), "sd": round(float(gd.std()), 4)}
        for g, gd in zip(groups, group_arrays)
    }

    post_hoc = None
    if options.post_hoc and p_val < 0.05:
        tukey = pairwise_tukeyhsd(valid[outcome].values, valid[group].values)
        rows = tukey.summary().data[1:]
        post_hoc = [
            {
                "group1": str(r[0]),
                "group2": str(r[1]),
                "mean_diff": round(float(r[2]), 4),
                "p_adj": round(float(r[3]), 4),
                "ci_low": round(float(r[4]), 4),
                "ci_high": round(float(r[5]), 4),
                "reject": bool(r[6]),
            }
            for r in rows
        ]

    statistics = {
        "f_statistic": round(float(f_stat), 4),
        "p_value": round(float(p_val), 4),
        "df_between": df_between,
        "df_within": df_within,
        "n": n_total,
        "groups": group_stats,
        "post_hoc": post_hoc,
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        lev_s, lev_p = stats.levene(*group_arrays)
        checks.append(AssumptionCheck(
            name="Homogeneity of variances (Levene's)",
            status="pass" if lev_p > 0.05 else "amber",
            detail=f"F = {lev_s:.3f}, p = {lev_p:.3f}",
            fix_suggestion="Consider Welch's ANOVA for unequal variances." if lev_p <= 0.05 else None,
        ))
        for g, gd in zip(groups, group_arrays):
            if len(gd) <= 50:
                sw_s, sw_p = stats.shapiro(gd)
                checks.append(AssumptionCheck(
                    name=f"Normality — {g} (Shapiro-Wilk)",
                    status="pass" if sw_p > 0.05 else "amber",
                    detail=f"W = {sw_s:.3f}, p = {sw_p:.3f}",
                    fix_suggestion="Consider Kruskal-Wallis for non-normal groups." if sw_p <= 0.05 else None,
                ))

    effect = None
    if options.effect_size:
        effect = EffectSize(
            name="eta²",
            value=round(eta_sq, 4),
            interpretation=_eta_sq_interp(eta_sq),
        )

    sig = "statistically significant" if p_val < 0.05 else "not statistically significant"
    plain = (
        f"A one-way ANOVA found a {sig} effect of {group} on {outcome}, "
        f"F({df_between}, {df_within}) = {f_stat:.2f}, p = {p_val:.3f}."
    )
    apa = (
        f"A one-way ANOVA examined the effect of {group} on {outcome}. "
        f"The effect was {'statistically significant' if p_val < 0.05 else 'not statistically significant'}, "
        f"F({df_between}, {df_within}) = {f_stat:.2f}, "
        f"p {'< .001' if p_val < 0.001 else f'= {p_val:.3f}'}, η² = {eta_sq:.3f}."
    )
    technical = (
        f"F({df_between}, {df_within}) = {f_stat:.4f}, p = {p_val:.4f}, "
        f"η² = {eta_sq:.4f}, ω² = {omega_sq:.4f}, N = {n_total}, k = {k}"
    )

    return AnalysisResult(
        test_key="one_way_anova",
        test_name="One-way ANOVA",
        n_obs=n_total,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )


def _eta_sq_interp(eta_sq: float) -> str:
    if eta_sq < 0.01:
        return "negligible"
    if eta_sq < 0.06:
        return "small"
    if eta_sq < 0.14:
        return "medium"
    return "large"
