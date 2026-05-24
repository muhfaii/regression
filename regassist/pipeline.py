"""
Regression pipelines — encapsulate the decision trees for cross-sectional
and panel data so app.py just calls the right pipeline and gets a uniform
result object.

Cross-sectional pipeline:
    estimate_ols → run_diagnostics → build_remediation

Panel pipeline (FR-4.2):
    estimate_ols (pooled) → BP-LM test
        ├── pooled_ok  → use pooled OLS
        └── re_preferred → estimate_fe + estimate_re → Hausman test
                ├── fe_preferred  → use FE model
                ├── borderline    → use FE model, flag borderline
                └── re_preferred  → use RE model

Covers: FR-4.2, spec §6 (model selection path).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .diagnostics import DiagnosticResult, run_diagnostics
from .estimate import (
    BPLMResult,
    FittedModel,
    HausmanResult,
    bp_lm_test,
    estimate_fe,
    estimate_ols,
    estimate_re,
    hausman_test,
)
from .ingest import IngestResult
from .remediate import RemediationReport, build_remediation
from .robust_se import (
    apply_cr,
    apply_hc,
    get_hat_values,
    select_cr_variant,
    select_hc_variant,
)

import pandas as pd

# Diagnostic IDs that trigger robust SE application
_HETERO_TESTS = {"breusch_pagan", "white"}
_CLUSTER_TESTS = {"wooldridge", "modified_wald"}


@dataclass
class ModelSelectionStep:
    """One step in the model selection decision log (shown in report section 3)."""
    test_name: str          # e.g. "BP-LM test", "Hausman test"
    statistic: float | None
    p_value: float | None
    verdict: str            # human-readable outcome label
    chosen_model: str       # "pooled_ols" | "fe" | "re"
    note: str


@dataclass
class PipelineResult:
    """Unified result returned by both pipelines."""
    model: FittedModel
    diagnostics: list[DiagnosticResult]
    remediation: RemediationReport
    selection_steps: list[ModelSelectionStep] = field(default_factory=list)
    # Panel-specific test results (None for cross-sectional)
    bplm: BPLMResult | None = None
    # User-facing warnings (e.g. absorbed variables in FE, few-cluster)
    warnings: list[str] = field(default_factory=list)
    hausman: HausmanResult | None = None
    # The entity/time column names (panel only)
    entity_col: str | None = None
    time_col: str | None = None
    # Robust SE override passed from app.py (e.g. "HC3", "CR1", or None/"Auto")
    robust_se_override: str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_cross_sectional_pipeline(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
    ingest_result: IngestResult,
    missing_strategy: str | None = None,
    robust_se_override: str | None = None,
) -> PipelineResult:
    """Fit pooled OLS and run all cross-sectional diagnostics.

    When BP or White rejects homoskedasticity (test-driven policy), selects
    an HC variant (HC1 or HC3 based on n and leverage) and returns a model
    with robust standard errors.

    Args:
        df:                 Clean DataFrame (post missing-data strategy).
        dep_var:            Dependent variable column name.
        indep_vars:         Independent variable column names.
        ingest_result:      IngestResult from the upload step (for the report).
        missing_strategy:   Strategy that was applied ("listwise", "mean", None).
        robust_se_override: Force a specific HC variant ("HC0"–"HC3"), or
                            None/"Auto" for automatic selection.

    Returns:
        PipelineResult with model (HC-corrected if triggered).
    """
    model = estimate_ols(df, dep_var, indep_vars)
    diag  = run_diagnostics(model)

    # Test-driven policy: apply HC when any heteroskedasticity test fails/borderline
    hetero_fired = any(
        r.test_id in _HETERO_TESTS and r.verdict != "pass"
        for r in diag
    )
    if hetero_fired:
        hat_vals = get_hat_values(model)
        selection = select_hc_variant(
            n=model.n_obs,
            k=model.n_params,
            hat_values=hat_vals,
            override=robust_se_override,
        )
        model = apply_hc(model, selection)

    remed = build_remediation(diag, model)
    return PipelineResult(
        model=model,
        diagnostics=diag,
        remediation=remed,
        selection_steps=[],
        robust_se_override=robust_se_override,
    )


def run_panel_pipeline(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
    entity_col: str,
    time_col: str,
    ingest_result: IngestResult,
    missing_strategy: str | None = None,
    robust_se_override: str | None = None,
) -> PipelineResult:
    """Panel decision tree: pooled OLS → BP-LM → FE+RE → Hausman.

    Decision logic
    ──────────────
    1. Fit pooled OLS; run BP-LM test.
       - BP-LM pooled_ok  → keep pooled OLS; stop.
    2. BP-LM re_preferred → fit FE and RE; run Hausman test.
       - fe_preferred   → use FE model.
       - borderline     → use FE model, flag as borderline in selection log.
       - re_preferred   → use RE model.
    3. Run panel diagnostics on the chosen model.

    Args:
        df:               Clean DataFrame (post missing-data strategy).
        dep_var:          Dependent variable column name.
        indep_vars:       Independent variable column names
                          (must NOT include entity_col or time_col).
        entity_col:         Column identifying entities.
        time_col:           Column identifying time periods.
        ingest_result:      IngestResult from the upload step.
        missing_strategy:   Strategy that was applied.
        robust_se_override: Force a specific CR variant ("CR0"–"CR2"), or
                            None/"Auto" for automatic selection.

    Returns:
        PipelineResult with the chosen model and full selection log.
    """
    selection_steps: list[ModelSelectionStep] = []

    # ── Step 1: Pooled OLS + BP-LM ──────────────────────────────────────────
    pooled = estimate_ols(df, dep_var, indep_vars)
    lm     = bp_lm_test(df, dep_var, indep_vars, entity_col, time_col)

    selection_steps.append(ModelSelectionStep(
        test_name="BP-LM test (pooled OLS vs Random Effects)",
        statistic=lm.statistic,
        p_value=lm.p_value,
        verdict=_bplm_label(lm),
        chosen_model="pooled_ols" if lm.verdict == "pooled_ok" else "…",
        note=lm.note,
    ))

    if lm.verdict == "pooled_ok":
        diag   = run_diagnostics(pooled)
        pooled = _maybe_apply_hc(pooled, diag, robust_se_override)
        remed  = build_remediation(diag, pooled)
        selection_steps[0].chosen_model = "pooled_ols"
        return PipelineResult(
            model=pooled,
            diagnostics=diag,
            remediation=remed,
            selection_steps=selection_steps,
            bplm=lm,
            entity_col=entity_col,
            time_col=time_col,
            robust_se_override=robust_se_override,
        )

    # ── Step 2: FE + RE + Hausman ────────────────────────────────────────────
    fe_model = estimate_fe(df, dep_var, indep_vars, entity_col, time_col)

    pipeline_warnings: list[str] = []
    if fe_model.absorbed_vars:
        n = len(fe_model.absorbed_vars)
        names = ", ".join(fe_model.absorbed_vars)
        pipeline_warnings.append(
            f"**Fixed Effects: {n} time-invariant variable(s) automatically dropped.** "
            f"Entity fixed effects absorb variables that do not change within an entity "
            f"(e.g. sector, location, or other time-invariant characteristics). "
            f"These variables were excluded from the FE estimation: {names}. "
            f"If you need to estimate their coefficients, use Random Effects or pooled OLS."
        )

    try:
        re_model = estimate_re(df, dep_var, indep_vars, entity_col, time_col)
    except Exception as re_exc:
        # RE estimation failed (e.g. degenerate variance components when some
        # entities have very few time periods).  Fall back to FE and warn the user.
        pipeline_warnings.append(
            f"**Random Effects estimation failed ({re_exc}) — Fixed Effects model used.** "
            "This usually happens when the panel is highly unbalanced or some entities "
            "have only one observation, making the between-entity variance component "
            "impossible to estimate. Fixed Effects avoids this by differencing out "
            "entity-level variation entirely."
        )
        selection_steps.append(ModelSelectionStep(
            test_name="Hausman test (Fixed Effects vs Random Effects)",
            statistic=None,
            p_value=None,
            verdict="RE estimation failed — FE used as fallback",
            chosen_model="fe",
            note=f"Random Effects could not be estimated: {re_exc}",
        ))
        diag     = run_diagnostics(fe_model)
        fe_model, cr_warn = _maybe_apply_cr(fe_model, diag, robust_se_override)
        if cr_warn:
            pipeline_warnings.append(cr_warn)
        remed = build_remediation(diag, fe_model)
        return PipelineResult(
            model=fe_model,
            diagnostics=diag,
            remediation=remed,
            selection_steps=selection_steps,
            bplm=lm,
            hausman=None,
            entity_col=entity_col,
            time_col=time_col,
            warnings=pipeline_warnings,
            robust_se_override=robust_se_override,
        )

    if re_model.absorbed_vars:
        n = len(re_model.absorbed_vars)
        names = ", ".join(re_model.absorbed_vars)
        pipeline_warnings.append(
            f"**Random Effects: {n} variable(s) dropped due to perfect multicollinearity.** "
            f"After adding the intercept, these columns became linearly dependent "
            f"(e.g. a set of dummy variables that sums to 1 — the dummy variable trap). "
            f"Dropped: {names}. "
            f"Consider removing one reference category from each dummy group."
        )

    h = hausman_test(fe_model, re_model)

    if h.verdict in ("fe_preferred", "borderline"):
        chosen      = fe_model
        chosen_name = "fe"
    else:
        chosen      = re_model
        chosen_name = "re"

    selection_steps.append(ModelSelectionStep(
        test_name="Hausman test (Fixed Effects vs Random Effects)",
        statistic=h.statistic,
        p_value=h.p_value,
        verdict=_hausman_label(h),
        chosen_model=chosen_name,
        note=h.note,
    ))

    diag            = run_diagnostics(chosen)
    chosen, cr_warn = _maybe_apply_cr(chosen, diag, robust_se_override)
    if cr_warn:
        pipeline_warnings.append(cr_warn)
    remed = build_remediation(diag, chosen)

    return PipelineResult(
        model=chosen,
        diagnostics=diag,
        remediation=remed,
        selection_steps=selection_steps,
        bplm=lm,
        hausman=h,
        entity_col=entity_col,
        time_col=time_col,
        warnings=pipeline_warnings,
        robust_se_override=robust_se_override,
    )


# ---------------------------------------------------------------------------
# Robust SE helpers
# ---------------------------------------------------------------------------

def _maybe_apply_hc(
    model: FittedModel,
    diag: list[DiagnosticResult],
    override: str | None,
) -> FittedModel:
    """Apply HC robust SEs if any heteroskedasticity test is non-passing."""
    hetero_fired = any(
        r.test_id in _HETERO_TESTS and r.verdict != "pass" for r in diag
    )
    if not hetero_fired:
        return model
    hat_vals = get_hat_values(model)
    selection = select_hc_variant(
        n=model.n_obs,
        k=model.n_params,
        hat_values=hat_vals,
        override=override,
    )
    return apply_hc(model, selection)


def _maybe_apply_cr(
    model: FittedModel,
    diag: list[DiagnosticResult],
    override: str | None,
) -> tuple[FittedModel, str | None]:
    """Apply CR robust SEs if any cluster-relevant test is non-passing.

    Returns the (possibly updated) model and an optional few-cluster warning.
    """
    cluster_fired = any(
        r.test_id in _CLUSTER_TESTS and r.verdict != "pass" for r in diag
    )
    if not cluster_fired:
        return model, None
    n_clusters = model.X.index.get_level_values(0).nunique()
    selection = select_cr_variant(n_clusters=n_clusters, override=override)
    updated = apply_cr(model, selection)
    return updated, selection.few_cluster_warning


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------

def _bplm_label(lm: BPLMResult) -> str:
    if lm.verdict == "pooled_ok":
        return f"p = {lm.p_value:.4f} — fail to reject H₀; use pooled OLS"
    return f"p = {lm.p_value:.4f} — reject H₀; individual effects present"


def _hausman_label(h: HausmanResult) -> str:
    if h.verdict == "fe_preferred":
        return f"p = {h.p_value:.4f} — reject H₀; FE preferred"
    if h.verdict == "borderline":
        return f"p = {h.p_value:.4f} — borderline; FE chosen (conservative)"
    if h.verdict == "re_preferred":
        return f"p = {h.p_value:.4f} — fail to reject H₀; RE preferred"
    return "inconclusive (negative statistic); defaulting to RE"
