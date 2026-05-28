"""One-way ANOVA and factorial ANOVA with Tukey/Bonferroni post-hoc."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation


# ---------------------------------------------------------------------------
# One-way ANOVA
# ---------------------------------------------------------------------------

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

    statistics = {
        "f_statistic": round(float(f_stat), 4),
        "p_value": round(float(p_val), 4),
        "df_between": df_between,
        "df_within": df_within,
        "n": n_total,
        "groups": group_stats,
    }

    if options.post_hoc and p_val < 0.05:
        tukey = pairwise_tukeyhsd(valid[outcome].values, valid[group].values)
        rows = tukey.summary().data[1:]
        statistics["post_hoc"] = [
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
        statistics["post_hoc_bonferroni"] = _bonferroni_posthoc(valid, outcome, group, groups)

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


# ---------------------------------------------------------------------------
# Factorial ANOVA
# ---------------------------------------------------------------------------

def run_factorial(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    outcome = config.get("outcome")
    factors: list[str] = config.get("factors", [])
    if not outcome or len(factors) < 2:
        raise ValueError("outcome and at least two factors are required for factorial ANOVA.")

    formula = f"{_safe_col(outcome)} ~ {' * '.join(_safe_col(f) for f in factors)}"

    import statsmodels.api as sm
    from statsmodels.formula.api import ols

    valid = df[[outcome] + factors].dropna()
    n_total = len(valid)
    model = ols(formula, data=valid).fit()
    anova_table = sm.stats.anova_lm(model, typ=2)

    terms = []
    for term in anova_table.index:
        if term == "Residual":
            continue
        f_val = float(anova_table.loc[term, "F"])
        p_val_term = float(anova_table.loc[term, "PR(>F)"])
        df_effect = int(anova_table.loc[term, "df"])
        ss_effect = float(anova_table.loc[term, "sum_sq"])
        ss_total = float(anova_table["sum_sq"].sum())
        eta_sq = ss_effect / ss_total if ss_total > 0 else 0.0

        terms.append({
            "term": term,
            "f_statistic": round(f_val, 4),
            "p_value": round(p_val_term, 4),
            "df": df_effect,
            "eta_sq": round(eta_sq, 4),
        })

    # Per-factor group summaries
    group_stats: dict[str, dict] = {}
    for f in factors:
        grouped = valid.groupby(f)[outcome]
        group_stats[f] = {
            str(g): {
                "n": int(v.count()),
                "mean": round(float(v.mean()), 4),
                "sd": round(float(v.std()), 4),
            }
            for g, v in grouped
        }

    # Post-hoc per factor with >2 levels
    post_hoc_map: dict[str, list] = {}
    if options.post_hoc:
        for f in factors:
            unique_vals = valid[f].unique()
            if len(unique_vals) >= 3:
                ph = _bonferroni_posthoc(valid, outcome, f, unique_vals)
                if ph:
                    post_hoc_map[f] = ph

    # Residuals for assumption checks
    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        residuals = model.resid
        if n_total <= 100:
            sw_s, sw_p = stats.shapiro(residuals)
            checks.append(AssumptionCheck(
                name="Normality of residuals (Shapiro-Wilk)",
                status="pass" if sw_p > 0.05 else "amber",
                detail=f"W = {sw_s:.3f}, p = {sw_p:.3f}",
                fix_suggestion="Consider non-parametric alternatives if violated." if sw_p <= 0.05 else None,
            ))
        # Homogeneity of variance per factor
        for f in factors:
            groups_list = [valid[valid[f] == g][outcome].astype(float) for g in valid[f].unique()]
            if len(groups_list) >= 2:
                try:
                    lev_s, lev_p = stats.levene(*groups_list)
                    checks.append(AssumptionCheck(
                        name=f"Homogeneity of variances — {f} (Levene's)",
                        status="pass" if lev_p > 0.05 else "amber",
                        detail=f"F = {lev_s:.3f}, p = {lev_p:.3f}",
                        fix_suggestion="Consider data transformation or robust methods." if lev_p <= 0.05 else None,
                    ))
                except Exception:
                    pass

    r_squared = round(float(model.rsquared), 4)

    statistics = {
        "terms": terms,
        "n": n_total,
        "r_squared": r_squared,
        "groups": group_stats,
    }
    if post_hoc_map:
        statistics["post_hoc_bonferroni"] = post_hoc_map

    effect = None
    if options.effect_size:
        main_eta = max((t["eta_sq"] for t in terms), default=0.0)
        effect = EffectSize(
            name="eta² (max)",
            value=main_eta,
            interpretation=_eta_sq_interp(main_eta),
        )

    factor_list = ", ".join(factors)
    n_sig = sum(1 for t in terms if t["p_value"] < 0.05)
    plain = (
        f"A factorial ANOVA was performed on {outcome} with factors {factor_list} "
        f"(R² = {r_squared:.3f}). "
        f"{n_sig} of {len(terms)} effects were statistically significant."
    )
    apa = (
        f"A factorial ANOVA examined the effects of {factor_list} on {outcome}. "
        f"The model explained {r_squared:.1%} of the variance in {outcome}."
    )
    technical = (
        f"Factorial ANOVA — outcome: {outcome}, factors: {factor_list}, "
        f"N = {n_total}, R² = {r_squared:.4f}, formula: {formula}"
    )

    return AnalysisResult(
        test_key="factorial_anova",
        test_name="Factorial ANOVA",
        n_obs=n_total,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bonferroni_posthoc(valid: pd.DataFrame, outcome: str, group: str, groups) -> list[dict]:
    """Pairwise t-tests with Bonferroni correction."""
    group_list = list(groups)
    pairs = []
    for i in range(len(group_list)):
        for j in range(i + 1, len(group_list)):
            a = valid[valid[group] == group_list[i]][outcome].astype(float)
            b = valid[valid[group] == group_list[j]][outcome].astype(float)
            t_stat, p_raw = stats.ttest_ind(a, b)
            pairs.append({
                "group1": str(group_list[i]),
                "group2": str(group_list[j]),
                "mean_diff": round(float(a.mean() - b.mean()), 4),
                "p_raw": p_raw,
            })
    n_comparisons = len(pairs)
    for p in pairs:
        p["p_adj"] = round(min(float(p["p_raw"]) * n_comparisons, 1.0), 4)
        p["reject"] = p["p_adj"] < 0.05
        del p["p_raw"]
    return pairs


def _safe_col(name: str) -> str:
    """Wrap column name in Q() if it contains spaces or special chars."""
    if name.replace("_", "").replace(".", "").isalnum():
        return name
    return f'Q("{name}")'


def _eta_sq_interp(eta_sq: float) -> str:
    if eta_sq < 0.01:
        return "negligible"
    if eta_sq < 0.06:
        return "small"
    if eta_sq < 0.14:
        return "medium"
    return "large"
