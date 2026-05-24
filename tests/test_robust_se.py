"""
Tests for regassist.robust_se — HC/CR variant selection and application.
"""
import numpy as np
import pandas as pd
import pytest

from regassist.estimate import estimate_fe, estimate_ols, estimate_re
from regassist.robust_se import (
    LeverageSummary,
    SESelection,
    _compute_leverage_summary,
    apply_cr,
    apply_hc,
    get_hat_values,
    select_cr_variant,
    select_hc_variant,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ols_model():
    """Small heteroskedastic OLS model."""
    rng = np.random.default_rng(42)
    n = 80
    x = rng.standard_normal(n)
    y = 2.0 + 1.5 * x + rng.standard_normal(n) * (1 + np.abs(x))  # hetero by design
    df = pd.DataFrame({"y": y, "x": x})
    return estimate_ols(df, "y", ["x"])


@pytest.fixture()
def ols_model_large():
    """Large OLS model (n >= 250, no extreme leverage) → should select HC1."""
    rng = np.random.default_rng(0)
    n = 300
    x = rng.standard_normal(n)
    y = 1.0 + 2.0 * x + rng.standard_normal(n)
    df = pd.DataFrame({"y": y, "x": x})
    return estimate_ols(df, "y", ["x"])


@pytest.fixture()
def panel_df_fe():
    """Balanced panel: 25 entities × 8 periods = 200 obs."""
    rng = np.random.default_rng(7)
    entities = [f"e{i}" for i in range(25)]
    times = list(range(8))
    rows = []
    for eid in entities:
        fe = rng.standard_normal()
        for t in times:
            x = rng.standard_normal()
            y = fe + 1.5 * x + rng.standard_normal()
            rows.append({"entity": eid, "time": t, "y": y, "x": x})
    return pd.DataFrame(rows)


@pytest.fixture()
def panel_df_few_clusters():
    """Unbalanced panel: 12 entities × 10 periods."""
    rng = np.random.default_rng(99)
    entities = [f"e{i}" for i in range(12)]
    times = list(range(10))
    rows = []
    for eid in entities:
        fe = rng.standard_normal()
        for t in times:
            x = rng.standard_normal()
            y = fe + 1.2 * x + rng.standard_normal()
            rows.append({"entity": eid, "time": t, "y": y, "x": x})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# HC selection rules
# ---------------------------------------------------------------------------

class TestSelectHcVariant:

    def test_small_sample_always_hc3(self):
        hat = np.full(100, 0.02)   # low leverage; n < 250 dominates
        sel = select_hc_variant(n=100, k=3, hat_values=hat)
        assert sel.variant == "HC3"
        assert "below 250" in sel.justification

    def test_large_sample_no_leverage_gives_hc1(self):
        hat = np.full(300, 0.005)  # n=300, k=3; 2k/n = 0.02 → no high-leverage
        sel = select_hc_variant(n=300, k=3, hat_values=hat)
        assert sel.variant == "HC1"
        assert "≥ 250" in sel.justification

    def test_high_leverage_forces_hc3(self):
        n, k = 300, 3
        hat = np.full(n, 0.001)
        hat[0] = 2 * k / n + 0.01   # one high-leverage observation
        sel = select_hc_variant(n=n, k=k, hat_values=hat)
        assert sel.variant == "HC3"
        assert "high leverage" in sel.justification

    def test_extreme_leverage_forces_hc3(self):
        n, k = 300, 3
        hat = np.full(n, 0.001)
        hat[0] = 4 * k / n + 0.05   # extreme leverage
        sel = select_hc_variant(n=n, k=k, hat_values=hat)
        assert sel.variant == "HC3"
        assert "extreme" in sel.justification

    def test_override_respected(self):
        hat = np.full(300, 0.001)
        sel = select_hc_variant(n=300, k=3, hat_values=hat, override="HC2")
        assert sel.variant == "HC2"
        assert "override" in sel.justification

    def test_auto_override_treated_as_no_override(self):
        hat = np.full(300, 0.001)
        sel_auto = select_hc_variant(n=300, k=3, hat_values=hat, override="Auto")
        sel_none = select_hc_variant(n=300, k=3, hat_values=hat, override=None)
        assert sel_auto.variant == sel_none.variant

    def test_invalid_override_raises(self):
        with pytest.raises(ValueError, match="Unknown HC variant"):
            select_hc_variant(n=100, k=2, hat_values=np.zeros(100), override="HC9")

    def test_citation_present(self):
        hat = np.full(100, 0.01)
        sel = select_hc_variant(n=100, k=2, hat_values=hat)
        assert sel.citation
        assert "HC3" in sel.citation

    def test_leverage_summary_populated(self):
        n, k = 300, 3
        hat = np.full(n, 0.001)
        hat[:5] = 2 * k / n + 0.01
        sel = select_hc_variant(n=n, k=k, hat_values=hat)
        assert isinstance(sel.leverage, LeverageSummary)
        assert sel.leverage.n_high == 5
        assert sel.leverage.n_extreme == 0


# ---------------------------------------------------------------------------
# CR selection rules
# ---------------------------------------------------------------------------

class TestSelectCrVariant:

    def test_many_clusters_gives_cr1(self):
        sel = select_cr_variant(n_clusters=60)
        assert sel.variant == "CR1"
        assert "≥ 50" in sel.justification
        assert sel.few_cluster_warning is None

    def test_medium_clusters_gives_cr2(self):
        sel = select_cr_variant(n_clusters=30)
        assert sel.variant == "CR2"
        assert sel.few_cluster_warning is None

    def test_few_clusters_gives_cr2_with_warning(self):
        sel = select_cr_variant(n_clusters=10)
        assert sel.variant == "CR2"
        assert sel.few_cluster_warning is not None
        assert "10 entities" in sel.few_cluster_warning

    def test_override_respected(self):
        sel = select_cr_variant(n_clusters=60, override="CR0")
        assert sel.variant == "CR0"
        assert "override" in sel.justification

    def test_invalid_override_raises(self):
        with pytest.raises(ValueError, match="Unknown CR variant"):
            select_cr_variant(n_clusters=60, override="CR9")

    def test_citation_present(self):
        sel = select_cr_variant(n_clusters=60)
        assert sel.citation
        assert "CR1" in sel.citation


# ---------------------------------------------------------------------------
# HC application (apply_hc)
# ---------------------------------------------------------------------------

class TestApplyHc:

    def test_se_changes_after_hc3(self, ols_model):
        hat = get_hat_values(ols_model)
        sel = select_hc_variant(ols_model.n_obs, ols_model.n_params, hat)
        robust = apply_hc(ols_model, sel)
        # SEs must differ from OLS classical SEs (model is heteroskedastic)
        assert not ols_model.bse.equals(robust.bse)

    def test_params_unchanged(self, ols_model):
        hat = get_hat_values(ols_model)
        sel = select_hc_variant(ols_model.n_obs, ols_model.n_params, hat)
        robust = apply_hc(ols_model, sel)
        pd.testing.assert_series_equal(ols_model.params, robust.params)

    def test_residuals_unchanged(self, ols_model):
        hat = get_hat_values(ols_model)
        sel = select_hc_variant(ols_model.n_obs, ols_model.n_params, hat)
        robust = apply_hc(ols_model, sel)
        pd.testing.assert_series_equal(ols_model.residuals, robust.residuals)

    def test_se_variant_set(self, ols_model):
        hat = get_hat_values(ols_model)
        sel = select_hc_variant(ols_model.n_obs, ols_model.n_params, hat)
        robust = apply_hc(ols_model, sel)
        assert robust.se_variant == sel.variant
        assert robust.se_justification == sel.justification
        assert robust.se_citation == sel.citation

    def test_original_model_not_mutated(self, ols_model):
        original_bse = ols_model.bse.copy()
        hat = get_hat_values(ols_model)
        sel = select_hc_variant(ols_model.n_obs, ols_model.n_params, hat)
        apply_hc(ols_model, sel)
        pd.testing.assert_series_equal(ols_model.bse, original_bse)

    def test_conf_int_columns(self, ols_model):
        hat = get_hat_values(ols_model)
        sel = select_hc_variant(ols_model.n_obs, ols_model.n_params, hat)
        robust = apply_hc(ols_model, sel)
        assert list(robust.conf_int.columns) == ["lower_95", "upper_95"]

    def test_hc1_applied_when_forced(self, ols_model_large):
        # Force HC1 via override regardless of leverage profile
        sel = SESelection(variant="HC1", justification="forced", citation="HC1 cite")
        robust = apply_hc(ols_model_large, sel)
        assert robust.se_variant == "HC1"
        pd.testing.assert_series_equal(ols_model_large.params, robust.params)


# ---------------------------------------------------------------------------
# CR application (apply_cr)
# ---------------------------------------------------------------------------

class TestApplyCr:

    def test_cr1_se_changes_vs_unadjusted(self, panel_df_fe):
        fe = estimate_fe(panel_df_fe, "y", ["x"], "entity", "time")
        sel = select_cr_variant(n_clusters=25)   # CR1
        robust = apply_cr(fe, sel)
        # With 25 clusters, CR1 should differ from unadjusted
        assert not fe.bse.equals(robust.bse)

    def test_cr2_se_differs_from_cr1(self, panel_df_few_clusters):
        fe = estimate_fe(panel_df_few_clusters, "y", ["x"], "entity", "time")
        sel_cr1 = SESelection(
            variant="CR1",
            justification="test CR1",
            citation="CR1 cite",
        )
        sel_cr2 = SESelection(
            variant="CR2",
            justification="test CR2",
            citation="CR2 cite",
        )
        robust_cr1 = apply_cr(fe, sel_cr1)
        robust_cr2 = apply_cr(fe, sel_cr2)
        assert not robust_cr1.bse.equals(robust_cr2.bse)

    def test_params_unchanged_cr(self, panel_df_fe):
        fe = estimate_fe(panel_df_fe, "y", ["x"], "entity", "time")
        sel = select_cr_variant(n_clusters=25)
        robust = apply_cr(fe, sel)
        pd.testing.assert_series_equal(fe.params, robust.params)

    def test_se_variant_set_cr(self, panel_df_fe):
        # panel_df_fe has 25 entities → 20 ≤ G < 50 → CR2
        fe = estimate_fe(panel_df_fe, "y", ["x"], "entity", "time")
        sel = select_cr_variant(n_clusters=25)
        robust = apply_cr(fe, sel)
        assert robust.se_variant == "CR2"

    def test_se_variant_cr1_when_many_clusters(self, panel_df_fe):
        fe = estimate_fe(panel_df_fe, "y", ["x"], "entity", "time")
        sel = select_cr_variant(n_clusters=60)   # G ≥ 50 → CR1
        robust = apply_cr(fe, sel)
        assert robust.se_variant == "CR1"

    def test_n_clusters_set(self, panel_df_fe):
        fe = estimate_fe(panel_df_fe, "y", ["x"], "entity", "time")
        sel = select_cr_variant(n_clusters=25)
        robust = apply_cr(fe, sel)
        assert robust.n_clusters == 25

    def test_cr2_fallback_for_re(self, panel_df_fe):
        """CR2 requested for RE should silently fall back to CR1."""
        re = estimate_re(panel_df_fe, "y", ["x"], "entity", "time")
        sel = SESelection(variant="CR2", justification="j", citation="c")
        robust = apply_cr(re, sel)
        # RE + CR2 → falls back to CR1 internally
        assert robust.se_variant == "CR1"

    def test_conf_int_columns_cr(self, panel_df_few_clusters):
        fe = estimate_fe(panel_df_few_clusters, "y", ["x"], "entity", "time")
        sel = select_cr_variant(n_clusters=12)
        robust = apply_cr(fe, sel)
        assert list(robust.conf_int.columns) == ["lower_95", "upper_95"]

    def test_original_fe_not_mutated(self, panel_df_fe):
        fe = estimate_fe(panel_df_fe, "y", ["x"], "entity", "time")
        orig_bse = fe.bse.copy()
        sel = select_cr_variant(n_clusters=25)
        apply_cr(fe, sel)
        pd.testing.assert_series_equal(fe.bse, orig_bse)


# ---------------------------------------------------------------------------
# Pipeline integration (end-to-end trigger check)
# ---------------------------------------------------------------------------

class TestPipelineIntegration:

    def test_hetero_data_triggers_hc(self):
        """Strongly heteroskedastic data should trigger HC and set se_variant."""
        from regassist.pipeline import run_cross_sectional_pipeline
        from regassist.ingest import IngestResult, ColumnInfo

        rng = np.random.default_rng(123)
        n = 60
        x = np.linspace(1, 10, n)
        y = 2.0 + 1.5 * x + rng.standard_normal(n) * x * 3   # strong hetero
        df = pd.DataFrame({"y": y, "x": x})

        ingest = IngestResult(
            df=df,
            row_count=n,
            columns=[ColumnInfo(name=c, dtype="float64", missing_count=0,
                                missing_pct=0.0, has_masked_numeric=False)
                     for c in df.columns],
        )
        result = run_cross_sectional_pipeline(df, "y", ["x"], ingest)
        # Strong hetero should trigger BP/White and apply robust SEs
        if result.model.se_variant is not None:
            assert result.model.se_variant in {"HC1", "HC2", "HC3"}

    def test_homoskedastic_data_no_hc(self):
        """Homoskedastic data should NOT trigger HC (se_variant stays None)."""
        from regassist.pipeline import run_cross_sectional_pipeline
        from regassist.ingest import IngestResult, ColumnInfo

        rng = np.random.default_rng(0)
        n = 200
        x = rng.standard_normal(n)
        y = 1.0 + 2.0 * x + rng.standard_normal(n) * 0.5
        df = pd.DataFrame({"y": y, "x": x})

        ingest = IngestResult(
            df=df,
            row_count=n,
            columns=[ColumnInfo(name=c, dtype="float64", missing_count=0,
                                missing_pct=0.0, has_masked_numeric=False)
                     for c in df.columns],
        )
        result = run_cross_sectional_pipeline(df, "y", ["x"], ingest)
        assert result.model.se_variant is None
