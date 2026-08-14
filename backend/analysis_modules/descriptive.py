"""Descriptive statistics module."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .base import AnalysisResult, Interpretation


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    variables: list[str] = config.get("variables", [])
    if not variables:
        raise ValueError("At least one variable is required.")

    col_stats: dict = {}
    for var in variables:
        s = df[var].dropna()
        if s.empty:
            raise ValueError(f"Column '{var}' has no non-missing values.")
        n = int(len(s))
        mean = float(s.mean())
        sd = float(s.std())
        se = sd / np.sqrt(n)
        t_crit = float(stats.t.ppf(0.975, n - 1)) if n > 1 else 0.0
        col_stats[var] = {
            "n": n,
            "mean": round(mean, 4),
            "median": round(float(s.median()), 4),
            "sd": round(sd, 4),
            "se": round(se, 4),
            "ci_lower": round(mean - t_crit * se, 4),
            "ci_upper": round(mean + t_crit * se, 4),
            "min": round(float(s.min()), 4),
            "max": round(float(s.max()), 4),
            "q1": round(float(s.quantile(0.25)), 4),
            "q3": round(float(s.quantile(0.75)), 4),
            "iqr": round(float(s.quantile(0.75) - s.quantile(0.25)), 4),
            "skewness": round(float(stats.skew(s)), 4),
            "kurtosis": round(float(stats.kurtosis(s)), 4),
        }

    n_total = sum(v["n"] for v in col_stats.values())
    interp = _build_interpretation(variables, col_stats)

    return AnalysisResult(
        test_key="descriptive",
        test_name="Descriptive Statistics",
        n_obs=n_total,
        statistics={"variables": col_stats},
        assumption_checks=[],
        interpretation=interp,
    )


def _build_interpretation(variables: list[str], col_stats: dict) -> Interpretation:
    if len(variables) == 1:
        var = variables[0]
        s = col_stats[var]
        plain = (
            f"{var} had a mean of {s['mean']:.2f} (SD = {s['sd']:.2f}, "
            f"median = {s['median']:.2f}, range = {s['min']:.2f}–{s['max']:.2f}, N = {s['n']})."
        )
        apa = f"{var} (M = {s['mean']:.2f}, SD = {s['sd']:.2f}, N = {s['n']})."
        technical = (
            f"{var}: N={s['n']}, M={s['mean']:.4f}, SD={s['sd']:.4f}, Mdn={s['median']:.4f}, "
            f"min={s['min']:.4f}, max={s['max']:.4f}, skew={s['skewness']:.4f}, kurtosis={s['kurtosis']:.4f}"
        )
        return Interpretation(plain=plain, apa=apa, technical=technical)

    parts_plain = [f"{v} (M = {col_stats[v]['mean']:.2f}, SD = {col_stats[v]['sd']:.2f})" for v in variables]
    parts_apa = [f"{v} (M = {col_stats[v]['mean']:.2f}, SD = {col_stats[v]['sd']:.2f})" for v in variables]
    plain = "Summary statistics: " + "; ".join(parts_plain) + "."
    apa = "Descriptive statistics were computed for " + ", ".join(parts_apa) + "."
    technical = "; ".join(
        f"{v}: N={col_stats[v]['n']}, M={col_stats[v]['mean']:.4f}, SD={col_stats[v]['sd']:.4f}"
        for v in variables
    )
    return Interpretation(plain=plain, apa=apa, technical=technical)
