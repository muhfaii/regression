"""Factor analysis — EFA with KMO, Bartlett's, extraction, and rotation."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import chi2 as chi2_dist

from .base import AnalysisResult, AssumptionCheck, Interpretation


def _manual_kmo(data: pd.DataFrame):
    corr = data.corr().values
    inv_corr = np.linalg.inv(corr)
    diag_inv = np.diag(inv_corr)
    kmo_num = np.sum(corr ** 2, axis=1) - np.diag(corr) ** 2
    kmo_denom = kmo_num + (np.diag(1 / diag_inv) - 1) ** 2
    kmo_per_item = kmo_num / kmo_denom
    kmo_total = np.sum(kmo_num) / np.sum(kmo_denom)
    return kmo_per_item, kmo_total


def _manual_bartlett(data: pd.DataFrame):
    n = len(data)
    k = data.shape[1]
    corr = data.corr().values
    det = np.linalg.det(corr)
    chi2 = -((n - 1) - (2 * k + 5) / 6) * np.log(det)
    df = k * (k - 1) // 2
    p = 1 - chi2_dist.cdf(chi2, df)
    return chi2, p


def _varimax(loadings: np.ndarray, max_iter: int = 1000, tol: float = 1e-6):
    n_rows, n_cols = loadings.shape
    rotmat = np.eye(n_cols)
    for _ in range(max_iter):
        rotated = loadings @ rotmat
        squared = rotated ** 2
        u = squared - np.mean(squared, axis=0)
        _, s, vh = np.linalg.svd(rotated.T @ (2 * u * rotated) / n_rows)
        new_rot = vh.T @ vh
        change = np.sum(np.abs(rotmat - new_rot))
        rotmat = new_rot
        if change < tol:
            break
    return loadings @ rotmat, rotmat


def _oblimin(loadings: np.ndarray, gamma: float = 0, max_iter: int = 1000):
    n_rows, n_cols = loadings.shape
    rotmat = np.eye(n_cols)
    for _ in range(max_iter):
        rotated = loadings @ rotmat
        squared = rotated ** 2
        u = squared - gamma * np.mean(squared, axis=0, keepdims=True) - (1 - gamma) * np.eye(n_rows, n_cols) @ squared
        _, s, vh = np.linalg.svd(rotated.T @ (2 * u * rotated) / n_rows)
        new_rot = vh.T @ vh
        rotmat = new_rot
    return loadings @ rotmat, rotmat


def _apply_rotation(loadings: np.ndarray, rotation: str):
    if rotation == "varimax":
        return _varimax(loadings)[0]
    elif rotation == "oblimin":
        return _oblimin(loadings)[0]
    elif rotation == "promax":
        varimax_loaded, rotmat = _varimax(loadings)
        squared = varimax_loaded ** 2
        target = squared / (np.sum(squared, axis=1, keepdims=True) + 1e-10)
        promax_rot = np.linalg.lstsq(varimax_loaded, target, rcond=None)[0]
        promax_rot = promax_rot / np.linalg.norm(promax_rot, axis=0)
        return varimax_loaded @ np.linalg.inv(varimax_loaded.T @ varimax_loaded) @ varimax_loaded.T @ target
    return loadings


def _make_loadings_table(loadings: np.ndarray, variables: list[str], threshold: float = 0.3):
    rows = []
    for i, var in enumerate(variables):
        row = {"variable": var}
        for f in range(loadings.shape[1]):
            val = round(float(loadings[i, f]), 4)
            row[f"factor_{f + 1}"] = val
            row[f"factor_{f + 1}_sig"] = abs(val) >= threshold
        rows.append(row)
    return rows


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    variables: list[str] = config.get("variables", [])
    if len(variables) < 3:
        raise ValueError("At least three variables are required for factor analysis.")

    valid = df[variables].dropna()
    n_obs = len(valid)
    if n_obs < 5:
        raise ValueError("At least 5 complete observations are required.")

    extras = getattr(options, "extras", {}) or {}
    n_factors = extras.get("n_factors", 0)
    rotation = extras.get("rotation", "varimax")
    method = extras.get("method", "principal_factor")

    data = valid[variables].astype(float)
    k = len(variables)

    # ---- KMO & Bartlett's ----
    try:
        from factor_analyzer import calculate_kmo, calculate_bartlett_sphericity
        kmo_per_item, kmo_total = calculate_kmo(data)
        bartlett_chi2, bartlett_p = calculate_bartlett_sphericity(data)
    except ImportError:
        kmo_per_item, kmo_total = _manual_kmo(data)
        bartlett_chi2, bartlett_p = _manual_bartlett(data)

    kmo_per_item_list = [round(float(v), 4) for v in kmo_per_item]
    kmo_total = round(float(kmo_total), 4)
    bartlett_chi2 = round(float(bartlett_chi2), 4)
    bartlett_p = round(float(bartlett_p), 4)

    # ---- Eigenvalues (scree) ----
    corr = data.corr().values
    eigvals_all = sorted(np.linalg.eigvalsh(corr), reverse=True)
    scree = [{"component": i + 1, "eigenvalue": round(float(v), 4)} for i, v in enumerate(eigvals_all)]

    if n_factors == 0:
        n_factors = max(1, int(np.sum(np.array(eigvals_all) > 1.0)))
        n_factors = min(n_factors, k - 1)

    # ---- Factor extraction ----
    if method == "pca" and rotation != "none":
        eigvals_arr = np.array(eigvals_all)
        eigvecs = np.linalg.eigh(corr)[1][:, ::-1]
        loadings = eigvecs[:, :n_factors] * np.sqrt(eigvals_arr[:n_factors])
        variance_pct = eigvals_arr[:n_factors] / k * 100
        cumulative_var = np.cumsum(variance_pct).tolist()
        communalities = np.sum(eigvecs[:, :n_factors] ** 2 * eigvals_arr[:n_factors], axis=1)
        loadings = _apply_rotation(loadings, rotation)
        uniquenesses = 1 - communalities
        variance_pct = variance_pct.tolist()
    else:
        fa_method = "principal" if method == "principal_factor" else "ml"
        fa_rotation = rotation if rotation != "none" else None
        from factor_analyzer import FactorAnalyzer
        fa = FactorAnalyzer(rotation=fa_rotation, method=fa_method, n_factors=n_factors)
        fa.fit(data)
        loadings = fa.loadings_
        communalities = np.array(fa.get_communalities())
        uniquenesses = np.array(fa.get_uniquenesses())
        var_data = fa.get_factor_variance()
        variance_pct = [round(float(v) * 100, 4) for v in var_data[1]]
        cumulative_var = [round(float(v) * 100, 4) for v in var_data[2]]

    loadings_table = _make_loadings_table(loadings, variables)

    kmo_per_item_dict = {variables[i]: kmo_per_item_list[i] for i in range(k)}

    statistics = {
        "n_variables": k,
        "n_obs": n_obs,
        "n_factors": n_factors,
        "kmo_total": kmo_total,
        "kmo_per_item": kmo_per_item_dict,
        "bartlett_chi2": bartlett_chi2,
        "bartlett_p": bartlett_p,
        "scree": scree,
        "loadings": loadings_table,
        "variance_explained_pct": variance_pct,
        "cumulative_variance_pct": cumulative_var,
        "communalities": [round(float(v), 4) for v in communalities],
        "uniquenesses": [round(float(v), 4) for v in uniquenesses],
        "rotation": rotation,
        "method": method,
    }

    # ---- Assumption checks ----
    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        if kmo_total < 0.5:
            checks.append(AssumptionCheck(
                name="Sampling adequacy (KMO)",
                status="fail",
                detail=f"Overall KMO = {kmo_total:.3f} is below 0.50.",
                fix_suggestion="Consider collecting more data or removing variables with low KMO.",
            ))
        elif kmo_total < 0.7:
            checks.append(AssumptionCheck(
                name="Sampling adequacy (KMO)",
                status="amber",
                detail=f"Overall KMO = {kmo_total:.3f} is mediocre (below 0.70).",
                fix_suggestion="Consider removing variables with low individual KMO values.",
            ))
        low_kmo_vars = [v for v, kmo in kmo_per_item_dict.items() if kmo < 0.5]
        if low_kmo_vars:
            checks.append(AssumptionCheck(
                name="Individual KMO",
                status="amber",
                detail=f"{', '.join(low_kmo_vars)} have KMO below 0.50.",
                fix_suggestion="Consider removing these variables or collecting more data.",
            ))
        if bartlett_p >= 0.05:
            checks.append(AssumptionCheck(
                name="Bartlett's test of sphericity",
                status="fail",
                detail=f"Bartlett's χ² = {bartlett_chi2:.2f}, p = {bartlett_p:.4f} (p ≥ 0.05).",
                fix_suggestion="The correlation matrix may not be suitable for factor analysis.",
            ))
        cross_loaded = []
        for row in loadings_table:
            sig_factors = [k for k, v in row.items() if k.endswith("_sig") and v]
            if len(sig_factors) >= 2:
                cross_loaded.append(row["variable"])
        if cross_loaded:
            checks.append(AssumptionCheck(
                name="Cross-loadings",
                status="amber",
                detail=f"{', '.join(cross_loaded)} load on multiple factors (≥{0.3}).",
                fix_suggestion="Consider removing these items or reassigning to a single factor.",
            ))

    # ---- Interpretation ----
    factor_labels = ", ".join(f"Factor {i+1} ({variance_pct[i]:.1f}%)" for i in range(n_factors))
    plain = (
        f"A factor analysis with {n_factors} factor{'s' if n_factors != 1 else ''} was conducted "
        f"on {k} items (N = {n_obs}, KMO = {kmo_total:.2f}, "
        f"Bartlett's χ² = {bartlett_chi2:.2f}, p = {bartlett_p:.3f}). "
        f"The {rotation} rotation explained {cumulative_var[-1]:.1f}% of the total variance "
        f"({factor_labels})."
    )
    apa = (
        f"An exploratory factor analysis (EFA) with {rotation} rotation "
        f"was performed on {k} items (N = {n_obs}). "
        f"The Kaiser-Meyer-Olkin measure verified sampling adequacy (KMO = {kmo_total:.3f}), "
        f"and Bartlett's test of sphericity was "
        f"{'significant' if bartlett_p < 0.05 else 'not significant'}, "
        f"χ²({k * (k - 1) // 2}) = {bartlett_chi2:.2f}, p = {bartlett_p:.3f}. "
        f"A {n_factors}-factor solution was extracted ({method} method) "
        f"accounting for {cumulative_var[-1]:.1f}% of the variance."
    )
    technical = (
        f"EFA — k = {k}, N = {n_obs}, KMO = {kmo_total:.4f}, "
        f"Bartlett χ² = {bartlett_chi2:.2f}, df = {k * (k - 1) // 2}, p = {bartlett_p:.4f}, "
        f"factors = {n_factors}, method = {method}, rotation = {rotation}, "
        f"variance explained = {cumulative_var[-1]:.2f}%"
    )

    return AnalysisResult(
        test_key="factor_analysis",
        test_name="Factor Analysis (EFA)",
        n_obs=n_obs,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
    )
