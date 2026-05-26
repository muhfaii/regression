"""Non-parametric tests: Mann-Whitney U, Wilcoxon Signed-Rank, Kruskal-Wallis."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation, r_interpretation


def run_mann_whitney(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    outcome = config.get("outcome")
    group = config.get("group")
    if not outcome or not group:
        raise ValueError("outcome and group are required.")

    valid = df[[outcome, group]].dropna()
    groups = valid[group].unique()
    if len(groups) != 2:
        raise ValueError(f"Group variable must have exactly 2 groups; found {len(groups)}.")

    g1 = valid[valid[group] == groups[0]][outcome].values.astype(float)
    g2 = valid[valid[group] == groups[1]][outcome].values.astype(float)
    n1, n2 = len(g1), len(g2)

    u_stat, p_val = stats.mannwhitneyu(g1, g2, alternative="two-sided")

    # Rank-biserial correlation as effect size
    r_rb = 1 - (2 * u_stat) / (n1 * n2)

    statistics = {
        "group_a": str(groups[0]),
        "group_b": str(groups[1]),
        "median_a": round(float(np.median(g1)), 4),
        "median_b": round(float(np.median(g2)), 4),
        "n_a": n1,
        "n_b": n2,
        "u_statistic": round(float(u_stat), 4),
        "p_value": round(float(p_val), 4),
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        checks.append(AssumptionCheck(
            name="Independence of observations",
            status="pass",
            detail="Mann-Whitney U assumes independent samples.",
        ))

    effect = None
    if options.effect_size:
        effect = EffectSize(
            name="Rank-biserial r",
            value=round(float(r_rb), 4),
            interpretation=r_interpretation(r_rb),
        )

    sig = "statistically significant" if p_val < 0.05 else "not statistically significant"
    plain = (
        f"A Mann-Whitney U test found a {sig} difference in {outcome} "
        f"between {groups[0]} (Mdn = {np.median(g1):.2f}) and {groups[1]} (Mdn = {np.median(g2):.2f}), "
        f"U = {u_stat:.0f}, p = {p_val:.3f}."
    )
    apa = (
        f"A Mann-Whitney U test indicated that {outcome} scores "
        f"{'differed significantly' if p_val < 0.05 else 'did not differ significantly'} "
        f"between {groups[0]} (Mdn = {np.median(g1):.2f}) and {groups[1]} (Mdn = {np.median(g2):.2f}), "
        f"U = {u_stat:.0f}, p {'< .001' if p_val < 0.001 else f'= {p_val:.3f}'}."
    )
    technical = (
        f"U = {u_stat:.4f}, p = {p_val:.4f}, r_rb = {r_rb:.4f}, "
        f"n₁ = {n1}, n₂ = {n2}"
    )

    return AnalysisResult(
        test_key="mann_whitney",
        test_name="Mann-Whitney U",
        n_obs=n1 + n2,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )


def run_wilcoxon(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    col_a = config.get("col_a")
    col_b = config.get("col_b")
    if not col_a or not col_b:
        raise ValueError("col_a and col_b are required.")

    valid = df[[col_a, col_b]].dropna()
    a = valid[col_a].astype(float)
    b = valid[col_b].astype(float)
    diff = a - b
    n = len(valid)

    w_stat, p_val = stats.wilcoxon(a, b)

    # Rank-biserial r for Wilcoxon: r = W / (n*(n+1)/2)
    r_rb = float(w_stat) / (n * (n + 1) / 2)

    statistics = {
        "median_a": round(float(a.median()), 4),
        "median_b": round(float(b.median()), 4),
        "median_diff": round(float(diff.median()), 4),
        "w_statistic": round(float(w_stat), 4),
        "p_value": round(float(p_val), 4),
        "n": n,
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        checks.append(AssumptionCheck(
            name="Paired observations",
            status="pass",
            detail="Wilcoxon assumes paired/matched samples.",
        ))

    effect = None
    if options.effect_size:
        effect = EffectSize(
            name="Rank-biserial r",
            value=round(r_rb, 4),
            interpretation=r_interpretation(r_rb),
        )

    plain = (
        f"A Wilcoxon Signed-Rank test found a "
        f"{'significant' if p_val < 0.05 else 'non-significant'} difference between "
        f"{col_a} (Mdn = {float(a.median()):.2f}) and {col_b} (Mdn = {float(b.median()):.2f}), "
        f"W = {w_stat:.0f}, p = {p_val:.3f}."
    )
    apa = (
        f"A Wilcoxon Signed-Rank test indicated a "
        f"{'significant' if p_val < 0.05 else 'non-significant'} difference between "
        f"{col_a} (Mdn = {float(a.median()):.2f}) and {col_b} (Mdn = {float(b.median()):.2f}), "
        f"W = {w_stat:.0f}, p {'< .001' if p_val < 0.001 else f'= {p_val:.3f}'}."
    )
    technical = (
        f"W = {w_stat:.4f}, p = {p_val:.4f}, r_rb = {r_rb:.4f}, N = {n}"
    )

    return AnalysisResult(
        test_key="wilcoxon",
        test_name="Wilcoxon Signed-Rank",
        n_obs=n,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )


def run_kruskal_wallis(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    outcome = config.get("outcome")
    group = config.get("group")
    if not outcome or not group:
        raise ValueError("outcome and group are required.")

    valid = df[[outcome, group]].dropna()
    groups = valid[group].unique()
    if len(groups) < 3:
        raise ValueError(f"Kruskal-Wallis requires at least 3 groups; found {len(groups)}.")

    group_arrays = [valid[valid[group] == g][outcome].values.astype(float) for g in groups]
    h_stat, p_val = stats.kruskal(*group_arrays)
    n_total = len(valid)
    k = len(groups)

    # eta²H effect size
    eta_sq_h = (h_stat - k + 1) / (n_total - k) if n_total > k else 0.0

    group_stats = {
        str(g): {"n": len(gd), "median": round(float(np.median(gd)), 4)}
        for g, gd in zip(groups, group_arrays)
    }

    statistics = {
        "h_statistic": round(float(h_stat), 4),
        "p_value": round(float(p_val), 4),
        "df": k - 1,
        "n": n_total,
        "groups": group_stats,
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        checks.append(AssumptionCheck(
            name="Independence of groups",
            status="pass",
            detail="Kruskal-Wallis assumes independent observations across groups.",
        ))

    effect = None
    if options.effect_size:
        effect = EffectSize(
            name="eta²H",
            value=round(max(eta_sq_h, 0.0), 4),
            interpretation=_eta_sq_interp(eta_sq_h),
        )

    sig = "statistically significant" if p_val < 0.05 else "not statistically significant"
    plain = (
        f"A Kruskal-Wallis test found a {sig} difference in {outcome} across {group} groups, "
        f"H({k - 1}) = {h_stat:.2f}, p = {p_val:.3f}."
    )
    apa = (
        f"A Kruskal-Wallis test indicated that {outcome} "
        f"{'differed significantly' if p_val < 0.05 else 'did not differ significantly'} "
        f"across {group} groups, H({k - 1}) = {h_stat:.2f}, "
        f"p {'< .001' if p_val < 0.001 else f'= {p_val:.3f}'}."
    )
    technical = (
        f"H({k - 1}) = {h_stat:.4f}, p = {p_val:.4f}, η²H = {max(eta_sq_h, 0.0):.4f}, "
        f"N = {n_total}, k = {k}"
    )

    return AnalysisResult(
        test_key="kruskal_wallis",
        test_name="Kruskal-Wallis",
        n_obs=n_total,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )


def _eta_sq_interp(v: float) -> str:
    v = abs(v)
    if v < 0.01:
        return "negligible"
    if v < 0.06:
        return "small"
    if v < 0.14:
        return "medium"
    return "large"
