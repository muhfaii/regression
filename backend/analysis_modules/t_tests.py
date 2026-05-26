"""Independent t-test and Paired t-test."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation, cohen_d_interpretation


def run_independent_t(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
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

    lev_stat, lev_p = stats.levene(g1, g2)
    equal_var = bool(lev_p > 0.05)

    t_stat, p_val = stats.ttest_ind(g1, g2, equal_var=equal_var)
    n1, n2 = len(g1), len(g2)
    df_val = n1 + n2 - 2

    pooled_sd = float(np.sqrt(((n1 - 1) * g1.std() ** 2 + (n2 - 1) * g2.std() ** 2) / (n1 + n2 - 2)))
    d = float((g1.mean() - g2.mean()) / pooled_sd) if pooled_sd > 0 else 0.0
    md = float(g1.mean() - g2.mean())
    se = pooled_sd * float(np.sqrt(1 / n1 + 1 / n2))
    t_crit = float(stats.t.ppf(0.975, df_val))

    statistics = {
        "group_a": str(groups[0]),
        "group_b": str(groups[1]),
        "mean_a": round(float(g1.mean()), 4),
        "mean_b": round(float(g2.mean()), 4),
        "sd_a": round(float(g1.std()), 4),
        "sd_b": round(float(g2.std()), 4),
        "n_a": n1,
        "n_b": n2,
        "t_statistic": round(float(t_stat), 4),
        "df": df_val,
        "p_value": round(float(p_val), 4),
        "mean_diff": round(md, 4),
        "ci_low": round(md - t_crit * se, 4),
        "ci_high": round(md + t_crit * se, 4),
        "equal_variances": equal_var,
        "levene_p": round(float(lev_p), 4),
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        checks.append(AssumptionCheck(
            name="Equal variances (Levene's test)",
            status="pass" if lev_p > 0.05 else "amber",
            detail=f"Levene's F = {lev_stat:.3f}, p = {lev_p:.3f}",
            fix_suggestion="Welch's correction was applied automatically." if not equal_var else None,
        ))
        for g, label in [(g1, str(groups[0])), (g2, str(groups[1]))]:
            if len(g) <= 50:
                sw_s, sw_p = stats.shapiro(g)
                checks.append(AssumptionCheck(
                    name=f"Normality — {label} (Shapiro-Wilk)",
                    status="pass" if sw_p > 0.05 else "amber",
                    detail=f"W = {sw_s:.3f}, p = {sw_p:.3f}",
                    fix_suggestion="Consider Mann-Whitney U for non-normal data." if sw_p <= 0.05 else None,
                ))

    effect = None
    if options.effect_size:
        effect = EffectSize(name="Cohen's d", value=round(d, 4), interpretation=cohen_d_interpretation(d))

    sig = "statistically significant" if p_val < 0.05 else "not statistically significant"
    plain = (
        f"The difference in {outcome} between {groups[0]} (M = {g1.mean():.2f}) "
        f"and {groups[1]} (M = {g2.mean():.2f}) was {sig} "
        f"(t({df_val}) = {t_stat:.2f}, p = {p_val:.3f})."
    )
    apa = (
        f"An independent samples t-test{' (Welch correction)' if not equal_var else ''} "
        f"indicated that {outcome} scores for {groups[0]} (M = {g1.mean():.2f}, SD = {g1.std():.2f}) "
        f"{'differed significantly from' if p_val < 0.05 else 'did not differ significantly from'} "
        f"{groups[1]} (M = {g2.mean():.2f}, SD = {g2.std():.2f}), "
        f"t({df_val}) = {t_stat:.2f}, p {'< .001' if p_val < 0.001 else f'= {p_val:.3f}'}."
    )
    technical = (
        f"t({df_val}) = {t_stat:.4f}, p = {p_val:.4f}, "
        f"MD = {md:.4f}, 95% CI [{md - t_crit * se:.4f}, {md + t_crit * se:.4f}], "
        f"{'Welch' if not equal_var else 'Student'}'s t, N = {n1 + n2}"
    )

    return AnalysisResult(
        test_key="independent_t",
        test_name="Independent t-test",
        n_obs=n1 + n2,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )


def run_paired_t(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    col_a = config.get("col_a")
    col_b = config.get("col_b")
    if not col_a or not col_b:
        raise ValueError("col_a and col_b are required.")

    valid = df[[col_a, col_b]].dropna()
    a = valid[col_a].astype(float)
    b = valid[col_b].astype(float)
    n = len(valid)
    diff = a - b

    t_stat, p_val = stats.ttest_rel(a, b)
    df_val = n - 1
    dz = float(diff.mean() / diff.std()) if float(diff.std()) > 0 else 0.0
    se = float(diff.std() / np.sqrt(n))
    t_crit = float(stats.t.ppf(0.975, df_val))
    md = float(diff.mean())

    statistics = {
        "mean_a": round(float(a.mean()), 4),
        "mean_b": round(float(b.mean()), 4),
        "sd_a": round(float(a.std()), 4),
        "sd_b": round(float(b.std()), 4),
        "mean_diff": round(md, 4),
        "sd_diff": round(float(diff.std()), 4),
        "t_statistic": round(float(t_stat), 4),
        "df": df_val,
        "p_value": round(float(p_val), 4),
        "ci_low": round(md - t_crit * se, 4),
        "ci_high": round(md + t_crit * se, 4),
        "n": n,
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks and n <= 50:
        sw_s, sw_p = stats.shapiro(diff)
        checks.append(AssumptionCheck(
            name="Normality of differences (Shapiro-Wilk)",
            status="pass" if sw_p > 0.05 else "amber",
            detail=f"W = {sw_s:.3f}, p = {sw_p:.3f}",
            fix_suggestion="Consider Wilcoxon Signed-Rank for non-normal differences." if sw_p <= 0.05 else None,
        ))

    effect = None
    if options.effect_size:
        effect = EffectSize(name="Cohen's dz", value=round(dz, 4), interpretation=cohen_d_interpretation(dz))

    plain = (
        f"A paired t-test showed that {col_a} (M = {float(a.mean()):.2f}) and "
        f"{col_b} (M = {float(b.mean()):.2f}) "
        f"{'differed significantly' if p_val < 0.05 else 'did not differ significantly'} "
        f"(t({df_val}) = {t_stat:.2f}, p = {p_val:.3f})."
    )
    apa = (
        f"A paired samples t-test indicated a "
        f"{'significant' if p_val < 0.05 else 'non-significant'} difference between "
        f"{col_a} (M = {float(a.mean()):.2f}, SD = {float(a.std()):.2f}) and "
        f"{col_b} (M = {float(b.mean()):.2f}, SD = {float(b.std()):.2f}), "
        f"t({df_val}) = {t_stat:.2f}, p {'< .001' if p_val < 0.001 else f'= {p_val:.3f}'}."
    )
    technical = (
        f"t({df_val}) = {t_stat:.4f}, p = {p_val:.4f}, "
        f"MD = {md:.4f}, SD_diff = {float(diff.std()):.4f}, "
        f"95% CI [{md - t_crit * se:.4f}, {md + t_crit * se:.4f}], N = {n}"
    )

    return AnalysisResult(
        test_key="paired_t",
        test_name="Paired t-test",
        n_obs=n,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )
