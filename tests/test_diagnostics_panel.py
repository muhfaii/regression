"""Tests for panel diagnostic runners: Wooldridge and Modified Wald."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from regassist.diagnostics import DiagnosticResult, run_diagnostics
from regassist.estimate import estimate_fe, estimate_re


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def _balanced_panel(n_entities=30, n_periods=10, seed=42) -> pd.DataFrame:
    """Balanced panel with no serial correlation and homoskedastic errors."""
    rng = np.random.default_rng(seed)
    rows = [(e, t) for e in range(n_entities) for t in range(n_periods)]
    df = pd.DataFrame(rows, columns=["entity", "time"])
    fe = {e: rng.normal(0, 1) for e in range(n_entities)}
    df["fe"] = df["entity"].map(fe)
    df["x1"] = rng.normal(0, 1, len(df))
    df["y"] = 1.5 + 2.0 * df["x1"] + df["fe"] + rng.normal(0, 0.5, len(df))
    return df.drop(columns=["fe"])


def _serial_panel(n_entities=40, n_periods=10, seed=11) -> pd.DataFrame:
    """Panel with strong AR(1) serial correlation (ρ = 0.8)."""
    rng = np.random.default_rng(seed)
    rows = []
    for e in range(n_entities):
        eps = 0.0
        for t in range(n_periods):
            eps = 0.8 * eps + rng.normal(0, 1)
            rows.append({"entity": e, "time": t, "x1": rng.normal(0, 1), "eps": eps})
    df = pd.DataFrame(rows)
    fe = {e: rng.normal(0, 1) for e in range(n_entities)}
    df["fe_val"] = df["entity"].map(fe)
    df["y"] = 1.0 + 2.0 * df["x1"] + df["fe_val"] + df["eps"]
    return df.drop(columns=["fe_val", "eps"])


def _hetero_panel(n_entities=30, n_periods=10, seed=77) -> pd.DataFrame:
    """Panel where entity-level error variance varies strongly across entities."""
    rng = np.random.default_rng(seed)
    rows = []
    for e in range(n_entities):
        sigma_e = 0.1 + e * 0.3    # entity e has variance proportional to its index
        fe_val = rng.normal(0, 1)
        for t in range(n_periods):
            x1 = rng.normal(0, 1)
            y = 1.0 + 2.0 * x1 + fe_val + rng.normal(0, sigma_e)
            rows.append({"entity": e, "time": t, "x1": x1, "y": y})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# run_diagnostics respects applies_to
# ---------------------------------------------------------------------------

def test_ols_model_does_not_run_wooldridge():
    """Wooldridge is applies_to: [fe, re] — should be absent for OLS."""
    from regassist.estimate import estimate_ols
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"y": rng.normal(0, 1, 100), "x": rng.normal(0, 1, 100)})
    m = estimate_ols(df, "y", ["x"])
    ids = {r.test_id for r in run_diagnostics(m)}
    assert "wooldridge" not in ids


def test_ols_model_does_not_run_modified_wald():
    from regassist.estimate import estimate_ols
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"y": rng.normal(0, 1, 100), "x": rng.normal(0, 1, 100)})
    m = estimate_ols(df, "y", ["x"])
    ids = {r.test_id for r in run_diagnostics(m)}
    assert "modified_wald" not in ids


def test_fe_model_runs_wooldridge():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    ids = {r.test_id for r in run_diagnostics(m)}
    assert "wooldridge" in ids


def test_fe_model_runs_modified_wald():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    ids = {r.test_id for r in run_diagnostics(m)}
    assert "modified_wald" in ids


def test_re_model_runs_wooldridge():
    df = _balanced_panel()
    m = estimate_re(df, "y", ["x1"], "entity", "time")
    ids = {r.test_id for r in run_diagnostics(m)}
    assert "wooldridge" in ids


def test_re_model_does_not_run_modified_wald():
    """Modified Wald is applies_to: [fe] only."""
    df = _balanced_panel()
    m = estimate_re(df, "y", ["x1"], "entity", "time")
    ids = {r.test_id for r in run_diagnostics(m)}
    assert "modified_wald" not in ids


# ---------------------------------------------------------------------------
# Wooldridge — result shape
# ---------------------------------------------------------------------------

def test_wooldridge_returns_diagnostic_result():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    results = run_diagnostics(m)
    w = next(r for r in results if r.test_id == "wooldridge")
    assert isinstance(w, DiagnosticResult)


def test_wooldridge_verdict_valid():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    w = next(r for r in run_diagnostics(m) if r.test_id == "wooldridge")
    assert w.verdict in {"pass", "fail", "borderline"}


def test_wooldridge_statistic_nonnegative():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    w = next(r for r in run_diagnostics(m) if r.test_id == "wooldridge")
    if w.statistic is not None:
        assert w.statistic >= 0


def test_wooldridge_pvalue_in_range():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    w = next(r for r in run_diagnostics(m) if r.test_id == "wooldridge")
    if w.p_value is not None:
        assert 0.0 <= w.p_value <= 1.0


def test_wooldridge_passes_for_clean_panel():
    """Clean panel (iid errors) should pass the serial correlation test."""
    df = _balanced_panel(n_entities=40, n_periods=12, seed=42)
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    w = next(r for r in run_diagnostics(m) if r.test_id == "wooldridge")
    assert w.verdict in {"pass", "borderline"}


def test_wooldridge_detects_serial_correlation():
    """AR(1) panel should trigger Wooldridge failure."""
    df = _serial_panel(n_entities=40, n_periods=10, seed=11)
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    w = next(r for r in run_diagnostics(m) if r.test_id == "wooldridge")
    assert w.verdict in {"fail", "borderline"}


def test_wooldridge_skipped_when_t_lt_3():
    """Panel with T=2 per entity: Wooldridge should be skipped (verdict=pass with note)."""
    rng = np.random.default_rng(55)
    rows = [(e, t) for e in range(20) for t in range(2)]
    df = pd.DataFrame(rows, columns=["entity", "time"])
    df["x1"] = rng.normal(0, 1, len(df))
    df["y"] = 2.0 * df["x1"] + rng.normal(0, 1, len(df))
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    w = next(r for r in run_diagnostics(m) if r.test_id == "wooldridge")
    assert w.verdict == "pass"
    assert "note" in w.details


# ---------------------------------------------------------------------------
# Modified Wald — result shape
# ---------------------------------------------------------------------------

def test_modified_wald_returns_diagnostic_result():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    results = run_diagnostics(m)
    mw = next(r for r in results if r.test_id == "modified_wald")
    assert isinstance(mw, DiagnosticResult)


def test_modified_wald_verdict_valid():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    mw = next(r for r in run_diagnostics(m) if r.test_id == "modified_wald")
    assert mw.verdict in {"pass", "fail", "borderline"}


def test_modified_wald_statistic_nonnegative():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    mw = next(r for r in run_diagnostics(m) if r.test_id == "modified_wald")
    if mw.statistic is not None:
        assert mw.statistic >= 0


def test_modified_wald_pvalue_in_range():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    mw = next(r for r in run_diagnostics(m) if r.test_id == "modified_wald")
    if mw.p_value is not None:
        assert 0.0 <= mw.p_value <= 1.0


def test_modified_wald_passes_for_homoskedastic_panel():
    """Clean panel with constant variance should pass."""
    df = _balanced_panel(n_entities=30, n_periods=10, seed=42)
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    mw = next(r for r in run_diagnostics(m) if r.test_id == "modified_wald")
    assert mw.verdict in {"pass", "borderline"}


def test_modified_wald_detects_groupwise_hetero():
    """Strongly heteroskedastic panel should fail."""
    df = _hetero_panel(n_entities=30, n_periods=10, seed=77)
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    mw = next(r for r in run_diagnostics(m) if r.test_id == "modified_wald")
    assert mw.verdict in {"fail", "borderline"}


def test_modified_wald_n_entities_in_details():
    df = _balanced_panel()
    m = estimate_fe(df, "y", ["x1"], "entity", "time")
    mw = next(r for r in run_diagnostics(m) if r.test_id == "modified_wald")
    assert mw.details.get("n_entities") == 30


# ---------------------------------------------------------------------------
# Cross-pattern: panel_serial_and_hetero fires when both fail
# ---------------------------------------------------------------------------

def test_panel_cross_pattern_fires_when_both_fail():
    from regassist.remediate import build_remediation

    ser = DiagnosticResult("wooldridge",    "Wooldridge", "fail", "x", statistic=8.0,  p_value=0.004)
    mw  = DiagnosticResult("modified_wald", "Mod Wald",  "fail", "x", statistic=60.0, p_value=0.001)

    df = _balanced_panel()
    m  = estimate_fe(df, "y", ["x1"], "entity", "time")
    rem = build_remediation([ser, mw], m)

    pattern_ids = {p.id for p in rem.patterns}
    assert "panel_serial_and_hetero" in pattern_ids


def test_panel_cross_pattern_does_not_fire_when_only_one_fails():
    from regassist.remediate import build_remediation

    ser  = DiagnosticResult("wooldridge",    "Wooldridge", "fail", "x", statistic=8.0, p_value=0.004)
    mw   = DiagnosticResult("modified_wald", "Mod Wald",  "pass", "x", statistic=5.0, p_value=0.20)

    df = _balanced_panel()
    m  = estimate_fe(df, "y", ["x1"], "entity", "time")
    rem = build_remediation([ser, mw], m)

    pattern_ids = {p.id for p in rem.patterns}
    assert "panel_serial_and_hetero" not in pattern_ids
