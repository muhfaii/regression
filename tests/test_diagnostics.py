"""
Tests for regassist.diagnostics (FR-5.1–5.3).

Each test needs a dataset designed to reliably trigger (or not trigger) a
specific diagnostic failure. All RNGs are seeded for reproducibility (NFR-3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from regassist.diagnostics import DiagnosticResult, run_diagnostics
from regassist.estimate import estimate_ols


# ---------------------------------------------------------------------------
# Dataset factories
# ---------------------------------------------------------------------------

def _clean(n: int = 200, seed: int = 0) -> pd.DataFrame:
    """Well-behaved DGP: linear, homoskedastic, normal errors."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(10, 2, n)
    x2 = rng.normal(5, 1, n)
    y = 3 + 2 * x1 + 1.5 * x2 + rng.normal(0, 1, n)
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _heteroskedastic(n: int = 200, seed: int = 1) -> pd.DataFrame:
    """Variance of errors grows with x1 → triggers BP and White."""
    rng = np.random.default_rng(seed)
    x1 = rng.uniform(1, 10, n)
    x2 = rng.normal(5, 1, n)
    noise = rng.normal(0, 1, n) * x1  # variance ∝ x1
    y = 3 + 2 * x1 + 1.5 * x2 + noise
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _multicollinear(n: int = 200, seed: int = 2) -> pd.DataFrame:
    """x2 ≈ x1 + tiny noise → VIF >> 10."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(10, 2, n)
    x2 = x1 + rng.normal(0, 0.05, n)   # near-perfect collinearity
    y = 3 + 2 * x1 + rng.normal(0, 1, n)
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _misspecified(n: int = 300, seed: int = 3) -> pd.DataFrame:
    """True relationship is quadratic; we fit linear → triggers RESET."""
    rng = np.random.default_rng(seed)
    x1 = rng.uniform(0, 5, n)
    x2 = rng.normal(5, 1, n)
    y = 1 + x1 ** 2 + 0.5 * x2 + rng.normal(0, 0.5, n)
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _heavy_tailed(n: int = 150, seed: int = 4) -> pd.DataFrame:
    """Errors drawn from t(2) — very heavy tails → triggers Jarque-Bera."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(10, 2, n)
    x2 = rng.normal(5, 1, n)
    noise = rng.standard_t(df=2, size=n) * 2
    y = 3 + 2 * x1 + 1.5 * x2 + noise
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _fit(df: pd.DataFrame) -> object:
    return estimate_ols(df, "y", ["x1", "x2"])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get(results: list[DiagnosticResult], test_id: str) -> DiagnosticResult:
    return next(r for r in results if r.test_id == test_id)


# ---------------------------------------------------------------------------
# run_diagnostics — structure checks
# ---------------------------------------------------------------------------

def test_returns_five_results_for_ols():
    results = run_diagnostics(_fit(_clean()))
    assert len(results) == 5


def test_all_results_are_diagnostic_result():
    for r in run_diagnostics(_fit(_clean())):
        assert isinstance(r, DiagnosticResult)


def test_result_ids_match_config():
    ids = [r.test_id for r in run_diagnostics(_fit(_clean()))]
    assert ids == ["vif", "breusch_pagan", "white", "ramsey_reset", "jarque_bera"]


def test_verdict_values_are_valid():
    for r in run_diagnostics(_fit(_clean())):
        assert r.verdict in {"pass", "fail", "borderline"}


def test_plain_explanation_is_non_empty():
    for r in run_diagnostics(_fit(_clean())):
        assert r.plain_explanation.strip()


def test_technical_note_is_non_empty():
    for r in run_diagnostics(_fit(_clean())):
        assert r.technical_note.strip()


# ---------------------------------------------------------------------------
# FR-5.2: non-OLS model type skips all OLS tests
# ---------------------------------------------------------------------------

def test_panel_only_tests_skipped_for_ols():
    """Panel-only tests (wooldridge, modified_wald) must not run for OLS models."""
    results = run_diagnostics(_fit(_clean()))
    panel_ids = {"wooldridge", "modified_wald"}
    result_ids = {r.test_id for r in results}
    assert panel_ids.isdisjoint(result_ids), (
        f"Panel-only tests should not run for OLS model; got: {result_ids & panel_ids}"
    )


# ---------------------------------------------------------------------------
# FR-5.3: statistic, p_value, threshold present where applicable
# ---------------------------------------------------------------------------

def test_bp_has_statistic_and_pvalue():
    r = _get(run_diagnostics(_fit(_clean())), "breusch_pagan")
    assert r.statistic is not None
    assert r.p_value is not None
    assert 0.0 <= r.p_value <= 1.0


def test_white_has_statistic_and_pvalue():
    r = _get(run_diagnostics(_fit(_clean())), "white")
    assert r.statistic is not None
    assert 0.0 <= r.p_value <= 1.0


def test_reset_has_statistic_and_pvalue():
    r = _get(run_diagnostics(_fit(_clean())), "ramsey_reset")
    assert r.statistic is not None
    assert 0.0 <= r.p_value <= 1.0


def test_jb_has_statistic_and_pvalue():
    r = _get(run_diagnostics(_fit(_clean())), "jarque_bera")
    assert r.statistic is not None
    assert 0.0 <= r.p_value <= 1.0


def test_vif_has_per_variable_detail():
    r = _get(run_diagnostics(_fit(_clean())), "vif")
    assert "per_variable" in r.details
    assert len(r.details["per_variable"]) == 2   # x1, x2


def test_jb_details_include_skewness_and_kurtosis():
    r = _get(run_diagnostics(_fit(_clean())), "jarque_bera")
    assert "skewness" in r.details
    assert "excess_kurtosis" in r.details


# ---------------------------------------------------------------------------
# Correct pass on clean data
# ---------------------------------------------------------------------------

def test_clean_data_all_pass():
    results = run_diagnostics(_fit(_clean()))
    failed = [r.test_id for r in results if r.verdict == "fail"]
    assert failed == [], f"Unexpected failures on clean data: {failed}"


# ---------------------------------------------------------------------------
# Correct fail on triggered data
# ---------------------------------------------------------------------------

def test_heteroskedastic_triggers_bp():
    r = _get(run_diagnostics(_fit(_heteroskedastic())), "breusch_pagan")
    assert r.verdict == "fail", f"Expected fail, got {r.verdict} (p={r.p_value})"


def test_heteroskedastic_triggers_white():
    r = _get(run_diagnostics(_fit(_heteroskedastic())), "white")
    assert r.verdict == "fail", f"Expected fail, got {r.verdict} (p={r.p_value})"


def test_multicollinear_triggers_vif():
    r = _get(run_diagnostics(_fit(_multicollinear())), "vif")
    assert r.verdict == "fail", f"Expected fail, got {r.verdict} (max VIF={r.statistic})"


def test_multicollinear_vif_per_variable_has_concern():
    r = _get(run_diagnostics(_fit(_multicollinear())), "vif")
    verdicts = {e["verdict"] for e in r.details["per_variable"]}
    assert "concern" in verdicts


def test_misspecified_triggers_reset():
    r = _get(run_diagnostics(_fit(_misspecified())), "ramsey_reset")
    assert r.verdict == "fail", f"Expected fail, got {r.verdict} (p={r.p_value})"


def test_heavy_tailed_triggers_jb():
    r = _get(run_diagnostics(_fit(_heavy_tailed())), "jarque_bera")
    assert r.verdict == "fail", f"Expected fail, got {r.verdict} (p={r.p_value})"


# ---------------------------------------------------------------------------
# VIF: single-predictor edge case
# ---------------------------------------------------------------------------

def test_single_predictor_vif_passes():
    rng = np.random.default_rng(99)
    df = pd.DataFrame({
        "y": rng.normal(0, 1, 50),
        "x": rng.normal(0, 1, 50),
    })
    model = estimate_ols(df, "y", ["x"])
    r = _get(run_diagnostics(model), "vif")
    assert r.verdict == "pass"
    assert "skipped" in r.details.get("note", "").lower()


# ---------------------------------------------------------------------------
# JB size note included for large n
# ---------------------------------------------------------------------------

def test_jb_size_note_for_large_n():
    """For n > 100 a failing JB should carry a note about CLT."""
    r = _get(run_diagnostics(_fit(_heavy_tailed(n=150))), "jarque_bera")
    if r.verdict == "fail":
        assert r.details["size_note"] != ""
