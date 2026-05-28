"""Mediation analysis via Baron & Kenny, Sobel test, and bootstrap CI.

Config: outcome, predictor, mediator, covariates (optional)
Fits: X->M (a), X->Y (c), X+M->Y (c', b)
Reports: path coefficients, Sobel test, bootstrap CI, proportion mediated.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.stats as scipy_stats
import statsmodels.api as sm

from .base import AnalysisResult, EffectSize, Interpretation


def run(df: pd.DataFrame, config: dict, options=None) -> AnalysisResult:
    outcome = config.get("outcome")
    predictor = config.get("predictor")
    mediator = config.get("mediator")
    covariates = config.get("covariates", [])

    if not outcome:
        raise ValueError("outcome is required.")
    if not predictor:
        raise ValueError("predictor is required.")
    if not mediator:
        raise ValueError("mediator is required.")

    required = [outcome, predictor, mediator] + list(covariates)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Columns not found: {missing}")

    df_clean = df[required].dropna().copy()
    n = len(df_clean)
    if n < 10:
        raise ValueError(f"Too few valid observations ({n}); need at least 10.")

    _assert_numeric(df_clean, [predictor, mediator, outcome])

    y = df_clean[outcome].values.astype(float)
    x = df_clean[predictor].values.astype(float)
    m = df_clean[mediator].values.astype(float)

    # Covariates: build expanded matrix
    cov_matrix = _build_covariate_matrix(df_clean, covariates)

    # ── Model 1: X → M (path a) ──────────────────────────────────────────────
    X_a = _build_X_matrix(predictor, x, cov_matrix)
    model_a = sm.OLS(m, X_a).fit(cov_type="HC3")
    a_coef = float(model_a.params[predictor])
    a_se = float(model_a.bse[predictor])
    a_t = float(model_a.tvalues[predictor])
    a_p = float(model_a.pvalues[predictor])

    # ── Model 2: X → Y (path c — total effect) ──────────────────────────────
    X_c = _build_X_matrix(predictor, x, cov_matrix)
    model_c = sm.OLS(y, X_c).fit(cov_type="HC3")
    c_coef = float(model_c.params[predictor])
    c_se = float(model_c.bse[predictor])
    c_t = float(model_c.tvalues[predictor])
    c_p = float(model_c.pvalues[predictor])

    # ── Model 3: X + M → Y (paths c' and b) ──────────────────────────────────
    X_b = _build_X_matrix([predictor, mediator], np.column_stack([x, m]), cov_matrix)
    model_b = sm.OLS(y, X_b).fit(cov_type="HC3")
    # b path (mediator → outcome, controlling for X)
    b_coef = float(model_b.params[mediator])
    b_se = float(model_b.bse[mediator])
    b_t = float(model_b.tvalues[mediator])
    b_p = float(model_b.pvalues[mediator])
    # c' path (direct effect of X on Y controlling for M)
    cp_coef = float(model_b.params[predictor])
    cp_se = float(model_b.bse[predictor])
    cp_t = float(model_b.tvalues[predictor])
    cp_p = float(model_b.pvalues[predictor])

    # ── Indirect effect (a × b) ───────────────────────────────────────────────
    indirect = a_coef * b_coef

    # Sobel test
    sobel_z = indirect / np.sqrt(b_coef**2 * a_se**2 + a_coef**2 * b_se**2) if (b_coef**2 * a_se**2 + a_coef**2 * b_se**2) > 0 else 0.0
    sobel_p = 2.0 * (1.0 - scipy_stats.norm.cdf(abs(sobel_z)))

    # ── Bootstrap CI for indirect effect ──────────────────────────────────────
    n_boot = 5000
    rng = np.random.default_rng(2024)
    boot_indirects = np.empty(n_boot)
    arr = df_clean.values
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boot = arr[idx]

        boot_cols = required
        boot_df = pd.DataFrame(boot, columns=boot_cols)
        boot_y = boot_df[outcome].values.astype(float)
        boot_x = boot_df[predictor].values.astype(float)
        boot_m = boot_df[mediator].values.astype(float)
        boot_cov = _build_covariate_matrix(boot_df, covariates)

        X_a_boot = _build_X_matrix(predictor, boot_x, boot_cov)
        X_b_boot = _build_X_matrix([predictor, mediator], np.column_stack([boot_x, boot_m]), boot_cov)
        ba = float(sm.OLS(boot_m, X_a_boot).fit().params[predictor])
        bb = float(sm.OLS(boot_y, X_b_boot).fit().params[mediator])
        boot_indirects[i] = ba * bb

    boot_ci_low = float(np.percentile(boot_indirects, 2.5))
    boot_ci_high = float(np.percentile(boot_indirects, 97.5))

    # ── Proportion mediated ───────────────────────────────────────────────────
    proportion_mediated = indirect / c_coef if abs(c_coef) > 1e-12 else float("inf")

    # ── Mediation type (bootstrap CI as primary test) ─────────────────────────
    ci_excludes_zero = boot_ci_low > 0 or boot_ci_high < 0
    if not ci_excludes_zero:
        mediation_type = "none"
    elif cp_p >= 0.05:
        mediation_type = "full"
    else:
        mediation_type = "partial"

    # ── Coefficient tables for all models ─────────────────────────────────────
    def _coef_table(model) -> dict:
        ci = model.conf_int()
        tbl = {}
        for name in model.params.index:
            display = "(Intercept)" if name == "const" else name
            tbl[display] = {
                "coef": _r4(float(model.params[name])),
                "se": _r4(float(model.bse[name])),
                "t": _r4(float(model.tvalues[name])),
                "p": _r4(float(model.pvalues[name])),
                "ci_low": _r4(float(ci.loc[name, 0])),
                "ci_high": _r4(float(ci.loc[name, 1])),
            }
        return tbl

    stats = {
        "n_obs": int(model_c.nobs),
        "path_a": {"coef": _r4(a_coef), "se": _r4(a_se), "t": _r4(a_t), "p": _r4(a_p)},
        "path_b": {"coef": _r4(b_coef), "se": _r4(b_se), "t": _r4(b_t), "p": _r4(b_p)},
        "path_c": {"coef": _r4(c_coef), "se": _r4(c_se), "t": _r4(c_t), "p": _r4(c_p)},
        "path_c_prime": {"coef": _r4(cp_coef), "se": _r4(cp_se), "t": _r4(cp_t), "p": _r4(cp_p)},
        "indirect_effect": _r4(indirect),
        "sobel_z": _r4(sobel_z),
        "sobel_p": _r4(sobel_p),
        "bootstrap_ci_low": _r4(boot_ci_low),
        "bootstrap_ci_high": _r4(boot_ci_high),
        "proportion_mediated": _r4(proportion_mediated),
        "mediation_type": mediation_type,
        "r_squared_x_m": _r4(float(model_a.rsquared)),
        "r_squared_x_y": _r4(float(model_c.rsquared)),
        "r_squared_xm_y": _r4(float(model_b.rsquared)),
        "coefficients_x_m": _coef_table(model_a),
        "coefficients_x_y": _coef_table(model_c),
        "coefficients_xm_y": _coef_table(model_b),
        "predictor": predictor,
        "mediator": mediator,
        "outcome": outcome,
        "covariates": list(covariates),
    }

    effect = EffectSize(
        name="Indirect effect (a × b)",
        value=_r4(indirect),
        interpretation=_prop_interp(proportion_mediated),
    )

    return AnalysisResult(
        test_key="mediation",
        test_name="Mediation Analysis",
        n_obs=int(model_c.nobs),
        statistics=stats,
        assumption_checks=[],
        interpretation=_build_interpretation(outcome, predictor, mediator, stats),
        effect_size=effect,
        warnings=[],
    )


def _build_X_matrix(
    names: str | list[str], values: np.ndarray, cov_arrays: list[np.ndarray]
) -> pd.DataFrame:
    if isinstance(names, str):
        names = [names]
        values = values.reshape(-1, 1)
    elif values.ndim == 1:
        values = values.reshape(-1, 1)
    data = {"const": np.ones(values.shape[0])}
    for i, name in enumerate(names):
        data[name] = values[:, i]
    for j, arr in enumerate(cov_arrays):
        data[f"_cov_{j}"] = arr
    return pd.DataFrame(data)


def _build_covariate_matrix(df: pd.DataFrame, covariates: list[str]) -> list[np.ndarray]:
    cols = []
    for c in covariates:
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(df[c].values.astype(float))
        else:
            dummies = pd.get_dummies(df[c], prefix=c, drop_first=True)
            for col in dummies.columns:
                cols.append(dummies[col].values.astype(float))
    return cols


def _r4(v: float) -> float:
    return round(float(v), 4)


def _prop_interp(prop: float) -> str:
    prop = abs(prop)
    if prop < 0.01:
        return "negligible"
    if prop < 0.2:
        return "small"
    if prop < 0.5:
        return "medium"
    return "large"


def _assert_numeric(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if not pd.api.types.is_numeric_dtype(df[c]):
            raise ValueError(
                f"'{c}' must be numeric for mediation analysis, got {df[c].dtype}."
            )


def _build_interpretation(
    outcome: str, predictor: str, mediator: str, stats: dict
) -> Interpretation:
    a = stats["path_a"]
    b = stats["path_b"]
    c = stats["path_c"]
    cp = stats["path_c_prime"]
    indirect = stats["indirect_effect"]
    sobel_p = stats["sobel_p"]
    prop = stats["proportion_mediated"]
    mtype = stats["mediation_type"]
    boot_low = stats["bootstrap_ci_low"]
    boot_high = stats["bootstrap_ci_high"]
    r2_xm = stats["r_squared_xm_y"]

    path_a_str = f"a = {a['coef']}, p = {a['p']:.4f}"
    path_b_str = f"b = {b['coef']}, p = {b['p']:.4f}"
    path_c_str = f"c = {c['coef']}, p = {c['p']:.4f}"
    path_cp_str = f"c' = {cp['coef']}, p = {cp['p']:.4f}"

    if mtype == "full":
        mediation_desc = (
            f"Full mediation: {mediator} fully mediates the relationship between "
            f"{predictor} and {outcome}. After controlling for {mediator}, "
            f"the direct effect of {predictor} on {outcome} is no longer significant "
            f"(c' = {cp['coef']}, p = {cp['p']:.4f})."
        )
    elif mtype == "partial":
        mediation_desc = (
            f"Partial mediation: {mediator} partially mediates the relationship. "
            f"The direct effect of {predictor} on {outcome} remains significant "
            f"after accounting for {mediator} (c' = {cp['coef']}, p = {cp['p']:.4f}), "
            f"but a significant indirect pathway exists."
        )
    else:
        mediation_desc = (
            f"No mediation detected: the indirect pathway through {mediator} "
            f"was not significant (indirect = {indirect}, "
            f"95% bootstrap CI [{boot_low}, {boot_high}])."
        )

    plain = (
        f"A mediation analysis tested whether {mediator} mediates the effect of "
        f"{predictor} on {outcome}. "
        f"The total effect of {predictor} on {outcome} was {path_c_str} (path c). "
        f"The effect of {predictor} on {mediator} was {path_a_str} (path a), "
        f"and the effect of {mediator} on {outcome} controlling for {predictor} "
        f"was {path_b_str} (path b). "
        f"The direct effect of {predictor} on {outcome} after controlling for "
        f"{mediator} was {path_cp_str} (path c'). "
        f"The indirect effect was {indirect} "
        f"(Sobel z = {stats['sobel_z']}, p = {sobel_p:.4f}; "
        f"95% bootstrap CI [{boot_low}, {boot_high}]). "
        f"The model explains {r2_xm * 100:.1f}% of the variance in {outcome}. "
        f"{mediation_desc}"
    )

    apa = (
        f"A mediation analysis (Baron & Kenny, 1986) was conducted to examine "
        f"whether {mediator} mediates the relationship between {predictor} and "
        f"{outcome}. The total effect of {predictor} on {outcome} was significant "
        f"(b = {c['coef']:.3f}, p = {c['p']:.3f}). "
        f"The effect of {predictor} on {mediator} was "
        f"(b = {a['coef']:.3f}, p = {a['p']:.3f}), "
        f"and the effect of {mediator} on {outcome} controlling for {predictor} was "
        f"(b = {b['coef']:.3f}, p = {b['p']:.3f}). "
        f"The direct effect of {predictor} on {outcome} after controlling for "
        f"{mediator} was (b = {cp['coef']:.3f}, p = {cp['p']:.3f}). "
        f"The indirect effect was estimated as {indirect:.3f} "
        f"(Sobel z = {stats['sobel_z']:.3f}, p = {sobel_p:.3f}; "
        f"95% bootstrap CI [{boot_low:.3f}, {boot_high:.3f}]), "
        f"indicating {mtype} mediation. "
        f"R² = {r2_xm:.3f}, N = {stats['n_obs']}."
    )

    technical = (
        f"Mediation: {outcome} ~ {predictor} + {mediator}"
        + (f" + {' + '.join(stats['covariates'])}" if stats["covariates"] else "")
        + f" | Path a = {a['coef']:.4f} (p = {a['p']:.4f}), "
        f"Path b = {b['coef']:.4f} (p = {b['p']:.4f}), "
        f"Path c = {c['coef']:.4f} (p = {c['p']:.4f}), "
        f"Path c' = {cp['coef']:.4f} (p = {cp['p']:.4f}) | "
        f"Indirect = {indirect:.4f}, Sobel z = {stats['sobel_z']:.4f}, "
        f"p = {sobel_p:.4f} | "
        f"Bootstrap 95% CI [{boot_low:.4f}, {boot_high:.4f}] | "
        f"Proportion mediated = {prop:.4f} | "
        f"Mediation type: {mtype} | "
        f"R² = {r2_xm:.4f}, N = {stats['n_obs']}"
    )

    return Interpretation(plain=plain, apa=apa, technical=technical)
