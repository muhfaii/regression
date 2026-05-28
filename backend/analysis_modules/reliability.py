"""Reliability analysis — Cronbach's alpha with item-total statistics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import AnalysisResult, AssumptionCheck, Interpretation


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    variables: list[str] = config.get("variables", [])
    if len(variables) < 2:
        raise ValueError("At least two scale items are required.")

    valid = df[variables].dropna()
    n_obs = len(valid)
    if n_obs < 3:
        raise ValueError("At least 3 complete observations are required.")

    k = len(variables)
    item_scores = valid[variables].astype(float)
    item_cov = np.cov(item_scores, rowvar=False)
    total_var = np.sum(item_cov)
    trace_var = np.trace(item_cov)

    alpha = (k / (k - 1)) * (1 - trace_var / total_var) if total_var > 0 else 0.0

    corr_mat = item_scores.corr().values
    mean_r = np.mean(corr_mat[np.triu_indices(k, k=1)])
    alpha_std = (k * mean_r) / (1 + (k - 1) * mean_r) if mean_r > 0 else 0.0

    item_stats = []
    for i, var in enumerate(variables):
        others = variables[:i] + variables[i + 1:]
        item_score = item_scores[var]
        others_total = item_scores[others].sum(axis=1)

        corr = item_score.corr(others_total)

        cov_i = np.cov(item_scores[others].T, rowvar=False) if len(others) > 1 else np.array([[np.var(item_scores[others[0]])]])
        total_no_i = np.sum(cov_i)
        trace_no_i = np.trace(cov_i)
        k_no_i = k - 1
        alpha_deleted = (k_no_i / (k_no_i - 1)) * (1 - trace_no_i / total_no_i) if total_no_i > 0 and k_no_i > 1 else np.nan

        item_stats.append({
            "item": var,
            "corrected_item_total_corr": round(float(corr), 4) if not pd.isna(corr) else 0.0,
            "alpha_if_deleted": round(float(alpha_deleted), 4) if not np.isnan(alpha_deleted) else None,
        })

    inter_item_cov = item_cov[np.triu_indices(k, k=1)]
    inter_item_r = corr_mat[np.triu_indices(k, k=1)]

    statistics = {
        "alpha": round(float(alpha), 4),
        "alpha_standardized": round(float(alpha_std), 4),
        "n_items": k,
        "n_obs": n_obs,
        "item_statistics": item_stats,
        "inter_item_corr_mean": round(float(np.mean(inter_item_r)), 4),
        "inter_item_corr_min": round(float(np.min(inter_item_r)), 4),
        "inter_item_corr_max": round(float(np.max(inter_item_r)), 4),
        "inter_item_cov_mean": round(float(np.mean(inter_item_cov)), 4),
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        negative_corr = [s["item"] for s in item_stats if s["corrected_item_total_corr"] < 0]
        if negative_corr:
            checks.append(AssumptionCheck(
                name="Item-total correlations",
                status="amber",
                detail=f"{', '.join(negative_corr)} have negative item-total correlations.",
                fix_suggestion="Consider reverse-coding these items before re-running reliability analysis.",
            ))
        near_zero = [s["item"] for s in item_stats if abs(s["corrected_item_total_corr"]) < 0.1]
        if near_zero:
            checks.append(AssumptionCheck(
                name="Weak item discrimination",
                status="amber",
                detail=f"{', '.join(near_zero)} have near-zero item-total correlations.",
                fix_suggestion="These items may not belong to the same construct; consider removal.",
            ))
        if alpha < 0.5:
            checks.append(AssumptionCheck(
                name="Overall reliability",
                status="fail",
                detail=f"Cronbach's alpha = {alpha:.3f} is below the acceptable threshold of 0.70.",
                fix_suggestion="Review item content; consider removing items with low item-total correlations.",
            ))

    labels = {0.7: "acceptable", 0.8: "good", 0.9: "excellent"}
    qual = next((v for thresh, v in sorted(labels.items()) if alpha >= thresh), "poor")
    var_list = ", ".join(variables)

    plain = (
        f"Cronbach's alpha for the {k}-item scale was {alpha:.2f}, indicating {qual} "
        f"internal consistency (N = {n_obs})."
    )
    apa = (
        f"Internal consistency was assessed using Cronbach's alpha "
        f"(α = {alpha:.3f}, k = {k}, N = {n_obs}), "
        f"indicating {qual} reliability."
    )
    technical = (
        f"Cronbach's α = {alpha:.4f}, standardized α = {alpha_std:.4f}, "
        f"k = {k}, N = {n_obs}, mean inter-item r = {mean_r:.4f}, variables = {var_list}"
    )

    return AnalysisResult(
        test_key="reliability",
        test_name="Reliability Analysis",
        n_obs=n_obs,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
    )
