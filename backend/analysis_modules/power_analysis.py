"""Power analysis — sample size, power, and effect size computation."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from statsmodels.stats.power import (
    TTestPower,
    TTestIndPower,
    FTestPower,
    NormalIndPower,
)

from .base import AnalysisResult, Interpretation


_FAMILIES = [
    "Independent t-test",
    "Paired t-test",
    "One-sample t-test",
    "ANOVA (F-test)",
    "Correlation (Pearson r)",
]

_COMPUTE_KEYS = {
    "Sample size (N)": "n_total",
    "Power (1-β)": "power",
    "Detectable effect size": "effect_size",
}

_EFFECT_LABELS = {
    "Independent t-test": "Cohen's d",
    "Paired t-test": "Cohen's d",
    "One-sample t-test": "Cohen's d",
    "ANOVA (F-test)": "Cohen's f",
    "Correlation (Pearson r)": "Pearson's r",
}

_PARAM_DISPLAY = {
    "n_total": "Total sample size (N)",
    "power": "Statistical power (1-β)",
    "effect_size": "Effect size",
    "alpha": "Significance level (α)",
}


def _format_power(effect_size: float, n_total: int, alpha: float, test_family: str, n_groups: int = 2) -> float:
    if test_family == "Independent t-test":
        return _power_independent_t(effect_size, n_total, alpha)
    elif test_family in ("Paired t-test", "One-sample t-test"):
        return _power_one_sample(effect_size, n_total, alpha)
    elif test_family == "ANOVA (F-test)":
        return _power_anova(effect_size, n_total, alpha, n_groups)
    elif test_family == "Correlation (Pearson r)":
        return _power_correlation(effect_size, n_total, alpha)
    return 0.0


def _format_n_total(effect_size: float, power: float, alpha: float, test_family: str, n_groups: int = 2) -> int:
    if test_family == "Independent t-test":
        return _n_independent_t(effect_size, power, alpha)
    elif test_family in ("Paired t-test", "One-sample t-test"):
        return _n_paired_one_sample(effect_size, power, alpha)
    elif test_family == "ANOVA (F-test)":
        return _n_anova(effect_size, power, alpha, n_groups)
    elif test_family == "Correlation (Pearson r)":
        return _n_correlation(effect_size, power, alpha)
    return 0


def _format_effect_size(n_total: int, power: float, alpha: float, test_family: str, n_groups: int = 2) -> float:
    if test_family == "Independent t-test":
        return _es_independent_t(n_total, power, alpha)
    elif test_family in ("Paired t-test", "One-sample t-test"):
        return _es_one_sample(n_total, power, alpha)
    elif test_family == "ANOVA (F-test)":
        return _es_anova(n_total, power, alpha, n_groups)
    elif test_family == "Correlation (Pearson r)":
        return _es_correlation(n_total, power, alpha)
    return 0.0


def _power_independent_t(es: float, n: int, alpha: float) -> float:
    n_per = n // 2
    if n_per < 2:
        return 0.0
    return float(TTestIndPower().power(effect_size=es, nobs1=n_per, alpha=alpha, ratio=1.0, alternative="two-sided"))


def _power_one_sample(es: float, n: int, alpha: float) -> float:
    if n < 2:
        return 0.0
    return float(TTestPower().power(effect_size=es, nobs=n, alpha=alpha, alternative="two-sided"))


def _power_anova(es: float, n: int, alpha: float, k: int) -> float:
    n_per = n // k
    if n_per < 2 or k < 2:
        return 0.0
    df_resid = n - k
    df_constr = k - 1
    return float(FTestPower().power(effect_size=es, df_num=df_resid, df_denom=df_constr, alpha=alpha))


def _power_correlation(es: float, n: int, alpha: float) -> float:
    from scipy.stats import norm
    z = np.arctanh(es)
    se = 1.0 / np.sqrt(n - 3) if n > 3 else 0.0
    if se == 0.0:
        return 0.0
    z_alpha = norm.ppf(1 - alpha / 2)
    z_power = (z / se) - z_alpha
    return float(norm.cdf(z_power))


def _n_independent_t(es: float, power: float, alpha: float) -> int:
    n_per = TTestIndPower().solve_power(effect_size=es, power=power, alpha=alpha, ratio=1.0, alternative="two-sided")
    return math.ceil(n_per) * 2


def _n_paired_one_sample(es: float, power: float, alpha: float) -> int:
    n = TTestPower().solve_power(effect_size=es, power=power, alpha=alpha, alternative="two-sided")
    return math.ceil(n)


def _n_anova(es: float, power: float, alpha: float, k: int) -> int:
    lo, hi = k + 3, 10000
    while lo < hi:
        mid = (lo + hi) // 2
        if mid - k < 1:
            lo = mid + 1
            continue
        p = FTestPower().power(effect_size=es, df_num=mid - k, df_denom=k - 1, alpha=alpha)
        if p >= power:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _n_correlation(es: float, power: float, alpha: float) -> int:
    from scipy.stats import norm
    z = np.arctanh(es)
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    n = math.ceil(((z_alpha + z_beta) / z) ** 2 + 3)
    return max(n, 3)


def _es_independent_t(n: int, power: float, alpha: float) -> float:
    n_per = n // 2
    if n_per < 2:
        return 0.0
    return round(float(TTestIndPower().solve_power(effect_size=None, power=power, alpha=alpha, ratio=1.0, alternative="two-sided", nobs1=n_per)), 4)


def _es_one_sample(n: int, power: float, alpha: float) -> float:
    if n < 2:
        return 0.0
    return round(float(TTestPower().solve_power(effect_size=None, power=power, alpha=alpha, alternative="two-sided", nobs=n)), 4)


def _es_anova(n: int, power: float, alpha: float, k: int) -> float:
    n_per = n // k
    if n_per < 2 or k < 2:
        return 0.0
    lo, hi = 0.001, 2.0
    for _ in range(50):
        mid = (lo + hi) / 2
        p = FTestPower().power(effect_size=mid, df_num=n - k, df_denom=k - 1, alpha=alpha)
        if p >= power:
            hi = mid
        else:
            lo = mid
    return round(float(hi), 4)


def _es_correlation(n: int, power: float, alpha: float) -> float:
    from scipy.stats import norm
    if n < 4:
        return 0.0
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    z = (z_alpha + z_beta) / np.sqrt(n - 3)
    return round(float(np.tanh(z)), 4)


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    extras = getattr(options, "extras", {})
    if not isinstance(extras, dict):
        extras = {}

    test_family = extras.get("test_family", "")
    compute = extras.get("compute", "")
    effect_size = extras.get("effect_size")
    alpha = extras.get("alpha", 0.05)
    power = extras.get("power")
    n_total = extras.get("n_total")
    n_groups = extras.get("n_groups", 2)

    if test_family not in _FAMILIES:
        raise ValueError(f"Unknown test family: {test_family!r}. Choose from {list(_FAMILIES)}.")
    if compute not in _COMPUTE_KEYS:
        raise ValueError(f"Unknown compute: {compute!r}. Choose from {list(_COMPUTE_KEYS)}.")

    compute_key = _COMPUTE_KEYS[compute]
    effect_label = _EFFECT_LABELS[test_family]
    n_groups = int(n_groups) if n_groups else 2

    if compute_key == "n_total":
        if effect_size is None:
            raise ValueError("effect_size is required to compute sample size.")
        if power is None:
            raise ValueError("power is required to compute sample size.")
        computed_n = _format_n_total(float(effect_size), float(power), float(alpha), test_family, n_groups)
        computed_power = float(power)
        computed_es = float(effect_size)
    elif compute_key == "power":
        if effect_size is None:
            raise ValueError("effect_size is required to compute power.")
        if n_total is None:
            raise ValueError("n_total is required to compute power.")
        computed_power = _format_power(float(effect_size), int(n_total), float(alpha), test_family, n_groups)
        computed_n = int(n_total)
        computed_es = float(effect_size)
    elif compute_key == "effect_size":
        if n_total is None:
            raise ValueError("n_total is required to compute effect size.")
        if power is None:
            raise ValueError("power is required to compute effect size.")
        computed_es = _format_effect_size(int(n_total), float(power), float(alpha), test_family, n_groups)
        computed_n = int(n_total)
        computed_power = float(power)

    n_per_group = computed_n // n_groups if n_groups > 1 else computed_n

    statistics = {
        "test_family": test_family,
        "compute": compute,
        "effect_size": computed_es,
        "effect_size_label": effect_label,
        "alpha": float(alpha),
        "power": computed_power,
        "n_total": computed_n,
        "n_per_group": n_per_group,
        "n_groups": n_groups,
    }

    param_desc = _PARAM_DISPLAY.get(compute_key, compute_key)
    plain = (
        f"A {compute.lower()} of {param_desc.lower()} was computed for the {test_family.lower()}. "
        f"Results: N = {computed_n}, effect size = {computed_es} ({effect_label}), "
        f"α = {alpha}, power = {computed_power:.3f}."
    )
    apa = (
        f"A priori power analysis ({test_family}) revealed that "
        f"{'a sample of N = ' + str(computed_n) if compute_key == 'n_total' else ''}"
        f"{'the statistical power was ' + f'{computed_power:.3f}' if compute_key == 'power' else ''}"
        f"{'the detectable effect size was ' + str(computed_es) if compute_key == 'effect_size' else ''}"
        f" (α = {alpha}, "
        f"{'power = ' + f'{computed_power:.3f}' if compute_key != 'power' else ''}"
        f"{'N = ' + str(computed_n) if compute_key != 'n_total' else ''})."
    )
    technical = (
        f"Power analysis — test: {test_family}, {compute_key}: {computed_n if compute_key == 'n_total' else computed_power if compute_key == 'power' else computed_es}, "
        f"effect size: {computed_es}, α: {alpha}, power: {computed_power:.4f}, N: {computed_n}"
    )

    return AnalysisResult(
        test_key="power_analysis",
        test_name="Power Analysis",
        n_obs=computed_n,
        statistics=statistics,
        assumption_checks=[],
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
    )
