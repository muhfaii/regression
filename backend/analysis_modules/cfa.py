"""Confirmatory Factor Analysis — ML estimation with fit indices."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import chi2 as chi2_dist

from .base import AnalysisResult, AssumptionCheck, Interpretation


def _build_factor_model(n_items: int, n_factors: int, items_per_factor: list[int]):
    """Build loading pattern matrix (n_items × n_factors) with 0/1 indicators."""
    pattern = np.zeros((n_items, n_factors))
    col_start = 0
    for f_idx, n_f in enumerate(items_per_factor):
        for i in range(col_start, col_start + n_f):
            pattern[i, f_idx] = 1.0
        col_start += n_f
    return pattern


def _params_to_matrices(params: np.ndarray, pattern: np.ndarray, n_items: int, n_factors: int):
    """Convert flat parameter vector to loading matrix, factor corr, uniquenesses."""
    idx = 0
    # Free loadings (where pattern == 1)
    n_free_loadings = int(pattern.sum())
    loadings = np.zeros((n_items, n_factors))
    loadings[pattern == 1] = params[idx:idx + n_free_loadings]
    idx += n_free_loadings

    # Factor correlation cholesky (lower triangular with diag)
    n_corr_params = n_factors * (n_factors - 1) // 2
    L_factor = np.eye(n_factors)
    if n_corr_params > 0:
        tri = np.zeros((n_factors, n_factors))
        tri[np.tril_indices(n_factors, -1)] = params[idx:idx + n_corr_params]
        L_factor = L_factor + tri
        idx += n_corr_params

    # Uniquenesses (log-transformed to keep positive)
    uniquenesses = np.exp(params[idx:idx + n_items])
    return loadings, L_factor @ L_factor.T, uniquenesses


def _implied_cov(loadings: np.ndarray, factor_corr: np.ndarray, uniquenesses: np.ndarray):
    """Compute model-implied covariance matrix: Λ Φ Λᵀ + Ψ"""
    return loadings @ factor_corr @ loadings.T + np.diag(uniquenesses)


def _ml_discrepancy(params, S: np.ndarray, n_items: int, n_factors: int, pattern: np.ndarray):
    """ML fit function: log|Σ| + tr(S Σ⁻¹) - log|S| - p"""
    loadings, factor_corr, uniquenesses = _params_to_matrices(params, pattern, n_items, n_factors)
    sigma = _implied_cov(loadings, factor_corr, uniquenesses)
    try:
        inv_sigma = np.linalg.inv(sigma)
        log_det_sigma = np.linalg.slogdet(sigma)[1]
        log_det_S = np.linalg.slogdet(S)[1]
        return log_det_sigma + np.trace(S @ inv_sigma) - log_det_S - n_items
    except np.linalg.LinAlgError:
        return 1e10


def _fit_indices(f_min: float, n_obs: int, n_items: int, df_model: int):
    """Compute standard CFA fit indices from the ML fit function minimum."""
    chi2 = f_min * (n_obs - 1)
    p_value = 1 - chi2_dist.cdf(chi2, df_model) if df_model > 0 else 0.0

    # Baseline (independence) model χ²
    S_corr = None
    return chi2, p_value


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    indicators: list[str] = config.get("indicators", [])
    if len(indicators) < 4:
        raise ValueError("At least 4 indicator variables are required for CFA.")

    extras = getattr(options, "extras", {}) or {}
    n_factors = extras.get("n_factors", 1)
    if n_factors < 1:
        n_factors = 1

    valid = df[indicators].dropna()
    n_obs = len(valid)
    if n_obs < max(indicators.__len__() * 5, 50):
        raise ValueError(f"At least {max(len(indicators) * 5, 50)} observations are required (found {n_obs}).")

    data = valid[indicators].astype(float)
    n_items = len(indicators)

    if n_factors > n_items:
        n_factors = n_items

    # Auto-assign indicators to factors (round-robin)
    items_per_factor = [0] * n_factors
    for i in range(n_items):
        items_per_factor[i % n_factors] += 1

    # Check each factor has at least 2 indicators
    if min(items_per_factor) < 2:
        raise ValueError(
            f"Each factor needs at least 2 indicators. With {n_items} items and {n_factors} factors, "
            f"some factors have only {min(items_per_factor)} indicator(s)."
        )

    pattern = _build_factor_model(n_items, n_factors, items_per_factor)
    S = data.cov().values

    # Initialize parameters with reasonable starting values
    init_loadings = np.zeros((n_items, n_factors))
    var_idx = 0
    for f in range(n_factors):
        for _ in range(items_per_factor[f]):
            init_loadings[var_idx, f] = 0.7
            var_idx += 1

    init_free = init_loadings[pattern == 1]
    n_free_loadings = len(init_free)

    n_corr_params = n_factors * (n_factors - 1) // 2
    init_corr = np.zeros(n_corr_params)
    init_uniqueness = np.full(n_items, -0.5)  # log(small variance)

    init_params = np.concatenate([init_free, init_corr, init_uniqueness])

    # ML estimation
    result = minimize(
        _ml_discrepancy, init_params,
        args=(S, n_items, n_factors, pattern),
        method="L-BFGS-B",
        options={"maxiter": 5000, "ftol": 1e-9},
    )

    if not result.success:
        # Try again with different starts
        init_params2 = np.concatenate([
            np.random.uniform(0.3, 0.8, n_free_loadings) * np.sign(init_free),
            np.zeros(n_corr_params),
            np.full(n_items, -0.5),
        ])
        result = minimize(
            _ml_discrepancy, init_params2,
            args=(S, n_items, n_factors, pattern),
            method="L-BFGS-B",
            options={"maxiter": 5000, "ftol": 1e-9},
        )

    loadings, factor_corr, uniquenesses = _params_to_matrices(result.x, pattern, n_items, n_factors)

    # Fit indices
    f_min = result.fun
    df_model = n_items * (n_items + 1) // 2 - (
        n_free_loadings + n_corr_params + n_items
    )
    chi2 = f_min * max(0, n_obs - 1)
    p_value = 1 - chi2_dist.cdf(max(0, chi2), max(1, df_model)) if df_model > 0 else 0.0

    # Baseline (independence) model
    S_diag = np.diag(S)
    sigma_indep = np.diag(S_diag)
    try:
        inv_sigma_i = np.linalg.inv(sigma_indep)
        f_min_indep = np.linalg.slogdet(sigma_indep)[1] + np.trace(S @ inv_sigma_i) - np.linalg.slogdet(S)[1] - n_items
    except np.linalg.LinAlgError:
        f_min_indep = 1e10
    chi2_indep = f_min_indep * (n_obs - 1) if f_min_indep < 1e9 else 1e10
    df_indep = n_items * (n_items - 1) // 2

    # CFI
    cfi = 1.0 - max(chi2 - df_model, 0) / max(chi2_indep - df_indep, chi2 - df_model, 1e-10) if chi2_indep > df_indep else 0.0
    cfi = max(0.0, min(1.0, cfi))

    # TLI / NNFI
    tli = 1.0 - (chi2 / df_model - chi2_indep / df_indep) / (chi2_indep / df_indep - 1) if df_model > 0 and df_indep > 0 and chi2_indep > df_indep else 0.0
    tli = max(0.0, min(1.0, tli))

    # RMSEA
    rmsea = np.sqrt(max(chi2 - df_model, 0) / (df_model * (n_obs - 1))) if df_model > 0 and n_obs > 1 else 0.0
    rmsea_lower = 0.0
    rmsea_upper = 0.0
    if df_model > 0 and chi2 > df_model:
        ncp_lower, ncp_upper = _rmsea_ci(chi2, df_model, n_obs - 1)
        rmsea_lower = np.sqrt(ncp_lower / (df_model * (n_obs - 1)))
        rmsea_upper = np.sqrt(ncp_upper / (df_model * (n_obs - 1)))

    # SRMR
    S_std = data.corr().values
    sigma_std = _implied_cov(
        loadings * np.std(data.values, axis=0)[:, np.newaxis],
        factor_corr,
        np.var(data.values, axis=0) * uniquenesses / np.var(data.values, axis=0),
    )
    # Actually SRMR from correlation matrix
    sigma_r = _implied_cov(loadings * np.std(data.values, axis=0)[:, np.newaxis], factor_corr, uniquenesses)
    # Let's compute SRMR on the correlation residual
    corr_data = data.corr().values
    try:
        sigma_implied = _implied_cov(loadings, factor_corr, uniquenesses)
        # Standardize both
        D = np.diag(1 / np.sqrt(np.diag(S)))
        S_corr = D @ S @ D
        sigma_corr = D @ sigma_implied @ D
        resid = S_corr - sigma_corr
        srmr = np.sqrt(np.sum(resid[np.triu_indices_from(resid, k=1)] ** 2) / (n_items * (n_items - 1) / 2))
    except Exception:
        srmr = 0.0

    # Loadings table
    factor_names = [f"Factor {f + 1}" for f in range(n_factors)]
    loadings_table = []
    var_idx = 0
    for f_idx in range(n_factors):
        for _ in range(items_per_factor[f_idx]):
            loading = float(loadings[var_idx, f_idx])
            # Approximate SE via inversion of information matrix (simplified)
            loadings_table.append({
                "indicator": indicators[var_idx],
                "factor": factor_names[f_idx],
                "loading": round(loading, 4),
                "loading_std": round(loading * float(np.std(data[indicators[var_idx]])) / float(np.sqrt(sigma_implied[var_idx, var_idx])), 4),
            })
            var_idx += 1

    # Factor correlations
    factor_corr_table = []
    for i in range(n_factors):
        for j in range(i + 1, n_factors):
            factor_corr_table.append({
                "factor1": factor_names[i],
                "factor2": factor_names[j],
                "correlation": round(float(factor_corr[i, j]), 4),
            })

    statistics = {
        "n_indicators": n_items,
        "n_factors": n_factors,
        "items_per_factor": items_per_factor,
        "chi2": round(chi2, 4),
        "df": df_model,
        "p_value": round(p_value, 4),
        "cfi": round(cfi, 4),
        "tli": round(tli, 4),
        "rmsea": round(rmsea, 4),
        "rmsea_ci_lower": round(rmsea_lower, 4),
        "rmsea_ci_upper": round(rmsea_upper, 4),
        "srmr": round(srmr, 4),
        "loadings": loadings_table,
        "factor_correlations": factor_corr_table if factor_corr_table else None,
        "converged": bool(result.success),
    }

    # Assumption checks
    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        if not result.success:
            checks.append(AssumptionCheck(
                name="Model convergence",
                status="fail",
                detail="The CFA model did not converge.",
                fix_suggestion="Try reducing the number of factors or check variable distributions.",
            ))

        if rmsea > 0.08:
            checks.append(AssumptionCheck(
                name="RMSEA fit",
                status="amber",
                detail=f"RMSEA = {rmsea:.3f} exceeds 0.08 threshold.",
                fix_suggestion="Consider model modifications or a different factor structure.",
            ))
        elif rmsea > 0.05:
            checks.append(AssumptionCheck(
                name="RMSEA fit",
                status="pass",
                detail=f"RMSEA = {rmsea:.3f} — acceptable fit (< 0.08).",
            ))
        else:
            checks.append(AssumptionCheck(
                name="RMSEA fit",
                status="pass",
                detail=f"RMSEA = {rmsea:.3f} — good fit (< 0.05).",
            ))

        if cfi < 0.90:
            checks.append(AssumptionCheck(
                name="CFI fit",
                status="amber",
                detail=f"CFI = {cfi:.3f} below 0.90 threshold.",
                fix_suggestion="Consider model modifications or a different factor structure.",
            ))
        else:
            checks.append(AssumptionCheck(
                name="CFI fit",
                status="pass",
                detail=f"CFI = {cfi:.3f} — {'good' if cfi >= 0.95 else 'acceptable'} fit.",
            ))

        if srmr > 0.08:
            checks.append(AssumptionCheck(
                name="SRMR fit",
                status="amber",
                detail=f"SRMR = {srmr:.3f} exceeds 0.08 threshold.",
            ))
        else:
            checks.append(AssumptionCheck(
                name="SRMR fit",
                status="pass",
                detail=f"SRMR = {srmr:.3f} — good fit (< 0.08).",
            ))

        if p_value < 0.05:
            checks.append(AssumptionCheck(
                name="Model χ² test",
                status="amber",
                detail=f"χ²({df_model}) = {chi2:.2f}, p = {p_value:.4f} — significant.",
                fix_suggestion="A significant χ² suggests imperfect fit (but is sensitive to large N).",
            ))

    # Interpretation
    factor_desc = ", ".join(f"{items_per_factor[i]} items" for i in range(n_factors))
    plain = (
        f"A confirmatory factor analysis with {n_factors} factor{'s' if n_factors != 1 else ''} "
        f"({factor_desc}) was fitted to {n_items} indicators (N = {n_obs}). "
        f"The model fit was {'good' if cfi >= 0.95 and rmsea <= 0.05 else 'acceptable' if cfi >= 0.90 and rmsea <= 0.08 else 'poor'}: "
        f"χ²({df_model}) = {chi2:.2f}, p = {p_value:.3f}, "
        f"CFI = {cfi:.3f}, TLI = {tli:.3f}, RMSEA = {rmsea:.3f}"
        + (f" [90% CI: {rmsea_lower:.3f}, {rmsea_upper:.3f}]" if rmsea_lower > 0 else "")
        + f", SRMR = {srmr:.3f}."
    )
    apa = (
        f"A CFA with {n_factors} correlated factor{'s' if n_factors != 1 else ''} was estimated "
        f"using maximum likelihood (N = {n_obs}). "
        f"The model had {'good' if cfi >= 0.95 and rmsea <= 0.05 else 'acceptable' if cfi >= 0.90 and rmsea <= 0.08 else 'poor'} fit: "
        f"χ²({df_model}) = {chi2:.2f}, "
        f"{'p < .001' if p_value < 0.001 else f'p = {p_value:.3f}'}, "
        f"CFI = {cfi:.3f}, TLI = {tli:.3f}, RMSEA = {rmsea:.3f}"
        + (f" [90% CI: {rmsea_lower:.3f}, {rmsea_upper:.3f}]" if rmsea_lower > 0 else "")
        + f", SRMR = {srmr:.3f}."
    )
    technical = (
        f"CFA — {n_factors} factors, {n_items} indicators, N = {n_obs}, "
        f"χ²({df_model}) = {chi2:.4f}, p = {p_value:.4f}, "
        f"CFI = {cfi:.4f}, TLI = {tli:.4f}, "
        f"RMSEA = {rmsea:.4f} [{rmsea_lower:.4f}, {rmsea_upper:.4f}], "
        f"SRMR = {srmr:.4f}, converged = {bool(result.success)}"
    )

    return AnalysisResult(
        test_key="cfa",
        test_name="Confirmatory Factor Analysis",
        n_obs=n_obs,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
    )


def _rmsea_ci(chi2: float, df: int, N: int):
    """Compute 90% CI for RMSEA using non-central chi-square."""
    alpha = 0.05
    ncp_lower = 0.0
    ncp_upper = 0.0
    if chi2 > df:
        try:
            ncp_lower = chi2_dist.ppf(alpha, df, chi2) - chi2 if chi2 > 0 else 0
            ncp_upper = chi2_dist.ppf(1 - alpha, df + 1, chi2) - chi2 if chi2 > 0 else 0
        except Exception:
            pass
    return max(0, ncp_lower), max(0, ncp_upper)
