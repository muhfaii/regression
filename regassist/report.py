"""
Report builder — assembles ReportData from pipeline outputs and renders HTML.

Covers: FR-7.1 (in-browser HTML), spec section 10 (8 sections), section 11
(adaptive three-tier explanation layer: verdict / plain / technical collapsible).
NFR-8: numeric precision enforced here (3–4 dp coefficients, 4 dp p-values).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from regassist.diagnostics import DiagnosticResult
from regassist.estimate import BPLMResult, FittedModel, HausmanResult
from regassist.ingest import IngestResult
from regassist.pipeline import ModelSelectionStep, PipelineResult
from regassist.remediate import RemediationReport

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DescStat:
    variable: str
    mean: float
    std: float
    minimum: float
    median: float
    maximum: float
    missing: int


@dataclass
class CoeffRow:
    variable: str
    estimate: float     # 4 dp
    std_err: float      # 4 dp
    t_stat: float       # 3 dp
    p_value: float      # 4 dp
    ci_lower: float     # 4 dp
    ci_upper: float     # 4 dp
    significant: bool   # p < 0.05


@dataclass
class ReportData:
    # § 1  Data summary
    n_obs: int
    dep_var: str
    indep_vars: list[str]
    desc_stats: list[DescStat]
    missing_strategy: str | None      # None if no missing values

    # § 2  Specification
    model_equation: str               # e.g. "wage = β₀ + β₁·education + ε"

    # § 3  Model selection path
    model_type_label: str             # "OLS (cross-sectional)" | "Fixed Effects (FE)" | …
    model_selection_note: str

    # § 4  Regression results
    coefficients: list[CoeffRow]
    rsquared: float
    rsquared_adj: float
    fvalue: float
    f_pvalue: float

    # § 5  Diagnostics dashboard
    diagnostic_results: list[DiagnosticResult]

    # § 6-8  Issues / Recommendations / Caveats
    remediation: RemediationReport
    all_pass: bool                    # drives success-path framing (§ 10.2)

    # Panel-only extras (default to empty / None for cross-sectional reports)
    selection_steps: list[ModelSelectionStep] = field(default_factory=list)
    entity_col: str | None = None
    time_col: str | None = None
    bplm: BPLMResult | None = None
    hausman: HausmanResult | None = None


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_report_data(
    ingest_result: IngestResult,
    model: FittedModel,
    diag_results: list[DiagnosticResult],
    remediation: RemediationReport,
    missing_strategy: str | None = None,
    pipeline_result: PipelineResult | None = None,
) -> ReportData:
    """Assemble a ReportData from pipeline outputs.

    All numeric rounding to spec NFR-8 happens here, not in the template.

    Args:
        ingest_result:    Upload metadata (used for desc stats and data summary).
        model:            The chosen FittedModel.
        diag_results:     Diagnostic results for the chosen model.
        remediation:      Remediation report.
        missing_strategy: Strategy applied to handle missing data.
        pipeline_result:  Optional PipelineResult; when provided, the model
                          selection path (BP-LM, Hausman steps) is shown in § 3.
    """
    # For panel models the raw ingest df has entity/time cols; we only compute
    # desc stats for the dep var and indep vars.
    df_for_stats = ingest_result.df
    desc_stats = _compute_desc_stats(df_for_stats, model.dep_var, model.indep_vars)
    coefficients = _build_coeff_rows(model)
    equation = _build_equation(model.dep_var, model.indep_vars)
    all_pass = all(r.verdict == "pass" for r in diag_results)

    # § 3 label and note
    if pipeline_result is not None:
        label, note = _selection_label(model, pipeline_result)
        steps      = pipeline_result.selection_steps
        entity_col = pipeline_result.entity_col
        time_col   = pipeline_result.time_col
        bplm       = pipeline_result.bplm
        hausman    = pipeline_result.hausman
    else:
        label   = _model_type_label(model.model_type)
        note    = (
            "Data detected as cross-sectional. Pooled OLS was estimated directly. "
            "No panel model selection (Breusch-Pagan LM / Hausman) was required."
        )
        steps      = []
        entity_col = None
        time_col   = None
        bplm       = None
        hausman    = None

    return ReportData(
        n_obs=model.n_obs,
        dep_var=model.dep_var,
        indep_vars=model.indep_vars,
        desc_stats=desc_stats,
        missing_strategy=missing_strategy,
        model_equation=equation,
        model_type_label=label,
        model_selection_note=note,
        selection_steps=steps,
        entity_col=entity_col,
        time_col=time_col,
        bplm=bplm,
        hausman=hausman,
        coefficients=coefficients,
        rsquared=round(model.rsquared, 4),
        rsquared_adj=round(model.rsquared_adj, 4),
        fvalue=round(model.fvalue, 3),
        f_pvalue=round(model.f_pvalue, 4),
        diagnostic_results=diag_results,
        remediation=remediation,
        all_pass=all_pass,
    )


def build_report_data_from_pipeline(
    ingest_result: IngestResult,
    pipeline_result: PipelineResult,
    missing_strategy: str | None = None,
) -> ReportData:
    """Convenience wrapper: build ReportData directly from a PipelineResult."""
    return build_report_data(
        ingest_result=ingest_result,
        model=pipeline_result.model,
        diag_results=pipeline_result.diagnostics,
        remediation=pipeline_result.remediation,
        missing_strategy=missing_strategy,
        pipeline_result=pipeline_result,
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def render_html(report_data: ReportData) -> str:
    """Render the ReportData to a standalone HTML string."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    # Custom filters
    env.filters["fmt_p"] = lambda v: f"{v:.4f}" if v is not None else "—"
    env.filters["fmt_coef"] = lambda v: f"{v:.4f}" if v is not None else "—"
    env.filters["fmt_stat"] = lambda v: f"{v:.3f}" if v is not None else "—"
    env.filters["pct"] = lambda v: f"{v:.1f}%"

    template = env.get_template("report.html.j2")
    return template.render(r=report_data)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_desc_stats(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
) -> list[DescStat]:
    stats = []
    for col in [dep_var] + list(indep_vars):
        if col not in df.columns:
            continue
        s = df[col].dropna()
        stats.append(DescStat(
            variable=col,
            mean=round(float(s.mean()), 4),
            std=round(float(s.std()), 4),
            minimum=round(float(s.min()), 4),
            median=round(float(s.median()), 4),
            maximum=round(float(s.max()), 4),
            missing=int(df[col].isnull().sum()),
        ))
    return stats


def _build_coeff_rows(model: FittedModel) -> list[CoeffRow]:
    rows = []
    for var in model.params.index:
        rows.append(CoeffRow(
            variable=var,
            estimate=round(float(model.params[var]), 4),
            std_err=round(float(model.bse[var]), 4),
            t_stat=round(float(model.tvalues[var]), 3),
            p_value=round(float(model.pvalues[var]), 4),
            ci_lower=round(float(model.conf_int.loc[var, "lower_95"]), 4),
            ci_upper=round(float(model.conf_int.loc[var, "upper_95"]), 4),
            significant=float(model.pvalues[var]) < 0.05,
        ))
    return rows


def _build_equation(dep_var: str, indep_vars: list[str]) -> str:
    terms = " + ".join(f"β{i+1}·{v}" for i, v in enumerate(indep_vars))
    return f"{dep_var} = β₀ + {terms} + ε"


_MODEL_TYPE_LABELS = {
    "ols": "Pooled OLS",
    "fe":  "Fixed Effects (FE)",
    "re":  "Random Effects (RE)",
}


def _model_type_label(model_type: str) -> str:
    return _MODEL_TYPE_LABELS.get(model_type, model_type.upper())


def _selection_label(model: FittedModel, pr: PipelineResult) -> tuple[str, str]:
    """Return (model_type_label, model_selection_note) for panel pipeline results."""
    label = _model_type_label(model.model_type)

    lm = pr.bplm
    h  = pr.hausman

    if lm is None or lm.verdict == "pooled_ok":
        note = (
            f"BP-LM test: p = {lm.p_value:.4f} — failed to reject H₀. "
            "No individual effects detected; pooled OLS is appropriate."
        ) if lm else "Pooled OLS used (no BP-LM test result available)."
    elif h is None:
        note = (
            f"BP-LM test: p = {lm.p_value:.4f} — individual effects detected. "
            f"{label} selected."
        )
    else:
        verdict_label = {
            "fe_preferred": "FE preferred (H₀ rejected)",
            "re_preferred": "RE preferred (H₀ not rejected)",
            "borderline":   "borderline — FE chosen (conservative)",
        }.get(h.verdict, h.verdict)
        note = (
            f"BP-LM test: p = {lm.p_value:.4f} — individual effects detected. "
            f"Hausman test: χ²({h.dof}) = {h.statistic:.4f}, p = {h.p_value:.4f} — "
            f"{verdict_label}. Model selected: {label}."
        )
    return label, note
