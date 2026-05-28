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
    var_list = ", ".join(variables)

    plain = f"Descriptive statistics computed for: {var_list}."
    apa = f"Descriptive statistics were computed for the following variable(s): {var_list}."
    technical = f"N = {n_total}, variables = {var_list}"

    return AnalysisResult(
        test_key="descriptive",
        test_name="Descriptive Statistics",
        n_obs=n_total,
        statistics={"variables": col_stats},
        assumption_checks=[],
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
    )
