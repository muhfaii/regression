"""Survival analysis — Kaplan-Meier, log-rank, and Cox PH model."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import AnalysisResult, AssumptionCheck, Interpretation


def _median_with_ci(survival_fn, ci_):
    """Extract median survival time with confidence bounds from KM fit."""
    below_05 = survival_fn <= 0.5
    if not below_05.any():
        return None, None, None
    idx = below_05.idxmax()
    median = float(idx.iloc[0]) if hasattr(idx, 'iloc') else float(idx)
    lower = float(ci_[ci_.columns[0]].loc[ci_.index <= median].iloc[-1]) if len(ci_) else None
    upper = float(ci_[ci_.columns[1]].loc[ci_.index <= median].iloc[-1]) if len(ci_) else None
    return median, lower, upper


def _survival_curve_data(survival_fn, ci_):
    """Convert KM fit to chart-friendly format."""
    times = survival_fn.index.tolist()
    surv = survival_fn[survival_fn.columns[0]].tolist()
    ci_lower = ci_[ci_.columns[0]].tolist() if ci_ is not None else None
    ci_upper = ci_[ci_.columns[1]].tolist() if ci_ is not None else None
    return {
        "times": times,
        "survival": surv,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
    }


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    duration_col = config.get("duration")
    event_col = config.get("event")
    predictors = config.get("predictors", [])
    group_col = config.get("group")

    if not duration_col or not event_col:
        raise ValueError("Both 'duration' and 'event' columns are required.")

    cols = [duration_col, event_col] + predictors
    if group_col:
        cols.append(group_col)

    valid = df[cols].dropna()
    n_obs = len(valid)
    if n_obs < 5:
        raise ValueError("At least 5 observations are required.")

    duration = valid[duration_col].astype(float)
    event = valid[event_col].astype(int)

    if event.nunique() < 2:
        raise ValueError("Event indicator must contain both 0 and 1 values.")
    n_events = int(event.sum())
    if n_events < 2:
        raise ValueError("At least 2 events are required for survival analysis.")

    # ---- Kaplan-Meier ----
    from lifelines import KaplanMeierFitter
    from lifelines.statistics import logrank_test

    kmf = KaplanMeierFitter()
    kmf.fit(duration, event_observed=event)
    km_median = float(kmf.median_survival_time_) if not np.isnan(kmf.median_survival_time_) else None
    km_survival = _survival_curve_data(kmf.survival_function_, kmf.confidence_interval_)

    # ---- Log-rank test (if group specified) ----
    logrank_stat = None
    logrank_p = None
    group_names = None
    if group_col:
        groups = valid[group_col]
        unique_groups = groups.unique()
        group_names = list(unique_groups)
        if len(unique_groups) >= 2:
            gm1 = groups == unique_groups[0]
            gm2 = groups == unique_groups[1]
            lr = logrank_test(duration[gm1], duration[gm2], event_observed_A=event[gm1], event_observed_B=event[gm2])
            logrank_stat = round(float(lr.test_statistic), 4)
            logrank_p = round(float(lr.p_value), 4)

    # ---- Cox PH ----
    from lifelines import CoxPHFitter

    cox_results = None
    cox_converged = True
    cox_warnings = []
    if predictors:
        cox_df = valid[[duration_col, event_col] + predictors]
        cph = CoxPHFitter()
        try:
            cph.fit(cox_df, duration_col=duration_col, event_col=event_col)
            cox_summary = cph.summary
            hr_rows = []
            for pred in predictors:
                if pred in cox_summary.index:
                    row = cox_summary.loc[pred]
                    hr_rows.append({
                        "predictor": pred,
                        "coef": round(float(row["coef"]), 4),
                        "hr": round(float(np.exp(row["coef"])), 4),
                        "se": round(float(row["se(coef)"]), 4),
                        "z": round(float(row["z"]), 4),
                        "p": round(float(row["p"]), 4),
                        "ci_lower": round(float(np.exp(row["coef"] - 1.96 * row["se(coef)"])), 4),
                        "ci_upper": round(float(np.exp(row["coef"] + 1.96 * row["se(coef)"])), 4),
                    })
                else:
                    hr_rows.append({"predictor": pred, "hr": None, "p": None})
            concordance = round(float(cph.concordance_index_), 4)
            cox_results = {
                "n_predictors": len(predictors),
                "hr_table": hr_rows,
                "concordance": concordance,
                "log_likelihood": round(float(cph.log_likelihood_), 4),
            }
            if hasattr(cph, '_converged'):
                cox_converged = cph._converged
        except Exception as e:
            cox_warnings.append(str(e))
            cox_converged = False

    # ---- Assumption checks ----
    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        if n_obs < 30:
            checks.append(AssumptionCheck(
                name="Sample size",
                status="amber",
                detail=f"Total N = {n_obs} is below the recommended 30 observations.",
                fix_suggestion="Survival estimates may be unreliable with small samples.",
            ))
        event_rate = n_events / n_obs
        if event_rate < 0.1:
            checks.append(AssumptionCheck(
                name="Event rate",
                status="amber",
                detail=f"Event rate = {event_rate:.1%} ({n_events}/{n_obs} events).",
                fix_suggestion="Low event rates can reduce statistical power for Cox models.",
            ))
        if logrank_p is not None and logrank_p >= 0.05:
            checks.append(AssumptionCheck(
                name="Log-rank test",
                status="amber",
                detail=f"Log-rank test p = {logrank_p:.4f} — no significant difference between groups.",
                fix_suggestion="The groups may not have different survival distributions.",
            ))

    # ---- Interpretation ----
    median_str = f"{km_median:.1f}" if km_median else "not reached"
    plain = (
        f"A Kaplan-Meier survival analysis was conducted (N = {n_obs}, {n_events} events). "
        f"Median survival time: {median_str}."
    )
    if logrank_p is not None:
        lr_sig = "significant" if logrank_p < 0.05 else "not significant"
        plain += f" The log-rank test was {lr_sig} (p = {logrank_p:.3f})."
    if cox_results:
        sig_preds = [r["predictor"] for r in cox_results["hr_table"] if r.get("p") is not None and r["p"] < 0.05]
        if sig_preds:
            plain += f" Significant predictors: {', '.join(sig_preds)}."

    apa = (
        f"Survival analysis (N = {n_obs}, {n_events} events) revealed a "
        f"median survival time of {median_str}."
    )
    if logrank_p is not None:
        apa += (
            f" A log-rank test {'' if logrank_p < 0.05 else 'did not '}show "
            f"a significant difference between groups, "
            f"χ²(1) = {logrank_stat:.2f}, p = {logrank_p:.3f}."
        )

    technical = (
        f"Survival — KM median = {median_str}, N = {n_obs}, events = {n_events}, "
        f"event rate = {event_rate:.2f}"
    )
    if logrank_stat is not None:
        technical += f", log-rank χ² = {logrank_stat:.4f}, p = {logrank_p:.4f}"
    if cox_results:
        hr_desc = "; ".join(f"{r['predictor']}: HR = {r['hr']:.4f}" for r in cox_results["hr_table"] if r.get("hr"))
        technical += f", Cox concordance = {cox_results['concordance']:.4f}, HRs: {hr_desc}"

    statistics: dict = {
        "n_obs": n_obs,
        "n_events": n_events,
        "event_rate": round(float(event_rate), 4),
        "km_median": km_median,
        "km_survival_curve": km_survival,
    }
    if logrank_stat is not None:
        statistics["logrank_statistic"] = logrank_stat
        statistics["logrank_p"] = logrank_p
        statistics["group_names"] = group_names
    if cox_results:
        statistics["cox"] = cox_results
        statistics["cox_converged"] = cox_converged
    if cox_warnings:
        statistics["cox_warnings"] = cox_warnings

    return AnalysisResult(
        test_key="survival_analysis",
        test_name="Survival Analysis",
        n_obs=n_obs,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        warnings=cox_warnings,
    )
