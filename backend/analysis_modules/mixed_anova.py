"""Mixed ANOVA — between + within subjects design with sphericity checks."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import chi2 as chi2_dist

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation
from .anova import _bonferroni_posthoc


def _mauchly(data: pd.DataFrame, within_levels: list, subject_id: str, depvar: str):
    """Compute Mauchly's test of sphericity for within-subject factor."""
    k = len(within_levels)
    if k < 3:
        return None
    pivot = data.pivot_table(index=subject_id, columns=within_levels, values=depvar, aggfunc="first").dropna()
    n = len(pivot)
    if n < k + 1:
        return None
    S = pivot.cov().values
    trace_S = np.trace(S) / k
    denom = np.linalg.det(S) / (trace_S ** k + 1e-15)
    W = denom ** ((n - 1) / 2)
    df = k * (k - 1) / 2 - 1
    if df <= 0:
        return None
    chi2 = -(n - 1 - (2 * k ** 2 + k + 2) / (6 * k)) * np.log(W + 1e-15)
    p = 1 - chi2_dist.cdf(max(0, chi2), max(1, df))

    eps_gg = (trace_S ** 2 * k - np.sum(S ** 2)) / ((k - 1) * (np.trace(S @ S) - (np.sum(S ** 2) / k))) if k > 1 else 1.0
    eps_gg = min(1.0, eps_gg)

    return {
        "W": round(float(W), 4),
        "chi2": round(float(chi2), 4),
        "df": int(df),
        "p_value": round(float(p), 4),
        "eps_gg": round(float(eps_gg), 4),
    }


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    outcome = config.get("outcome")
    within_factor = config.get("within_factor")
    subject_id = config.get("subject_id")
    between_factor = config.get("between_factor")

    if not outcome or not within_factor or not subject_id:
        raise ValueError("outcome, within_factor, and subject_id are required.")

    cols = [outcome, within_factor, subject_id]
    if between_factor:
        cols.append(between_factor)

    valid = df[cols].dropna()
    n_obs = len(valid)
    n_subjects = valid[subject_id].nunique()

    import pingouin as pg

    effects = []
    if between_factor:
        # Mixed design using pingouin
        aov = pg.mixed_anova(dv=outcome, within=within_factor, between=between_factor, subject=subject_id, data=valid)
        for _, row in aov.iterrows():
            effects.append({
                "effect": str(row["Source"]),
                "f_statistic": round(float(row["F"]), 4),
                "df_num": int(row["DF1"]),
                "df_den": int(row["DF2"]),
                "p_value": round(float(row["p_unc"]), 4),
            })
    else:
        # Within-only design using AnovaRM
        from statsmodels.stats.anova import AnovaRM
        anova_rm = AnovaRM(valid, outcome, subject_id, within=[within_factor])
        try:
            fit_result = anova_rm.fit()
        except Exception as e:
            raise ValueError(f"Repeated measures ANOVA failed: {e}")
        anova_table = fit_result.anova_table
        for idx in anova_table.index:
            row = anova_table.loc[idx]
            effects.append({
                "effect": str(idx),
                "f_statistic": round(float(row["F Value"]), 4),
                "df_num": int(row["Num DF"]),
                "df_den": int(row["Den DF"]),
                "p_value": round(float(row["Pr > F"]), 4),
            })

    # Per-cell descriptive stats
    group_cols = [within_factor]
    if between_factor:
        group_cols.insert(0, between_factor)
    desc = valid.groupby(group_cols)[outcome].agg(["mean", "std", "count"]).reset_index()
    cell_stats = []
    for _, row in desc.iterrows():
        entry = {col: str(row[col]) for col in group_cols}
        entry["mean"] = round(float(row["mean"]), 4)
        entry["sd"] = round(float(row["std"]), 4)
        entry["n"] = int(row["count"])
        cell_stats.append(entry)

    # Mauchly's test (only for >2 within levels)
    within_levels = sorted(valid[within_factor].unique())
    mauchly = None
    if len(within_levels) >= 3:
        mauchly = _mauchly(valid, within_levels, subject_id, outcome)

    # Post-hoc for within-subject factor
    post_hoc_within = None
    if options.post_hoc:
        pairs = []
        for i in range(len(within_levels)):
            for j in range(i + 1, len(within_levels)):
                a = valid[valid[within_factor] == within_levels[i]].set_index(subject_id)[outcome]
                b = valid[valid[within_factor] == within_levels[j]].set_index(subject_id)[outcome]
                idx_common = a.index.intersection(b.index)
                if len(idx_common) < 3:
                    continue
                t_stat, p_raw = stats.ttest_rel(a.loc[idx_common], b.loc[idx_common])
                pairs.append({
                    "level1": str(within_levels[i]),
                    "level2": str(within_levels[j]),
                    "mean_diff": round(float(a.loc[idx_common].mean() - b.loc[idx_common].mean()), 4),
                    "t_stat": round(float(t_stat), 4),
                    "p_raw": round(float(p_raw), 4),
                })
        n_pairs = len(pairs)
        for p in pairs:
            p["p_adj"] = round(min(p["p_raw"] * n_pairs, 1.0), 4)
            p["reject"] = p["p_adj"] < 0.05
            del p["p_raw"]
        if pairs:
            post_hoc_within = pairs

    # Post-hoc for between factor (>2 levels)
    post_hoc_between = None
    if between_factor and options.post_hoc:
        bf_levels = valid[between_factor].unique()
        if len(bf_levels) >= 3:
            ph = _bonferroni_posthoc(valid, outcome, between_factor, bf_levels)
            if ph:
                post_hoc_between = ph

    # Assumption checks
    grand_mean = valid[outcome].mean()
    residuals = valid[outcome] - grand_mean

    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        if mauchly:
            sphericity_ok = mauchly["p_value"] > 0.05
            checks.append(AssumptionCheck(
                name="Sphericity (Mauchly's test)",
                status="pass" if sphericity_ok else "amber",
                detail=f"W = {mauchly['W']:.4f}, χ²({mauchly['df']}) = {mauchly['chi2']:.2f}, p = {mauchly['p_value']:.4f}"
                + (f", GG ε = {mauchly['eps_gg']:.4f}" if not sphericity_ok else ""),
                fix_suggestion="Use Greenhouse-Geisser or Huynh-Feldt correction." if not sphericity_ok else None,
            ))

        if n_obs <= 100:
            sw_s, sw_p = stats.shapiro(residuals)
            checks.append(AssumptionCheck(
                name="Normality of residuals (Shapiro-Wilk)",
                status="pass" if sw_p > 0.05 else "amber",
                detail=f"W = {sw_s:.3f}, p = {sw_p:.3f}",
                fix_suggestion="Consider data transformation or non-parametric approach." if sw_p <= 0.05 else None,
            ))

        if between_factor:
            groups = [valid[valid[between_factor] == g][outcome].values.astype(float) for g in valid[between_factor].unique()]
            if len(groups) >= 2:
                lev_s, lev_p = stats.levene(*groups)
                checks.append(AssumptionCheck(
                    name=f"Homogeneity of variances — {between_factor} (Levene's)",
                    status="pass" if lev_p > 0.05 else "amber",
                    detail=f"F = {lev_s:.3f}, p = {lev_p:.3f}",
                    fix_suggestion="Consider data transformation or robust methods." if lev_p <= 0.05 else None,
                ))

    statistics = {
        "effects": effects,
        "n_obs": n_obs,
        "n_subjects": n_subjects,
        "cell_stats": cell_stats,
        "within_levels": [str(l) for l in within_levels],
        "has_between": bool(between_factor),
    }
    if mauchly:
        statistics["mauchly"] = mauchly
    if between_factor:
        statistics["between_factor"] = between_factor
        statistics["between_levels"] = [str(l) for l in sorted(valid[between_factor].unique())]
    if post_hoc_within:
        statistics["post_hoc_within"] = post_hoc_within
    if post_hoc_between:
        statistics["post_hoc_between"] = post_hoc_between

    # Effect size: partial eta-squared from largest effect
    max_effect = max(effects, key=lambda e: e["f_statistic"]) if effects else None
    partial_eta_sq = None
    if max_effect:
        f = max_effect["f_statistic"]
        df_effect = max_effect["df_num"]
        df_error = max_effect["df_den"]
        partial_eta_sq = (f * df_effect) / (f * df_effect + df_error) if (f * df_effect + df_error) > 0 else 0.0

    effect = None
    if options.effect_size and partial_eta_sq is not None:
        interp = "small" if partial_eta_sq < 0.01 else ("medium" if partial_eta_sq < 0.06 else ("large" if partial_eta_sq < 0.14 else "very large"))
        effect = EffectSize(
            name="partial η² (max)",
            value=round(partial_eta_sq, 4),
            interpretation=interp,
        )

    # Interpretation
    sig_effects = [e for e in effects if e["p_value"] < 0.05]
    n_sig = len(sig_effects)
    n_total = len(effects)

    parts = [f"A mixed ANOVA was conducted on {outcome}"]
    if between_factor:
        parts.append(f"with between-subjects factor {between_factor} and within-subjects factor {within_factor}")
    else:
        parts.append(f"with within-subjects factor {within_factor}")
    parts.append(f"(N = {n_subjects} subjects, {n_obs} observations)")
    if n_sig == 0:
        parts.append("No effects were statistically significant.")
    elif n_sig == n_total:
        parts.append(f"All {n_total} effects were statistically significant.")
    else:
        effect_names = ", ".join(e["effect"] for e in sig_effects)
        parts.append(f"{n_sig} of {n_total} effects were statistically significant: {effect_names}.")

    plain = " ".join(parts)

    apa = f"A mixed ANOVA on {outcome} "
    if between_factor:
        apa += f"with {between_factor} as between-subjects factor and {within_factor} as within-subjects factor "
    else:
        apa += f"with {within_factor} as within-subjects factor "
    apa += f"(N = {n_subjects}). "
    for e in effects:
        sig_marker = "p < .001" if e["p_value"] < 0.001 else f"p = {e['p_value']:.3f}"
        apa += f"The effect of {e['effect']} was {'statistically significant' if e['p_value'] < 0.05 else 'not statistically significant'}, F({e['df_num']}, {e['df_den']}) = {e['f_statistic']:.2f}, {sig_marker}. "

    has_mauchly = ""
    if mauchly:
        has_mauchly = f", Mauchly W = {mauchly['W']:.4f}, p = {mauchly['p_value']:.4f}" + (f", ε_GG = {mauchly['eps_gg']:.4f}" if mauchly["p_value"] < 0.05 else "")

    sig_strs = "; ".join(f"{e['effect']}: F({e['df_num']},{e['df_den']})={e['f_statistic']:.4f}, p={e['p_value']:.4f}" for e in effects)
    technical = (
        f"Mixed ANOVA — outcome: {outcome}, within: {within_factor}"
        + (f", between: {between_factor}" if between_factor else "")
        + f", N_subjects = {n_subjects}, N_obs = {n_obs}"
        + has_mauchly
        + (f", partial η² = {partial_eta_sq:.4f}" if partial_eta_sq else "")
        + f" | {sig_strs}"
    )

    return AnalysisResult(
        test_key="mixed_anova",
        test_name="Mixed ANOVA",
        n_obs=n_obs,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )
