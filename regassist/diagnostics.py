"""
Diagnostic engine — runs all applicable tests against a FittedModel.

Config drives thresholds and explanations; Python drives the statsmodels calls.
Each test returns a DiagnosticResult that the remediation and report layers consume.

Covers: FR-5.1–5.3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yaml
from scipy.stats import chi2 as _chi2
from statsmodels.stats.diagnostic import het_breuschpagan, het_white
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import jarque_bera

from regassist.estimate import FittedModel

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "diagnostics.yaml"
_BORDERLINE_LOW_DEFAULT = 0.04
_BORDERLINE_HIGH_DEFAULT = 0.06


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class VIFEntry:
    """Per-variable VIF detail (VIF is multi-valued, unlike other tests)."""
    variable: str
    vif: float
    verdict: str   # "ok" | "examine" | "concern"


@dataclass
class DiagnosticResult:
    test_id: str
    test_name: str
    verdict: str              # "pass" | "fail" | "borderline"
    plain_explanation: str    # from config
    # Numeric summary (None for VIF which is per-variable)
    statistic: float | None = None
    p_value: float | None = None
    # Extra detail surfaced in the technical-detail layer
    details: dict = field(default_factory=dict)
    technical_note: str = ""
    error: str | None = None  # set if the test itself raised an exception


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_diagnostics(
    model: FittedModel,
    config_path: Path | str | None = None,
) -> list[DiagnosticResult]:
    """Run all applicable diagnostics for the given FittedModel.

    Args:
        model:       A FittedModel produced by estimate_ols (or future panel estimators).
        config_path: Override for the YAML config path (used in tests).

    Returns:
        A list of DiagnosticResult, one per test, in config order.
        Tests that don't apply to model.model_type are silently skipped (FR-5.2).
    """
    cfg = _load_config(config_path or _CONFIG_PATH)
    results = []
    for entry in cfg["diagnostics"]:
        if model.model_type not in entry.get("applies_to", []):
            continue
        runner = _RUNNERS.get(entry["id"])
        if runner is None:
            continue
        results.append(runner(model, entry))
    return results


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_config(path: Path | str) -> dict:
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Verdict helpers
# ---------------------------------------------------------------------------

def _with_const(X: pd.DataFrame) -> pd.DataFrame:
    """Return X with a constant column prepended if one is not already present.

    FE models store X without a constant (entity effects absorb it).
    Several statsmodels test functions require a constant in the design matrix.
    """
    if "const" not in X.columns:
        X = X.copy()
        X.insert(0, "const", 1.0)
    return X


def _p_verdict(p: float, entry: dict) -> str:
    """Map a p-value to pass / borderline / fail using config thresholds."""
    lo = entry.get("borderline_low", _BORDERLINE_LOW_DEFAULT)
    hi = entry.get("borderline_high", _BORDERLINE_HIGH_DEFAULT)
    threshold = entry.get("threshold", 0.05)
    if p > threshold:
        return "pass"
    if lo <= p <= hi:
        return "borderline"
    return "fail"


def _vif_verdict(vif: float, concern: float, examine: float) -> str:
    if vif >= concern:
        return "concern"
    if vif >= examine:
        return "examine"
    return "ok"


# ---------------------------------------------------------------------------
# Individual test runners
# (signature: FittedModel, config_entry -> DiagnosticResult)
# ---------------------------------------------------------------------------

def _run_vif(model: FittedModel, entry: dict) -> DiagnosticResult:
    concern = entry.get("threshold_concern", 10)
    examine = entry.get("threshold_examine", 5)

    # VIF is only meaningful with ≥2 independent variables
    if len(model.indep_vars) < 2:
        return DiagnosticResult(
            test_id=entry["id"],
            test_name=entry["name"],
            verdict="pass",
            plain_explanation=entry["plain_explanation"],
            technical_note=entry.get("technical_note", ""),
            details={"note": "VIF requires ≥2 independent variables; skipped with a single predictor."},
        )

    # variance_inflation_factor must receive the FULL design matrix (including
    # the constant column) so that the intercept is correctly partialled out.
    # FE models store X without a constant — add one before computing VIF.
    # We then report VIFs only for the non-constant predictors.
    X_for_vif = _with_const(model.X)
    X_arr = X_for_vif.values.astype(float)
    col_names = list(X_for_vif.columns)

    entries: list[VIFEntry] = []
    for i, var in enumerate(col_names):
        if var == "const":
            continue
        vif_val = float(variance_inflation_factor(X_arr, i))
        entries.append(VIFEntry(
            variable=var,
            vif=round(vif_val, 4),
            verdict=_vif_verdict(vif_val, concern, examine),
        ))

    max_vif = max(e.vif for e in entries)
    worst = max(entries, key=lambda e: e.vif).verdict

    if worst == "concern":
        overall = "fail"
    elif worst == "examine":
        overall = "borderline"
    else:
        overall = "pass"

    return DiagnosticResult(
        test_id=entry["id"],
        test_name=entry["name"],
        verdict=overall,
        plain_explanation=entry["plain_explanation"],
        technical_note=entry.get("technical_note", ""),
        statistic=round(max_vif, 4),
        details={
            "per_variable": [
                {"variable": e.variable, "vif": e.vif, "verdict": e.verdict}
                for e in entries
            ],
            "threshold_concern": concern,
            "threshold_examine": examine,
        },
    )


def _run_breusch_pagan(model: FittedModel, entry: dict) -> DiagnosticResult:
    try:
        # het_breuschpagan requires exog to contain a constant column.
        # FE models store X without one — _with_const adds it when needed.
        lm, lm_p, _f, _fp = het_breuschpagan(model.residuals, _with_const(model.X))
        return DiagnosticResult(
            test_id=entry["id"],
            test_name=entry["name"],
            verdict=_p_verdict(float(lm_p), entry),
            plain_explanation=entry["plain_explanation"],
            technical_note=entry.get("technical_note", ""),
            statistic=round(float(lm), 4),
            p_value=round(float(lm_p), 4),
            details={"statistic_type": "LM (χ²)", "null": "Homoskedasticity"},
        )
    except Exception as exc:
        return _error_result(entry, exc)


def _run_white(model: FittedModel, entry: dict) -> DiagnosticResult:
    try:
        # het_white requires a constant column — add one for FE models.
        lm, lm_p, _f, _fp = het_white(model.residuals, _with_const(model.X))
        return DiagnosticResult(
            test_id=entry["id"],
            test_name=entry["name"],
            verdict=_p_verdict(float(lm_p), entry),
            plain_explanation=entry["plain_explanation"],
            technical_note=entry.get("technical_note", ""),
            statistic=round(float(lm), 4),
            p_value=round(float(lm_p), 4),
            details={"statistic_type": "LM (χ²)", "null": "Homoskedasticity"},
        )
    except Exception as exc:
        return _error_result(entry, exc)


def _run_ramsey_reset(model: FittedModel, entry: dict) -> DiagnosticResult:
    """Manual RESET implementation: add ŷ² and ŷ³, F-test their joint significance.

    We implement this directly rather than using statsmodels' linear_reset()
    to avoid unstable ContrastResults attribute names across statsmodels versions.
    """
    try:
        yhat = model.fitted
        # FE models store X without a constant — add one so the augmented OLS
        # is correctly specified. RE and OLS already have a "const" column.
        X_aug = _with_const(model.X).copy()
        X_aug["_yhat2"] = yhat ** 2
        X_aug["_yhat3"] = yhat ** 3

        res_aug = sm.OLS(model.y, X_aug).fit()

        # F-test: are the coefficients on ŷ² and ŷ³ jointly zero?
        r_matrix = np.zeros((2, X_aug.shape[1]))
        aug_cols = list(X_aug.columns)
        r_matrix[0, aug_cols.index("_yhat2")] = 1
        r_matrix[1, aug_cols.index("_yhat3")] = 1

        f_test = res_aug.f_test(r_matrix)
        f_stat = float(f_test.fvalue.item() if hasattr(f_test.fvalue, "item") else f_test.fvalue)
        f_p = float(f_test.pvalue.item() if hasattr(f_test.pvalue, "item") else f_test.pvalue)

        return DiagnosticResult(
            test_id=entry["id"],
            test_name=entry["name"],
            verdict=_p_verdict(f_p, entry),
            plain_explanation=entry["plain_explanation"],
            technical_note=entry.get("technical_note", ""),
            statistic=round(f_stat, 4),
            p_value=round(f_p, 4),
            details={
                "statistic_type": "F",
                "null": "No omitted nonlinear terms",
                "powers_tested": "ŷ², ŷ³",
            },
        )
    except Exception as exc:
        return _error_result(entry, exc)


def _run_jarque_bera(model: FittedModel, entry: dict) -> DiagnosticResult:
    try:
        jb_stat, jb_p, skew, kurtosis = jarque_bera(model.residuals)

        # Context note: JB is less meaningful for large n (CLT rescues inference).
        n = model.n_obs
        if n > 100 and float(jb_p) < entry.get("threshold", 0.05):
            size_note = (
                f"Note: with n={n} the Central Limit Theorem largely rescues "
                "inference; this failure is often not actionable."
            )
        elif n < 30 and float(jb_p) < entry.get("threshold", 0.05):
            size_note = (
                f"Note: with n={n} non-normality can affect t/F test reliability."
            )
        else:
            size_note = ""

        return DiagnosticResult(
            test_id=entry["id"],
            test_name=entry["name"],
            verdict=_p_verdict(float(jb_p), entry),
            plain_explanation=entry["plain_explanation"],
            technical_note=entry.get("technical_note", ""),
            statistic=round(float(jb_stat), 4),
            p_value=round(float(jb_p), 4),
            details={
                "statistic_type": "JB (χ²)",
                "null": "Residuals are normally distributed",
                "skewness": round(float(skew), 4),
                "excess_kurtosis": round(float(kurtosis), 4),
                "n_obs": n,
                "size_note": size_note,
            },
        )
    except Exception as exc:
        return _error_result(entry, exc)


def _run_wooldridge(model: FittedModel, entry: dict) -> DiagnosticResult:
    """Wooldridge (2002) test for first-order serial correlation in panel data.

    Correct implementation (Wooldridge 2002, Ch. 10):
      1. First-difference y and X within each entity.
      2. Regress Δy on ΔX (no constant) to get FD residuals ũ_it.
      3. Regress ũ_it on ũ_{i,t-1} (pooled OLS with constant).
      4. F-test H₀: ρ̂ = −0.5 (implied by no serial correlation in levels).

    Skipped with a note when any entity has fewer than 3 time periods.
    """
    from scipy.stats import f as _f_dist

    y = model.y
    X = model.X

    if not isinstance(y.index, pd.MultiIndex):
        return _error_result(entry, ValueError("Wooldridge test requires a panel model with MultiIndex data."))

    # Check minimum T (original data)
    T_per_entity = y.groupby(level=0).count()
    min_T = int(T_per_entity.min())
    n_entities = int(len(T_per_entity))
    if min_T < 3:
        return DiagnosticResult(
            test_id=entry["id"],
            test_name=entry["name"],
            verdict="pass",
            plain_explanation=entry["plain_explanation"],
            technical_note=entry.get("technical_note", ""),
            details={"note": f"Minimum T = {min_T} (< 3 periods); Wooldridge test skipped."},
        )

    # First-difference y and X together so they share the exact same index.
    # Diffing from a joint DataFrame avoids MultiIndex intersection bugs where
    # .intersection() can return a deduplicated index (N entities instead of
    # N×T rows), causing a length mismatch when building the residual Series.
    X_no_const = X.drop(columns=["const"], errors="ignore")
    fd_frame = pd.concat([y.rename("__y__"), X_no_const], axis=1)
    fd_frame = fd_frame.groupby(level=0).diff().dropna()
    y_fd = fd_frame["__y__"]
    X_fd = fd_frame.drop(columns=["__y__"])

    if y_fd.empty or X_fd.empty:
        return _error_result(entry, ValueError("No observations remain after first-differencing."))

    # First-differenced OLS (no constant — differencing removes the intercept)
    try:
        fd_res = sm.OLS(y_fd.values, X_fd.values).fit()
    except Exception as exc:
        return _error_result(entry, exc)

    u_fd = pd.Series(fd_res.resid, index=y_fd.index)

    # Lag FD residuals within entity
    u_df = u_fd.reset_index()
    u_df.columns = ["entity", "time", "u"]
    u_df = u_df.sort_values(["entity", "time"])
    u_df["u_lag"] = u_df.groupby("entity")["u"].shift(1)
    fd2 = u_df.dropna(subset=["u_lag"])

    if len(fd2) < 4:
        return _error_result(entry, ValueError("Too few observations after lagging FD residuals."))

    # Regress ũ_it on ũ_{i,t-1} and F-test coeff = −0.5
    y_r = fd2["u"].values
    X_r = sm.add_constant(fd2["u_lag"].values)
    try:
        res_r = sm.OLS(y_r, X_r).fit()
    except Exception as exc:
        return _error_result(entry, exc)

    rho    = float(res_r.params[1])
    se_rho = float(res_r.bse[1])
    if se_rho == 0:
        return _error_result(entry, ValueError("Zero SE in Wooldridge regression."))

    f_stat = ((rho - (-0.5)) / se_rho) ** 2
    p_val  = float(1.0 - _f_dist.cdf(f_stat, 1, len(fd2) - 2))

    return DiagnosticResult(
        test_id=entry["id"],
        test_name=entry["name"],
        verdict=_p_verdict(p_val, entry),
        plain_explanation=entry["plain_explanation"],
        technical_note=entry.get("technical_note", ""),
        statistic=round(f_stat, 4),
        p_value=round(p_val, 4),
        details={
            "statistic_type": "F(1, N·(T̄−2)−1)",
            "null": "No first-order serial correlation",
            "rho_hat": round(rho, 4),
            "n_entities": n_entities,
            "min_T": min_T,
        },
    )


def _run_modified_wald(model: FittedModel, entry: dict) -> DiagnosticResult:
    """Modified Wald test for groupwise heteroskedasticity in FE panel residuals.

    H₀: σ²_i = σ² for all entities i (homoskedastic across groups).
    Statistic: W = Σᵢ Tᵢ·(σ̂²_i − σ̂²)² / (2·σ̂⁴)  ~ χ²(N−1).
    """
    resids = model.residuals
    if not isinstance(resids.index, pd.MultiIndex):
        return _error_result(entry, ValueError("Modified Wald test requires a panel model with MultiIndex residuals."))

    df = resids.reset_index()
    df.columns = ["entity", "time", "e"]

    grp = df.groupby("entity")["e"]
    sigma2_i = grp.apply(lambda x: float((x ** 2).mean()))   # per-entity mean sq resid
    T_i      = grp.count().astype(float)
    N        = len(sigma2_i)
    sigma2   = float(sigma2_i.mean())

    if sigma2 == 0 or N < 2:
        return _error_result(entry, ValueError("Cannot compute Modified Wald: zero variance or fewer than 2 entities."))

    W   = float(((T_i * (sigma2_i - sigma2) ** 2) / (2.0 * sigma2 ** 2)).sum())
    p   = float(1.0 - _chi2.cdf(W, df=N - 1))

    return DiagnosticResult(
        test_id=entry["id"],
        test_name=entry["name"],
        verdict=_p_verdict(p, entry),
        plain_explanation=entry["plain_explanation"],
        technical_note=entry.get("technical_note", ""),
        statistic=round(W, 4),
        p_value=round(p, 4),
        details={
            "statistic_type": f"χ²({N - 1})",
            "null": "Homoskedastic errors across entities",
            "n_entities": N,
            "dof": N - 1,
        },
    )


def _error_result(entry: dict, exc: Exception) -> DiagnosticResult:
    return DiagnosticResult(
        test_id=entry["id"],
        test_name=entry["name"],
        verdict="borderline",   # don't block on a test failure; flag it
        plain_explanation=entry["plain_explanation"],
        technical_note=entry.get("technical_note", ""),
        error=f"Test could not be computed: {exc}",
    )


# ---------------------------------------------------------------------------
# Runner registry (order matches config)
# ---------------------------------------------------------------------------

_RUNNERS: dict[str, Callable[[FittedModel, dict], DiagnosticResult]] = {
    "vif":             _run_vif,
    "breusch_pagan":   _run_breusch_pagan,
    "white":           _run_white,
    "ramsey_reset":    _run_ramsey_reset,
    "jarque_bera":     _run_jarque_bera,
    "wooldridge":      _run_wooldridge,
    "modified_wald":   _run_modified_wald,
}
