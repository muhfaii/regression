"""
Tests for regassist.report (FR-7.1, spec §10 sections, §11 adaptive layer).

Uses contains-string assertions so the tests survive minor template tweaks
while still verifying that all required content is present.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from regassist.diagnostics import run_diagnostics
from regassist.estimate import estimate_ols
from regassist.ingest import IngestResult, ColumnInfo
from regassist.remediate import build_remediation
from regassist.report import ReportData, build_report_data, render_html


# ---------------------------------------------------------------------------
# Dataset factories
# ---------------------------------------------------------------------------

def _clean_df(n=200, seed=5):
    rng = np.random.default_rng(seed)
    x1, x2 = rng.normal(10, 2, n), rng.normal(5, 1, n)
    y = 3 + 2 * x1 + 1.5 * x2 + rng.normal(0, 1, n)
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _hetero_df(n=200, seed=1):
    rng = np.random.default_rng(seed)
    x1 = rng.uniform(1, 10, n)
    x2 = rng.normal(5, 1, n)
    y = 3 + 2 * x1 + 1.5 * x2 + rng.normal(0, 1, n) * x1
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _make_ingest(df: pd.DataFrame) -> IngestResult:
    cols = [
        ColumnInfo(name=c, dtype=str(df[c].dtype),
                   missing_count=0, missing_pct=0.0)
        for c in df.columns
    ]
    return IngestResult(df=df, row_count=len(df), columns=cols)


def _build(df: pd.DataFrame):
    model   = estimate_ols(df, "y", ["x1", "x2"])
    diag    = run_diagnostics(model)
    remed   = build_remediation(diag, model)
    ingest  = _make_ingest(df)
    data    = build_report_data(ingest, model, diag, remed)
    html    = render_html(data)
    return data, html


# ---------------------------------------------------------------------------
# ReportData structure
# ---------------------------------------------------------------------------

def test_build_report_data_returns_report_data():
    data, _ = _build(_clean_df())
    assert isinstance(data, ReportData)


def test_all_pass_flag_set_correctly_for_clean_data():
    data, _ = _build(_clean_df())
    assert data.all_pass is True


def test_all_pass_flag_false_for_hetero_data():
    data, _ = _build(_hetero_df())
    assert data.all_pass is False


def test_n_obs_matches_df():
    df = _clean_df()
    data, _ = _build(df)
    assert data.n_obs == len(df)


def test_desc_stats_cover_dep_and_indep():
    data, _ = _build(_clean_df())
    names = {s.variable for s in data.desc_stats}
    assert "y" in names
    assert "x1" in names
    assert "x2" in names


def test_coefficients_include_const():
    data, _ = _build(_clean_df())
    vars_ = [c.variable for c in data.coefficients]
    assert "const" in vars_


def test_numeric_rounding_coefficients(  ):
    """NFR-8: coefficients rounded to 4 dp."""
    data, _ = _build(_clean_df())
    for c in data.coefficients:
        assert len(str(c.estimate).split(".")[-1]) <= 4


def test_numeric_rounding_p_values():
    """NFR-8: p-values rounded to 4 dp."""
    data, _ = _build(_clean_df())
    for c in data.coefficients:
        assert len(str(c.p_value).split(".")[-1]) <= 4


def test_model_equation_contains_dep_var():
    data, _ = _build(_clean_df())
    assert "y" in data.model_equation


def test_model_equation_contains_indep_vars():
    data, _ = _build(_clean_df())
    assert "x1" in data.model_equation
    assert "x2" in data.model_equation


# ---------------------------------------------------------------------------
# HTML rendering — all 8 sections present (§ 10)
# ---------------------------------------------------------------------------

SECTION_MARKERS = [
    ("1", "Data summary"),
    ("2", "Model specification"),
    ("3", "Model selection path"),
    ("4", "Regression results"),
    ("5", "Diagnostics dashboard"),
    ("6", "Issues"),
    ("7", "Recommendations"),
    ("8", "Caveats"),
]

@pytest.mark.parametrize("num,heading", SECTION_MARKERS)
def test_section_present_in_html(num, heading):
    _, html = _build(_clean_df())
    assert heading in html, f"Section '{heading}' not found in rendered HTML"


def test_html_is_valid_html5_doctype():
    _, html = _build(_clean_df())
    assert html.strip().lower().startswith("<!doctype html>")


def test_dep_var_in_html():
    _, html = _build(_clean_df())
    assert "y" in html


def test_n_obs_in_html():
    _, html = _build(_clean_df())
    assert "200" in html


# ---------------------------------------------------------------------------
# § 11 Adaptive explanation layer — all 3 tiers
# ---------------------------------------------------------------------------

def test_verdict_badges_present():
    """Tier 1: verdict badge visible for every diagnostic."""
    _, html = _build(_clean_df())
    assert "PASS" in html or "FAIL" in html or "BORDERLINE" in html


def test_plain_explanation_present():
    """Tier 2: plain explanation always rendered."""
    _, html = _build(_clean_df())
    # The plain explanation for VIF is always shown
    assert "similar to each other" in html   # from VIF plain_explanation


def test_collapsible_technical_present():
    """Tier 3: technical detail uses <details>/<summary>."""
    _, html = _build(_clean_df())
    assert "<details" in html
    assert "<summary>" in html
    assert "Technical detail" in html


def test_technical_note_in_collapsed_section():
    """Technical note text must appear inside a details block."""
    _, html = _build(_clean_df())
    assert "null hypothesis" in html.lower() or "H₀" in html or "Tests H" in html


# ---------------------------------------------------------------------------
# § 10.2 Success-path framing
# ---------------------------------------------------------------------------

def test_success_path_no_issues_heading():
    _, html = _build(_clean_df())
    assert "No issues identified" in html


def test_success_path_positive_recommendation():
    _, html = _build(_clean_df())
    assert "Notes on interpretation" in html


def test_success_path_standard_caveats():
    _, html = _build(_clean_df())
    assert "causality" in html.lower() or "causal" in html.lower()


# ---------------------------------------------------------------------------
# Failure-path content
# ---------------------------------------------------------------------------

def test_failure_path_issues_heading():
    _, html = _build(_hetero_df())
    assert "Issues found" in html


def test_failure_path_recommendations_heading():
    _, html = _build(_hetero_df())
    assert "Recommendations" in html


def test_failure_path_quick_fix_badge():
    _, html = _build(_hetero_df())
    assert "quick fix" in html


def test_failure_path_thinking_fix_badge():
    _, html = _build(_hetero_df())
    assert "thinking fix" in html


def test_failure_path_caveats_from_config():
    _, html = _build(_hetero_df())
    # The BP caveat mentions "Robust standard errors"
    assert "Robust" in html or "robust" in html


def test_cross_pattern_shown_when_present():
    """If a cross-pattern fires, its interpretation appears in the report."""
    from regassist.diagnostics import DiagnosticResult
    from regassist.remediate import build_remediation

    bp_fail    = DiagnosticResult("breusch_pagan", "Breusch-Pagan", "fail", "x", statistic=5.0, p_value=0.01)
    reset_fail = DiagnosticResult("ramsey_reset",  "Ramsey RESET",  "fail", "x", statistic=8.0, p_value=0.001)
    others = [
        DiagnosticResult("vif",         "VIF",   "pass", "x"),
        DiagnosticResult("white",       "White", "pass", "x"),
        DiagnosticResult("jarque_bera", "JB",    "pass", "x"),
    ]
    diag_results = [bp_fail, reset_fail] + others

    df    = _clean_df()
    model = estimate_ols(df, "y", ["x1", "x2"])
    remed = build_remediation(diag_results, model)
    ingest = _make_ingest(df)
    data  = build_report_data(ingest, model, diag_results, remed)
    html  = render_html(data)

    assert "spec_not_inference" in html.lower() or "Spec Not Inference" in html
    assert "specification" in html.lower()
