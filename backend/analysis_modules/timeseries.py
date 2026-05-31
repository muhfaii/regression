"""Time-series analysis — stationarity tests, ACF/PACF, ARIMA modelling, and forecast."""
from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import acf, adfuller, kpss, pacf

from .base import AnalysisResult, AssumptionCheck, Interpretation

_MAX_AUTO_LAGS = 40
_MIN_OBS = 10
_MIN_ARIMA_OBS = 20


def _auto_arima_order(y: pd.Series, seasonal: bool = False, s: int = 12) -> dict[str, Any]:
    best_aic = np.inf
    best_order = (0, 0, 0)
    best_seasonal_order: tuple | None = None
    best_bic = np.inf

    for d in range(0, 3):
        for p in range(0, 4):
            for q in range(0, 4):
                if p == 0 and d == 0 and q == 0:
                    continue
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        arima_kwargs = dict(order=(p, d, q))
                        if seasonal:
                            arima_kwargs["seasonal_order"] = (1, 0, 1, s)
                        model = ARIMA(y, **arima_kwargs)
                        fitted = model.fit(method_kwargs={"disp": False})
                    if fitted.aic < best_aic:
                        best_aic = fitted.aic
                        best_bic = fitted.bic
                        best_order = (p, d, q)
                        best_seasonal_order = (1, 0, 1, s) if seasonal else None
                except Exception:
                    continue

    return {
        "order": list(best_order),
        "seasonal_order": list(best_seasonal_order) if best_seasonal_order else None,
        "aic": best_aic if np.isfinite(best_aic) else None,
        "bic": best_bic if np.isfinite(best_bic) else None,
    }


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    value_col = config.get("value")
    time_col = config.get("time_col")
    if not value_col or not time_col:
        raise ValueError("value and time_col are required.")

    extras = getattr(options, "extras", {})
    if not isinstance(extras, dict):
        extras = {}
    do_assumptions = getattr(options, "assumption_checks", True)

    order_type = extras.get("order", "Auto (AIC)")
    manual_p = int(extras.get("p", 1))
    manual_d = int(extras.get("d", 0))
    manual_q = int(extras.get("q", 0))
    seasonal = bool(extras.get("seasonal", False))
    manual_P = int(extras.get("P", 1))
    manual_D = int(extras.get("D", 0))
    manual_Q = int(extras.get("Q", 1))
    s = int(extras.get("s", 12))
    forecast_steps = int(extras.get("forecast_steps", 12))

    ts = df[[time_col, value_col]].copy()
    ts = ts.sort_values(time_col)
    try:
        ts[time_col] = pd.to_datetime(ts[time_col])
    except (ValueError, TypeError):
        ts = ts.reset_index(drop=True)

    y = pd.to_numeric(ts[value_col], errors="coerce").dropna()
    n_obs = len(y)
    if n_obs < _MIN_OBS:
        raise ValueError(f"At least {_MIN_OBS} complete observations are required.")

    statistics: dict[str, Any] = {"n_obs": n_obs}

    adf_stat, adf_pval, kpss_stat, kpss_pval = None, None, None, None
    is_stationary = None
    acf_vals, pacf_vals = [], []
    lb_stat, lb_pval = None, None
    nlags = 1

    # ADF test
    try:
        adf_result = adfuller(y, autolag="AIC")
        adf_stat = float(adf_result[0])
        adf_pval = float(adf_result[1])
        adf_crit = {str(k): float(v) for k, v in adf_result[4].items()}
        is_stationary = adf_pval < 0.05
        statistics.update({
            "adf_statistic": round(adf_stat, 4),
            "adf_pvalue": round(adf_pval, 4),
            "adf_critical_values": adf_crit,
            "is_stationary": is_stationary,
        })
    except Exception:
        statistics["adf_note"] = "ADF test could not be computed."

    # KPSS test
    try:
        kpss_result = kpss(y, regression="c", nlags="auto")
        kpss_stat = float(kpss_result[0])
        kpss_pval = float(kpss_result[1])
        kpss_crit = {str(k): float(v) for k, v in kpss_result[3].items()}
        statistics.update({
            "kpss_statistic": round(kpss_stat, 4),
            "kpss_pvalue": round(kpss_pval, 4),
            "kpss_critical_values": kpss_crit,
        })
    except Exception:
        statistics["kpss_note"] = "KPSS test could not be computed."

    # ACF/PACF
    nlags = min(_MAX_AUTO_LAGS, n_obs // 2 - 1)
    if nlags < 1:
        nlags = 1
    try:
        acf_vals = acf(y, nlags=nlags).tolist()
        pacf_vals = pacf(y, nlags=nlags).tolist()
        statistics["acf_values"] = [
            {"lag": int(i), "value": round(float(v), 4)} for i, v in enumerate(acf_vals)
        ]
        statistics["pacf_values"] = [
            {"lag": int(i), "value": round(float(v), 4)} for i, v in enumerate(pacf_vals)
        ]
    except Exception:
        pass

    # Ljung-Box test
    try:
        lb_result = acorr_ljungbox(y, lags=[min(10, nlags)], return_df=True)
        lb_stat = float(lb_result["lb_stat"].iloc[0])
        lb_pval = float(lb_result["lb_pvalue"].iloc[0])
        statistics.update({
            "ljung_box_statistic": round(lb_stat, 4),
            "ljung_box_pvalue": round(lb_pval, 4),
        })
    except Exception:
        pass

    # Seasonal decomposition
    if seasonal and n_obs >= 2 * s:
        try:
            decomp = seasonal_decompose(y, model="additive", period=s)
            resid_var = np.var(decomp.resid.dropna())
            seas_plus_resid = decomp.seasonal.dropna() + decomp.resid.dropna()
            seasonal_strength = float(1 - resid_var / np.var(seas_plus_resid)) if np.var(seas_plus_resid) > 0 else 0
            statistics.update({
                "is_seasonal": True,
                "seasonal_period": s,
                "seasonal_strength": round(seasonal_strength, 4),
                "decomposition": {
                    "observed": y.tolist(),
                    "trend": decomp.trend.dropna().tolist() if decomp.trend is not None else [],
                    "seasonal": decomp.seasonal.dropna().tolist() if decomp.seasonal is not None else [],
                    "residual": decomp.resid.dropna().tolist() if decomp.resid is not None else [],
                },
            })
        except Exception:
            statistics["is_seasonal"] = False
    else:
        statistics["is_seasonal"] = False

    # ARIMA model
    if n_obs >= _MIN_ARIMA_OBS:
        try:
            if order_type == "Auto (AIC)":
                auto = _auto_arima_order(y, seasonal=seasonal, s=s)
                order = tuple(auto["order"])
                has_seasonal = auto["seasonal_order"] is not None
                arima_aic_val = auto["aic"]
                arima_bic_val = auto["bic"]
                arima_order_val = auto["order"]
            else:
                order = (manual_p, manual_d, manual_q)
                arima_order_val = [manual_p, manual_d, manual_q]
                has_seasonal = seasonal
                arima_aic_val, arima_bic_val = None, None

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                kwargs = dict(order=order)
                if has_seasonal:
                    seasonal_order = tuple(auto["seasonal_order"]) if order_type == "Auto (AIC)" else (manual_P, manual_D, manual_Q, s)
                    kwargs["seasonal_order"] = seasonal_order
                model = ARIMA(y, **kwargs)
                fitted = model.fit(method_kwargs={"disp": False})

            if arima_aic_val is None:
                arima_aic_val = float(fitted.aic)
                arima_bic_val = float(fitted.bic)

            statistics["arima_order"] = arima_order_val
            statistics["arima_aic"] = round(arima_aic_val, 2)
            statistics["arima_bic"] = round(arima_bic_val, 2)

            if forecast_steps > 0:
                fcast = fitted.get_forecast(steps=forecast_steps)
                fcast_mean = fcast.predicted_mean
                fcast_ci = fcast.conf_int(alpha=0.05)
                statistics["forecast_steps"] = forecast_steps
                statistics["forecast_values"] = [round(float(v), 4) for v in fcast_mean]
                statistics["forecast_ci_low"] = [round(float(v), 4) for v in fcast_ci.iloc[:, 0]]
                statistics["forecast_ci_high"] = [round(float(v), 4) for v in fcast_ci.iloc[:, 1]]

            residuals = fitted.resid
            resid_mean = float(np.mean(residuals))
            resid_std = float(np.std(residuals))
            if len(residuals) >= 8:
                _, resid_norm_p = scipy_stats.normaltest(residuals)
            else:
                resid_norm_p = None
            statistics["arima_residuals"] = {
                "mean_residual": round(resid_mean, 6),
                "std_residual": round(resid_std, 6),
                "residual_normality_p": round(float(resid_norm_p), 4) if resid_norm_p is not None else None,
            }
        except Exception:
            pass

    # Assumption checks
    checks: list[AssumptionCheck] = []
    if do_assumptions:
        if is_stationary is not None:
            if is_stationary:
                checks.append(AssumptionCheck(
                    name="Stationarity (ADF test)",
                    status="pass",
                    detail=f"ADF = {adf_stat:.4f}, p = {adf_pval:.4f}. Data appears stationary.",
                ))
            else:
                checks.append(AssumptionCheck(
                    name="Stationarity (ADF test)",
                    status="fail",
                    detail=f"ADF = {adf_stat:.4f}, p = {adf_pval:.4f}. Data is non-stationary.",
                    fix_suggestion="Consider differencing the series (d ≥ 1 in ARIMA) or applying a transformation.",
                ))
        if kpss_pval is not None:
            if kpss_pval < 0.05:
                checks.append(AssumptionCheck(
                    name="Stationarity (KPSS test)",
                    status="fail",
                    detail=f"KPSS = {kpss_stat:.4f}, p = {kpss_pval:.4f}. Rejects trend-stationarity.",
                    fix_suggestion="Series may have a unit root. Consider differencing.",
                ))
            else:
                checks.append(AssumptionCheck(
                    name="Stationarity (KPSS test)",
                    status="pass",
                    detail=f"KPSS = {kpss_stat:.4f}, p = {kpss_pval:.4f}. Data appears trend-stationary.",
                ))
        if lb_pval is not None:
            if lb_pval < 0.05:
                checks.append(AssumptionCheck(
                    name="Autocorrelation (Ljung-Box)",
                    status="fail",
                    detail=f"Q({nlags}) = {lb_stat:.4f}, p = {lb_pval:.4f}. Significant autocorrelation detected.",
                    fix_suggestion="Consider adding AR and/or MA terms to the model.",
                ))
            else:
                checks.append(AssumptionCheck(
                    name="Autocorrelation (Ljung-Box)",
                    status="pass",
                    detail=f"Q({nlags}) = {lb_stat:.4f}, p = {lb_pval:.4f}. No significant autocorrelation.",
                ))
        if "arima_residuals" in statistics and statistics["arima_residuals"].get("residual_normality_p") is not None:
            rnp = statistics["arima_residuals"]["residual_normality_p"]
            if rnp < 0.05:
                checks.append(AssumptionCheck(
                    name="Residual normality",
                    status="amber",
                    detail=f"ARIMA residuals deviate from normality (p = {rnp:.4f}).",
                    fix_suggestion="Estimates remain consistent, but prediction intervals may be affected.",
                ))
            else:
                checks.append(AssumptionCheck(
                    name="Residual normality",
                    status="pass",
                    detail=f"ARIMA residuals are approximately normal (p = {rnp:.4f}).",
                ))

    # Interpretation
    stat_desc = "stationary" if is_stationary else "non-stationary"
    arima_desc = ""
    if "arima_order" in statistics:
        p_str = ",".join(str(x) for x in statistics["arima_order"])
        aic_v = statistics["arima_aic"]
        bic_v = statistics["arima_bic"]
        arima_desc = f"ARIMA({p_str}) model fitted (AIC = {aic_v}, BIC = {bic_v}). "
        if len(statistics.get("forecast_values", [])) > 0:
            arima_desc += f"Forecast for {forecast_steps} steps generated."

    plain = (
        f"Time-series analysis of {n_obs} observations. "
        f"The series is {stat_desc} "
        f"(ADF p = {adf_pval:.4f}, KPSS p = {kpss_pval:.4f}). "
        f"{arima_desc}"
        f"Ljung-Box: Q({nlags}) = {lb_stat:.2f}, p = {lb_pval:.4f}."
    )

    apa = (
        f"A time-series analysis was conducted on {n_obs} data points "
        f"(value: {value_col}, time: {time_col}). "
        f"The ADF test indicated the series is {stat_desc} "
        f"(ADF = {adf_stat:.3f}, p = {adf_pval:.3f}), "
        f"and the KPSS test confirmed "
        f"{'trend-stationarity' if kpss_pval is not None and kpss_pval >= 0.05 else 'non-stationarity'} "
        f"(KPSS = {kpss_stat:.3f}, p = {kpss_pval:.3f}). "
        f"{arima_desc}"
    )

    technical = (
        f"Time-series — N: {n_obs}, ADF: {adf_stat:.4f} (p={adf_pval:.4f}), "
        f"KPSS: {kpss_stat:.4f} (p={kpss_pval:.4f}), "
        f"LB Q({nlags}): {lb_stat:.4f} (p={lb_pval:.4f})"
    )
    if "arima_order" in statistics:
        p_str = ",".join(str(x) for x in statistics["arima_order"])
        technical += f", ARIMA({p_str}): AIC={statistics['arima_aic']}, BIC={statistics['arima_bic']}"

    warnings_list: list[str] = []
    if not is_stationary and "arima_order" not in statistics:
        warnings_list.append("Series is non-stationary. Consider differencing before ARIMA modelling.")

    return AnalysisResult(
        test_key="timeseries",
        test_name="Time-Series Analysis",
        n_obs=n_obs,
        statistics=statistics,
        assumption_checks=checks,
        interpretation=Interpretation(plain=plain, apa=apa, technical=technical),
        warnings=warnings_list,
    )
