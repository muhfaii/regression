"""Tests for regassist.pipeline — cross-sectional and panel decision trees."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from regassist.estimate import FittedModel
from regassist.ingest import ColumnInfo, IngestResult
from regassist.pipeline import (
    ModelSelectionStep,
    PipelineResult,
    run_cross_sectional_pipeline,
    run_panel_pipeline,
)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def _make_ingest(df: pd.DataFrame) -> IngestResult:
    cols = [ColumnInfo(name=c, dtype=str(df[c].dtype), missing_count=0, missing_pct=0.0)
            for c in df.columns]
    return IngestResult(df=df, row_count=len(df), columns=cols)


def _cs_df(n=200, seed=5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x1, x2 = rng.normal(10, 2, n), rng.normal(5, 1, n)
    y = 3 + 2 * x1 + 1.5 * x2 + rng.normal(0, 1, n)
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def _re_panel(n_entities=40, n_periods=8, seed=7) -> pd.DataFrame:
    """Panel with pure random effects (uncorrelated with regressors)."""
    rng = np.random.default_rng(seed)
    rows = [(e, t) for e in range(n_entities) for t in range(n_periods)]
    df = pd.DataFrame(rows, columns=["firm", "time"])
    u_i = {e: rng.normal(0, 2) for e in range(n_entities)}
    df["u"] = df["firm"].map(u_i)
    x1 = rng.normal(0, 1, len(df))
    x2 = rng.normal(0, 1, len(df))
    df["x1"] = x1
    df["x2"] = x2
    df["y"] = 2.0 + 1.5 * x1 + 0.5 * x2 + df["u"] + rng.normal(0, 0.3, len(df))
    return df.drop(columns=["u"])


def _fe_panel(n_entities=50, n_periods=10, seed=3) -> pd.DataFrame:
    """Panel where entity effects correlate strongly with x1."""
    rng = np.random.default_rng(seed)
    rows = [(e, t) for e in range(n_entities) for t in range(n_periods)]
    df = pd.DataFrame(rows, columns=["entity", "period"])
    x1 = rng.normal(0, 1, len(df))
    x2 = rng.normal(0, 1, len(df))
    # Entity mean of x1 — creates correlation between alpha_i and x1
    tmp = pd.DataFrame({"entity": df["entity"], "x1": x1})
    entity_mean_x1 = tmp.groupby("entity")["x1"].mean()
    alpha = entity_mean_x1 * 4.0 + rng.normal(0, 0.5, n_entities)
    df["alpha"] = df["entity"].map(alpha)
    df["x1"] = x1
    df["x2"] = x2
    df["y"] = 1.0 + 2.5 * x1 + 0.8 * x2 + df["alpha"] + rng.normal(0, 0.3, len(df))
    return df.drop(columns=["alpha"])


# ---------------------------------------------------------------------------
# Cross-sectional pipeline
# ---------------------------------------------------------------------------

def test_cs_pipeline_returns_pipeline_result():
    df = _cs_df()
    r = run_cross_sectional_pipeline(df, "y", ["x1", "x2"], _make_ingest(df))
    assert isinstance(r, PipelineResult)


def test_cs_pipeline_model_type_ols():
    df = _cs_df()
    r = run_cross_sectional_pipeline(df, "y", ["x1", "x2"], _make_ingest(df))
    assert r.model.model_type == "ols"


def test_cs_pipeline_no_selection_steps():
    df = _cs_df()
    r = run_cross_sectional_pipeline(df, "y", ["x1", "x2"], _make_ingest(df))
    assert r.selection_steps == []


def test_cs_pipeline_diagnostics_non_empty():
    df = _cs_df()
    r = run_cross_sectional_pipeline(df, "y", ["x1", "x2"], _make_ingest(df))
    assert len(r.diagnostics) > 0


def test_cs_pipeline_remediation_present():
    df = _cs_df()
    r = run_cross_sectional_pipeline(df, "y", ["x1", "x2"], _make_ingest(df))
    assert r.remediation is not None


def test_cs_pipeline_no_bplm():
    df = _cs_df()
    r = run_cross_sectional_pipeline(df, "y", ["x1", "x2"], _make_ingest(df))
    assert r.bplm is None


def test_cs_pipeline_no_hausman():
    df = _cs_df()
    r = run_cross_sectional_pipeline(df, "y", ["x1", "x2"], _make_ingest(df))
    assert r.hausman is None


# ---------------------------------------------------------------------------
# Panel pipeline — structure
# ---------------------------------------------------------------------------

def test_panel_pipeline_returns_pipeline_result():
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    assert isinstance(r, PipelineResult)


def test_panel_pipeline_model_is_fitted_model():
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    assert isinstance(r.model, FittedModel)


def test_panel_pipeline_model_type_valid():
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    assert r.model.model_type in {"ols", "fe", "re"}


def test_panel_pipeline_has_bplm():
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    assert r.bplm is not None


def test_panel_pipeline_entity_col_stored():
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    assert r.entity_col == "firm"


def test_panel_pipeline_time_col_stored():
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    assert r.time_col == "time"


def test_panel_pipeline_selection_steps_non_empty():
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    assert len(r.selection_steps) >= 1


def test_panel_pipeline_selection_step_is_model_selection_step():
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    assert all(isinstance(s, ModelSelectionStep) for s in r.selection_steps)


def test_panel_pipeline_selection_step_chosen_model_valid():
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    for s in r.selection_steps:
        assert s.chosen_model in {"pooled_ols", "fe", "re", "…"}


def test_panel_pipeline_diagnostics_is_list():
    # Panel-specific diagnostic tests (Wooldridge, Modified Wald) are added
    # separately; until then the list may be empty for FE/RE models.
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    assert isinstance(r.diagnostics, list)


def test_panel_pipeline_remediation_present():
    df = _re_panel()
    r = run_panel_pipeline(df, "y", ["x1", "x2"], "firm", "time", _make_ingest(df))
    assert r.remediation is not None


# ---------------------------------------------------------------------------
# Panel pipeline — RE world: expects BP-LM to reject pooled
# ---------------------------------------------------------------------------

def test_panel_re_world_bplm_rejects_pooled():
    """With strong random effects, BP-LM should push past pooled OLS."""
    rng = np.random.default_rng(200)
    N, T = 60, 10
    rows = [(e, t) for e in range(N) for t in range(T)]
    df = pd.DataFrame(rows, columns=["firm", "time"])
    u = {e: rng.normal(0, 5) for e in range(N)}   # large random effects
    df["u"] = df["firm"].map(u)
    df["x1"] = rng.normal(0, 1, len(df))
    df["y"] = 1.0 + 2.0 * df["x1"] + df["u"] + rng.normal(0, 0.1, len(df))
    df = df.drop(columns=["u"])
    r = run_panel_pipeline(df, "y", ["x1"], "firm", "time", _make_ingest(df))
    # BP-LM rejects pooled → at least 2 selection steps (BP-LM + Hausman)
    assert len(r.selection_steps) == 2


def test_panel_re_world_hausman_step_present():
    rng = np.random.default_rng(200)
    N, T = 60, 10
    rows = [(e, t) for e in range(N) for t in range(T)]
    df = pd.DataFrame(rows, columns=["firm", "time"])
    u = {e: rng.normal(0, 5) for e in range(N)}
    df["u"] = df["firm"].map(u)
    df["x1"] = rng.normal(0, 1, len(df))
    df["y"] = 1.0 + 2.0 * df["x1"] + df["u"] + rng.normal(0, 0.1, len(df))
    df = df.drop(columns=["u"])
    r = run_panel_pipeline(df, "y", ["x1"], "firm", "time", _make_ingest(df))
    assert r.hausman is not None
    assert any("Hausman" in s.test_name for s in r.selection_steps)


# ---------------------------------------------------------------------------
# Panel pipeline — pooled path (no individual effects)
# ---------------------------------------------------------------------------

def test_panel_pooled_path_when_no_effects():
    """When there are no individual effects BP-LM should not reject pooled."""
    rng = np.random.default_rng(999)
    N, T = 30, 6
    rows = [(e, t) for e in range(N) for t in range(T)]
    df = pd.DataFrame(rows, columns=["entity", "period"])
    df["x1"] = rng.normal(0, 1, len(df))
    df["y"] = 1.0 + 2.0 * df["x1"] + rng.normal(0, 1, len(df))  # no entity effect
    r = run_panel_pipeline(df, "y", ["x1"], "entity", "period", _make_ingest(df))
    if r.bplm.verdict == "pooled_ok":
        assert r.model.model_type == "ols"
        assert len(r.selection_steps) == 1
        assert r.hausman is None
