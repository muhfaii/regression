"""Moderation/interaction effects analysis.

Fits: outcome ~ centered_predictor * centered_moderator + covariates
Reports: coefficient table, simple slopes, Johnson-Neyman region, floodlight data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as scipy_stats

from .base import AnalysisResult, EffectSize, Interpretation


def run(df: pd.DataFrame, config: dict, options=None) -> AnalysisResult:
    outcome = config.get("outcome")
    predictor = config.get("predictor")
    moderator = config.get("moderator")
    covariates = config.get("covariates", [])

    if not outcome:
        raise ValueError("outcome is required.")
    if not predictor:
        raise ValueError("predictor is required.")
    if not moderator:
        raise ValueError("moderator is required.")

    required = [outcome, predictor, moderator] + list(covariates)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Columns not found: {missing}")

    df_clean = df[required].dropna().copy()
    n = len(df_clean)
    if n < 10:
        raise ValueError(f"Too few valid observations ({n}); need at least 10.")

    y = df_clean[outcome].values
    _assert_numeric(df_clean, [predictor, moderator])

    p_vals = df_clean[predictor].values.astype(float)
    m_vals = df_clean[moderator].values.astype(float)
    p_mean = float(p_vals.mean())
    m_mean = float(m_vals.mean())
    p_sd = float(p_vals.std(ddof=1))
    m_sd = float(m_vals.std(ddof=1))

    p_centered = p_vals - p_mean
    m_centered = m_vals - m_mean
    interaction = p_centered * m_centered

    interaction_name = f"{predictor}:{moderator}"

    data = {"const": np.ones(n)}
    data[predictor] = p_centered
    data[moderator] = m_centered
    data[interaction_name] = interaction

    # Handle covariates — expand non-numeric to dummies
    if covariates:
        cov_df = df_clean[list(covariates)]
        numeric_covs = [c for c in covariates if pd.api.types.is_numeric_dtype(cov_df[c])]
        categ_covs = [c for c in covariates if not pd.api.types.is_numeric_dtype(cov_df[c])]
        for c in numeric_covs:
            data[c] = cov_df[c].values.astype(float)
        if categ_covs:
            dummies = pd.get_dummies(cov_df[categ_covs], prefix=categ_covs, drop_first=True)
            for col in dummies.columns:
                data[col] = dummies[col].values.astype(float)

    X_full = pd.DataFrame(data)
    model = sm.OLS(y, X_full).fit(cov_type="HC3")

    # Reduced model (no interaction) for f²
    data_r = {k: v for k, v in data.items() if k != interaction_name}
    X_reduced = pd.DataFrame(data_r)
    model_reduced = sm.OLS(y, X_reduced).fit(cov_type="HC3")

    r2_full = float(model.rsquared)
    r2_reduced = float(model_reduced.rsquared)
    interaction_f2 = (r2_full - r2_reduced) / (1.0 - r2_full) if r2_full < 1.0 else float("inf")

    # Coefficient table — read from model.params.index to get actual names
    ci = model.conf_int()
    coef_table = {}
    for var in model.params.index:
        if var == "const":
            continue
        coef_table[var] = {
            "coef": _r4(model.params[var]),
            "se": _r4(model.bse[var]),
            "t": _r4(model.tvalues[var]),
            "p": _r4(model.pvalues[var]),
            "ci_low": _r4(ci.loc[var, 0]),
            "ci_high": _r4(ci.loc[var, 1]),
        }

    # Simple slopes
    b1 = model.params[predictor]
    b3 = model.params[interaction_name]
    cov_mat = model.cov_params()
    var_b1 = cov_mat.loc[predictor, predictor]
    var_b3 = cov_mat.loc[interaction_name, interaction_name]
    cov_b1b3 = cov_mat.loc[predictor, interaction_name]

    def _simple_slope(m_val: float) -> dict:
        slope = float(b1 + b3 * m_val)
        se = float(np.sqrt(var_b1 + 2 * m_val * cov_b1b3 + m_val**2 * var_b3))
        t_val = slope / se if se > 0 else 0.0
        p_val = 2.0 * (1.0 - scipy_stats.t.cdf(abs(t_val), model.df_resid))
        half_ci = float(scipy_stats.t.ppf(0.975, model.df_resid) * se)
        return {
            "slope": _r4(slope),
            "se": _r4(se),
            "t": _r4(t_val),
            "p": _r4(p_val),
            "ci_low": _r4(slope - half_ci),
            "ci_high": _r4(slope + half_ci),
        }

    simple_slopes = {
        "mean_minus_1sd": {"moderator_value": _r4(m_mean - m_sd), **_simple_slope(m_mean - m_sd)},
        "mean": {"moderator_value": _r4(m_mean), **_simple_slope(m_mean)},
        "mean_plus_1sd": {"moderator_value": _r4(m_mean + m_sd), **_simple_slope(m_mean + m_sd)},
    }

    # Johnson-Neyman significance region
    t_crit = float(scipy_stats.t.ppf(0.975, model.df_resid))
    A = b3**2 - t_crit**2 * var_b3
    B = 2.0 * b1 * b3 - 2.0 * t_crit**2 * cov_b1b3
    C = b1**2 - t_crit**2 * var_b1
    disc = B**2 - 4.0 * A * C
    m_min = float(m_vals.min())
    m_max = float(m_vals.max())

    jn_region = {"has_region": False, "lower_bound": None, "upper_bound": None}
    if disc >= 0 and abs(A) > 1e-12:
        r1 = (-B - np.sqrt(disc)) / (2.0 * A)
        r2 = (-B + np.sqrt(disc)) / (2.0 * A)
        roots = sorted([r1, r2])
        in_range = [r for r in roots if m_min <= r <= m_max]
        if len(in_range) == 1:
            r = in_range[0]
            lb = _r4(r) if r > m_min else None
            ub = _r4(r) if r < m_max else None
            jn_region = {"has_region": True, "lower_bound": lb, "upper_bound": ub}
        elif len(in_range) == 2:
            jn_region = {
                "has_region": True,
                "lower_bound": _r4(in_range[0]),
                "upper_bound": _r4(in_range[1]),
            }

    # Floodlight plot data
    m_grid = np.linspace(m_min, m_max, 100)
    floodlight = []
    for mv in m_grid:
        ss = _simple_slope(float(mv))
        floodlight.append({
            "moderator_value": _r4(mv),
            "slope": ss["slope"],
            "ci_low": ss["ci_low"],
            "ci_high": ss["ci_high"],
            "significant": abs(ss["t"]) > _r4(t_crit),
        })

    stats = {
        "r_squared": _r4(r2_full),
        "adj_r_squared": _r4(float(model.rsquared_adj)),
        "f_statistic": _r4(float(model.fvalue)),
        "f_pvalue": _r4(float(model.f_pvalue)),
        "n_obs": int(model.nobs),
        "coefficients": coef_table,
        "intercept": _r4(float(model.params["const"])),
        "simple_slopes": simple_slopes,
        "jn_region": jn_region,
        "floodlight": floodlight,
        "interaction_f2": _r4(interaction_f2),
        "predictor": predictor,
        "moderator": moderator,
        "outcome": outcome,
        "covariates": list(covariates),
    }

    interp = _build_interpretation(outcome, predictor, moderator, stats)
    effect = EffectSize(
        name="Cohen's f² (interaction)",
        value=_r4(interaction_f2),
        interpretation=_f2_interp(interaction_f2),
    )

    return AnalysisResult(
        test_key="moderation",
        test_name="Moderation Analysis",
        n_obs=int(model.nobs),
        statistics=stats,
        assumption_checks=[],
        interpretation=interp,
        effect_size=effect,
        warnings=[],
    )


def _r4(v: float) -> float:
    return round(float(v), 4)


def _assert_numeric(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if not pd.api.types.is_numeric_dtype(df[c]):
            raise ValueError(
                f"'{c}' must be numeric for moderation analysis, got {df[c].dtype}."
            )


def _f2_interp(f2: float) -> str:
    if f2 < 0.02:
        return "negligible"
    if f2 < 0.15:
        return "small"
    if f2 < 0.35:
        return "medium"
    return "large"


def _build_interpretation(
    outcome: str, predictor: str, moderator: str, stats: dict
) -> Interpretation:
    coef_table = stats["coefficients"]
    interaction_name = f"{predictor}:{moderator}"
    int_coef = coef_table.get(interaction_name, {})
    b3 = int_coef.get("coef", 0.0)
    p_int = int_coef.get("p", 1.0)
    sig = p_int < 0.05
    r2 = stats["r_squared"]
    f_p = stats["f_pvalue"]
    ss = stats["simple_slopes"]

    if sig:
        direction = "amplifies" if b3 > 0 else "dampens"
        # Simple slope narrative
        slope_parts = []
        for label, key in [("low", "mean_minus_1sd"), ("moderate", "mean"), ("high", "mean_plus_1sd")]:
            s = ss.get(key, {})
            if s.get("p", 1.0) < 0.05:
                slope_parts.append(
                    f"{label} (b = {s['slope']}, p = {s['p']:.3f})"
                )

        slope_note = ""
        if slope_parts:
            slope_note = (
                " The simple slope of "
                f"{predictor} on {outcome} was significant at "
                f"{', '.join(slope_parts)} levels of {moderator}."
            )

        plain = (
            f"A moderation analysis shows that {moderator} {direction} "
            f"the relationship between {predictor} and {outcome} "
            f"(interaction b = {b3}, p = {p_int:.3f}). "
            f"The model explains {r2 * 100:.1f}% of the variance in {outcome}."
            f"{slope_note}"
        )

        apa = (
            f"A moderation analysis was conducted with {predictor} as the focal predictor "
            f"and {moderator} as the moderator. The interaction term was significant "
            f"(b = {b3:.3f}, p = {p_int:.3f}), indicating that {moderator} {direction} "
            f"the effect of {predictor} on {outcome}, "
            f"R² = {r2:.3f}, F({stats.get('n_obs', 0)}), p {'< .001' if f_p < 0.001 else f'= {f_p:.3f}'}."
            f"{slope_note}"
        )
    else:
        plain = (
            f"A moderation analysis found no significant interaction between "
            f"{predictor} and {moderator} in predicting {outcome} "
            f"(b = {b3}, p = {p_int:.3f}). The effect of {predictor} on {outcome} "
            f"does not appear to depend on {moderator}."
        )

        apa = (
            f"A moderation analysis revealed no significant interaction between "
            f"{predictor} and {moderator} in predicting {outcome} "
            f"(b = {b3:.3f}, p = {p_int:.3f}), "
            f"R² = {r2:.3f}, p {'< .001' if f_p < 0.001 else f'= {f_p:.3f}.'}"
        )

    technical = (
        f"Model: {outcome} ~ {predictor} * {moderator}"
        + (f" + {' + '.join(stats['covariates'])}" if stats["covariates"] else "")
        + f" | R² = {r2:.4f}, Adj. R² = {stats['adj_r_squared']:.4f}, "
        f"F = {stats['f_statistic']:.4f}, p = {f_p:.4f}, N = {stats['n_obs']} | "
        f"Interaction: b = {b3:.4f}, p = {p_int:.4f}, f² = {stats['interaction_f2']:.4f}"
    )

    return Interpretation(plain=plain, apa=apa, technical=technical)
