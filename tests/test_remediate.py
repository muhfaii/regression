"""
Tests for regassist.remediate (FR-6.1, 6.2, 6.4, FR-5.4).

Uses synthetic datasets from test_diagnostics to produce real DiagnosticResults,
then verifies the remediation layer maps them correctly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from regassist.diagnostics import run_diagnostics
from regassist.estimate import estimate_ols
from regassist.remediate import (
    CrossPattern,
    PerTestRemediation,
    RemediationReport,
    build_remediation,
)


# ---------------------------------------------------------------------------
# Dataset helpers (mirrors test_diagnostics)
# ---------------------------------------------------------------------------

def _clean(n=200, seed=5):
    rng = np.random.default_rng(seed)
    x1, x2 = rng.normal(10, 2, n), rng.normal(5, 1, n)
    y = 3 + 2 * x1 + 1.5 * x2 + rng.normal(0, 1, n)
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _heteroskedastic(n=200, seed=1):
    rng = np.random.default_rng(seed)
    x1 = rng.uniform(1, 10, n)
    x2 = rng.normal(5, 1, n)
    y = 3 + 2 * x1 + 1.5 * x2 + rng.normal(0, 1, n) * x1
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _misspecified(n=300, seed=3):
    rng = np.random.default_rng(seed)
    x1 = rng.uniform(0, 5, n)
    x2 = rng.normal(5, 1, n)
    y = 1 + x1 ** 2 + 0.5 * x2 + rng.normal(0, 0.5, n)
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _run(df: pd.DataFrame):
    model = estimate_ols(df, "y", ["x1", "x2"])
    diag = run_diagnostics(model)
    return build_remediation(diag, model)


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def test_returns_remediation_report():
    assert isinstance(_run(_clean()), RemediationReport)


def test_clean_data_no_issues():
    report = _run(_clean())
    assert not report.has_issues
    assert report.per_test == []
    assert report.patterns == []


def test_non_passing_tests_get_remedies():
    report = _run(_heteroskedastic())
    assert report.has_issues
    assert len(report.per_test) > 0


def test_only_non_passing_get_remedies():
    """Passing tests must not appear in per_test."""
    report = _run(_heteroskedastic())
    for tr in report.per_test:
        assert tr.verdict in ("fail", "borderline")


# ---------------------------------------------------------------------------
# FR-6.1: ranked remedies
# ---------------------------------------------------------------------------

def test_remedies_are_sorted_by_priority():
    report = _run(_heteroskedastic())
    bp = next((t for t in report.per_test if t.test_id == "breusch_pagan"), None)
    if bp:
        priorities = [r.priority for r in bp.remedies]
        assert priorities == sorted(priorities)


def test_remedies_non_empty_for_failed_test():
    report = _run(_heteroskedastic())
    for tr in report.per_test:
        assert len(tr.remedies) > 0, f"No remedies for {tr.test_id}"


# ---------------------------------------------------------------------------
# FR-6.2: quick_fix vs thinking_fix
# ---------------------------------------------------------------------------

def test_remedy_kind_values():
    report = _run(_heteroskedastic())
    for tr in report.per_test:
        for rem in tr.remedies:
            assert rem.kind in ("quick_fix", "thinking_fix"), \
                f"Invalid kind '{rem.kind}' for {tr.test_id}"


def test_bp_first_remedy_is_quick_fix():
    """Robust SEs (priority 1) must be a quick_fix for BP."""
    report = _run(_heteroskedastic())
    bp = next((t for t in report.per_test if t.test_id == "breusch_pagan"), None)
    if bp:
        assert bp.remedies[0].kind == "quick_fix"


def test_reset_first_remedy_is_quick_fix():
    """Examine residual plots (priority 1) must be a quick_fix for RESET."""
    report = _run(_misspecified())
    reset = next((t for t in report.per_test if t.test_id == "ramsey_reset"), None)
    if reset:
        assert reset.remedies[0].kind == "quick_fix"


# ---------------------------------------------------------------------------
# FR-6.4: each remedy has a non-empty 'why' explanation
# ---------------------------------------------------------------------------

def test_all_remedies_have_why():
    report = _run(_heteroskedastic())
    for tr in report.per_test:
        for rem in tr.remedies:
            assert rem.why.strip(), \
                f"Empty 'why' for remedy '{rem.description}' in {tr.test_id}"


def test_all_remediations_have_caveat():
    report = _run(_heteroskedastic())
    for tr in report.per_test:
        assert tr.honest_caveat.strip(), f"Missing caveat for {tr.test_id}"


# ---------------------------------------------------------------------------
# failed_ids helper
# ---------------------------------------------------------------------------

def test_failed_ids_returns_set_of_test_ids():
    report = _run(_heteroskedastic())
    assert isinstance(report.failed_ids, set)
    if report.has_issues:
        for tid in report.failed_ids:
            assert isinstance(tid, str)


# ---------------------------------------------------------------------------
# FR-5.4: cross-diagnostic patterns
# ---------------------------------------------------------------------------

def test_spec_not_inference_fires_when_bp_and_reset_fail():
    """Pattern 'spec_not_inference' requires BP + RESET both non-passing."""
    from regassist.diagnostics import DiagnosticResult

    bp_fail   = DiagnosticResult("breusch_pagan", "BP",    "fail",      "x", statistic=5.0, p_value=0.01)
    reset_fail = DiagnosticResult("ramsey_reset",  "RESET", "fail",      "x", statistic=8.0, p_value=0.001)
    vif_pass   = DiagnosticResult("vif",           "VIF",   "pass",      "x")
    white_pass = DiagnosticResult("white",         "White", "pass",      "x")
    jb_pass    = DiagnosticResult("jarque_bera",   "JB",    "pass",      "x")

    rng = np.random.default_rng(0)
    df = pd.DataFrame({"y": rng.normal(0, 1, 50), "x1": rng.normal(0, 1, 50), "x2": rng.normal(0, 1, 50)})
    model = estimate_ols(df, "y", ["x1", "x2"])

    report = build_remediation([bp_fail, reset_fail, vif_pass, white_pass, jb_pass], model)
    pattern_ids = {p.id for p in report.patterns}
    assert "spec_not_inference" in pattern_ids


def test_no_pattern_when_only_one_test_fails():
    """Single failure cannot trigger any two-test pattern."""
    from regassist.diagnostics import DiagnosticResult

    bp_fail   = DiagnosticResult("breusch_pagan", "BP",    "fail", "x", statistic=5.0, p_value=0.01)
    reset_pass = DiagnosticResult("ramsey_reset",  "RESET", "pass", "x")
    vif_pass   = DiagnosticResult("vif",           "VIF",   "pass", "x")
    white_pass = DiagnosticResult("white",         "White", "pass", "x")
    jb_pass    = DiagnosticResult("jarque_bera",   "JB",    "pass", "x")

    rng = np.random.default_rng(0)
    df = pd.DataFrame({"y": rng.normal(0, 1, 50), "x1": rng.normal(0, 1, 50), "x2": rng.normal(0, 1, 50)})
    model = estimate_ols(df, "y", ["x1", "x2"])

    report = build_remediation([bp_fail, reset_pass, vif_pass, white_pass, jb_pass], model)
    assert report.patterns == []


def test_outlier_misspec_pattern_fires():
    """Pattern 'outlier_misspec' requires RESET + JB both non-passing."""
    from regassist.diagnostics import DiagnosticResult

    reset_fail = DiagnosticResult("ramsey_reset", "RESET", "fail", "x", statistic=8.0, p_value=0.001)
    jb_fail    = DiagnosticResult("jarque_bera",  "JB",    "fail", "x", statistic=12.0, p_value=0.002)
    bp_pass    = DiagnosticResult("breusch_pagan","BP",    "pass", "x")
    white_pass = DiagnosticResult("white",        "White", "pass", "x")
    vif_pass   = DiagnosticResult("vif",          "VIF",   "pass", "x")

    rng = np.random.default_rng(0)
    df = pd.DataFrame({"y": rng.normal(0, 1, 50), "x1": rng.normal(0, 1, 50), "x2": rng.normal(0, 1, 50)})
    model = estimate_ols(df, "y", ["x1", "x2"])

    report = build_remediation([reset_fail, jb_fail, bp_pass, white_pass, vif_pass], model)
    pattern_ids = {p.id for p in report.patterns}
    assert "outlier_misspec" in pattern_ids


def test_pattern_triggered_by_borderline_counts_as_not_pass():
    """'not_pass' trigger should fire for borderline verdicts too."""
    from regassist.diagnostics import DiagnosticResult

    bp_borderline  = DiagnosticResult("breusch_pagan", "BP",    "borderline", "x", statistic=3.0, p_value=0.045)
    reset_fail     = DiagnosticResult("ramsey_reset",  "RESET", "fail",       "x", statistic=8.0, p_value=0.001)
    vif_pass       = DiagnosticResult("vif",           "VIF",   "pass",       "x")
    white_pass     = DiagnosticResult("white",         "White", "pass",       "x")
    jb_pass        = DiagnosticResult("jarque_bera",   "JB",    "pass",       "x")

    rng = np.random.default_rng(0)
    df = pd.DataFrame({"y": rng.normal(0, 1, 50), "x1": rng.normal(0, 1, 50), "x2": rng.normal(0, 1, 50)})
    model = estimate_ols(df, "y", ["x1", "x2"])

    report = build_remediation([bp_borderline, reset_fail, vif_pass, white_pass, jb_pass], model)
    pattern_ids = {p.id for p in report.patterns}
    assert "spec_not_inference" in pattern_ids


def test_patterns_have_required_fields():
    from regassist.diagnostics import DiagnosticResult

    bp_fail    = DiagnosticResult("breusch_pagan", "BP",    "fail", "x", statistic=5.0, p_value=0.01)
    reset_fail = DiagnosticResult("ramsey_reset",  "RESET", "fail", "x", statistic=8.0, p_value=0.001)
    others     = [
        DiagnosticResult("vif",         "VIF",   "pass", "x"),
        DiagnosticResult("white",       "White", "pass", "x"),
        DiagnosticResult("jarque_bera", "JB",    "pass", "x"),
    ]

    rng = np.random.default_rng(0)
    df = pd.DataFrame({"y": rng.normal(0, 1, 50), "x1": rng.normal(0, 1, 50), "x2": rng.normal(0, 1, 50)})
    model = estimate_ols(df, "y", ["x1", "x2"])

    report = build_remediation([bp_fail, reset_fail] + others, model)
    for p in report.patterns:
        assert p.id
        assert p.severity in ("high", "medium", "low")
        assert p.interpretation.strip()
        assert p.recommendation.strip()
        assert isinstance(p.triggered_by, list)
        assert len(p.triggered_by) > 0
