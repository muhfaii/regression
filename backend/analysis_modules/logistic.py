"""Logistic regression via statsmodels (binary outcome)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import mannwhitneyu as _mwu

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    outcome = config.get("outcome")
    predictors: list[str] = config.get("predictors", [])
    if not outcome or not predictors:
        raise ValueError("outcome and at least one predictor are required.")

    cols = [outcome] + predictors
    valid = df[cols].dropna()
    n = len(valid)

    # Encode outcome as 0/1
    y_raw = valid[outcome]
    categories = sorted(y_raw.unique())
    if len(categories) != 2:
        raise ValueError(f"Logistic regression requires a binary outcome; found {len(categories)} categories.")
    y = (y_raw == categories[1]).astype(int)
    X_df = valid[predictors].copy()
    X_df["__outcome__"] = y.values

    formula = f"__outcome__ ~ {' + '.join(_safe_col(p) for p in predictors)}"
    model = smf.logit(formula, data=X_df).fit(disp=False)

    # Nagelkerke pseudo-R²
    ll_full = model.llf
    ll_null = model.llnull
    n_obs = int(model.nobs)
    nagelkerke = _nagelkerke_r2(ll_full, ll_null, n_obs)

    # AUC via Mann-Whitney U relationship: AUC = U / (n_pos * n_neg)
    try:
        y_hat = model.predict()
        pos = y_hat[y.values == 1]
        neg = y_hat[y.values == 0]
        u, _ = _mwu(pos, neg, alternative="greater")
        auc = float(u) / (len(pos) * len(neg)) if len(pos) > 0 and len(neg) > 0 else float("nan")
    except Exception:
        auc = float("nan")

    # Coefficient table
    coef_table = {}
    for pred in predictors:
        key = _safe_col(pred)
        if key in model.params.index:
            coef_table[pred] = {
                "coef": round(float(model.params[key]), 4),
                "se": round(float(model.bse[key]), 4),
                "z": round(float(model.tvalues[key]), 4),
                "p": round(float(model.pvalues[key]), 4),
                "or": round(float(np.exp(model.params[key])), 4),
                "ci_low_or": round(float(np.exp(model.conf_int().loc[key, 0])), 4),
                "ci_high_or": round(float(np.exp(model.conf_int().loc[key, 1])), 4),
            }

    statistics = {
        "outcome_categories": [str(c) for c in categories],
        "n": n_obs,
        "log_likelihood": round(float(ll_full), 4),
        "chi2": round(float(model.llr), 4),
        "chi2_p": round(float(model.llr_pvalue), 4),
        "df": int(model.df_model),
        "nagelkerke_r2": round(nagelkerke, 4),
        "auc": round(auc, 4) if not np.isnan(auc) else None,
        "coefficients": coef_table,
    }

    checks: list[AssumptionCheck] = []
    if options.assumption_checks:
        # Check for multicollinearity via VIF
        try:
            from statsmodels.stats.outliers_influence import variance_inflation_factor
            X_num = pd.get_dummies(valid[predictors], drop_first=True).astype(float)
            high_vif = []
            for i, col in enumerate(X_num.columns):
                vif = variance_inflation_factor(X_num.values, i)
                if vif > 10:
                    high_vif.append(f"{col} (VIF={vif:.1f})")
            checks.append(AssumptionCheck(
                name="Multicollinearity (VIF)",
                status="pass" if not high_vif else "amber",
                detail=f"High VIF predictors: {', '.join(high_vif)}" if high_vif else "All VIF values ≤ 10.",
                fix_suggestion="Remove or combine highly correlated predictors." if high_vif else None,
            ))
        except Exception:
            pass
        # Sample size adequacy (rule of thumb: 10 events per predictor)
        events = int(y.sum())
        epp = events / len(predictors) if predictors else float("inf")
        checks.append(AssumptionCheck(
            name="Events per predictor (EPP ≥ 10)",
            status="pass" if epp >= 10 else "amber",
            detail=f"EPP = {epp:.1f} ({events} events, {len(predictors)} predictors).",
            fix_suggestion="Consider reducing predictors or collecting more data." if epp < 10 else None,
        ))

    effect = None
    if options.effect_size:
        effect = EffectSize(
            name="Nagelkerke R²",
            value=round(nagelkerke, 4),
            interpretation=_r2_interp(nagelkerke),
        )

    sig = "statistically significant" if model.llr_pvalue < 0.05 else "not statistically significant"
    plain = (
        f"A logistic regression model predicting {outcome} from {', '.join(predictors)} was "
        f"{sig} (χ²({int(model.df_model)}) = {model.llr:.2f}, p = {model.llr_pvalue:.3f}), "
        f"Nagelkerke R² = {nagelkerke:.3f}."
    )
    apa = (
        f"A logistic regression was performed to assess the effects of {', '.join(predictors)} "
        f"on {outcome} ({categories[0]} vs. {categories[1]}). "
        f"The model was {'statistically significant' if model.llr_pvalue < 0.05 else 'not statistically significant'}, "
        f"χ²({int(model.df_model)}, N = {n_obs}) = {model.llr:.2f}, "
        f"p {'< .001' if model.llr_pvalue < 0.001 else f'= {model.llr_pvalue:.3f}'}, "
        f"Nagelkerke R² = {nagelkerke:.3f}."
    )
    technical = (
        f"χ²({int(model.df_model)}) = {model.llr:.4f}, p = {model.llr_pvalue:.4f}, "
        f"Nagelkerke R² = {nagelkerke:.4f}, AUC = {f'{auc:.4f}' if not np.isnan(auc) else 'N/A'}, "
        f"N = {n_obs}, LL = {ll_full:.4f}"
    )

    return AnalysisResult(
        test_key="logistic_regression",
        test_name="Logistic Regression",
        n_obs=n_obs,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        effect_size=effect,
    )


def _safe_col(name: str) -> str:
    """Wrap column name in Q() if it contains spaces or special chars."""
    if name.replace("_", "").replace(".", "").isalnum():
        return name
    return f'Q("{name}")'


def _nagelkerke_r2(ll_full: float, ll_null: float, n: int) -> float:
    cox_snell = 1 - np.exp((2 / n) * (ll_null - ll_full))
    max_r2 = 1 - np.exp((2 / n) * ll_null)
    return float(cox_snell / max_r2) if max_r2 > 0 else 0.0


def _r2_interp(r2: float) -> str:
    if r2 < 0.1:
        return "negligible"
    if r2 < 0.3:
        return "small"
    if r2 < 0.5:
        return "medium"
    return "large"
