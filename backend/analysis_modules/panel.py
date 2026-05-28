"""Panel regression wrapper — FE/RE/Pooled OLS via regassist pipeline.

Maps regassist.pipeline.PipelineResult → backend.analysis_modules.base.AnalysisResult.
"""
from __future__ import annotations

import pandas as pd
from regassist.ingest import IngestResult, ColumnInfo as IngestColumnInfo
from regassist.pipeline import run_panel_pipeline

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation

_VERDICT_MAP = {"pass": "pass", "borderline": "amber", "fail": "fail"}


def run(df: pd.DataFrame, config: dict, options) -> AnalysisResult:
    dep_var = config.get("dep_var")
    indep_vars = config.get("indep_vars", [])
    entity_col = config.get("entity_col")
    time_col = config.get("time_col")

    if not dep_var:
        raise ValueError("dep_var is required.")
    if not indep_vars:
        raise ValueError("At least one indep_var is required.")
    if not entity_col:
        raise ValueError("entity_col is required.")
    if not time_col:
        raise ValueError("time_col is required.")

    se_type = getattr(options, "se_type", "auto")
    robust_se_override = se_type if se_type != "auto" else None

    ingest = IngestResult(
        df=df,
        row_count=len(df),
        columns=[
            IngestColumnInfo(name=c, dtype=str(df[c].dtype), missing_count=0, missing_pct=0.0)
            for c in df.columns
        ],
    )

    result = run_panel_pipeline(
        df=df,
        dep_var=dep_var,
        indep_vars=indep_vars,
        entity_col=entity_col,
        time_col=time_col,
        ingest_result=ingest,
        robust_se_override=robust_se_override,
    )

    model = result.model
    diags = result.diagnostics

    model_type_map = {"ols": "pooled_ols", "fe": "fe", "re": "re"}
    model_type = model_type_map.get(model.model_type, model.model_type)

    ci = model.conf_int
    coef_table = {}
    for var in indep_vars:
        if var in model.params.index:
            coef_table[var] = {
                "coef": round(float(model.params[var]), 4),
                "se": round(float(model.bse[var]), 4),
                "t": round(float(model.tvalues[var]), 4),
                "p": round(float(model.pvalues[var]), 4),
                "ci_low": round(float(ci.loc[var, "lower_95"]), 4),
                "ci_high": round(float(ci.loc[var, "upper_95"]), 4),
            }

    stats = {
        "model_type": model_type,
        "r_squared": round(float(model.rsquared), 4),
        "adj_r_squared": round(float(model.rsquared_adj), 4),
        "f_statistic": round(float(model.fvalue), 4),
        "f_pvalue": round(float(model.f_pvalue), 4),
        "n_obs": model.n_obs,
        "coefficients": coef_table,
        "intercept": round(float(model.params.get("const", float("nan"))), 4),
        "se_type": model.se_variant or "classical",
        "entity_col": entity_col,
        "time_col": time_col,
        "absorbed_vars": model.absorbed_vars or [],
        "bplm": _bplm_to_dict(result.bplm),
        "hausman": _hausman_to_dict(result.hausman),
        "selection_steps": [
            {
                "test_name": s.test_name,
                "statistic": round(float(s.statistic), 4) if s.statistic is not None else None,
                "p_value": round(float(s.p_value), 4) if s.p_value is not None else None,
                "verdict": s.verdict,
                "chosen_model": s.chosen_model,
                "note": s.note,
            }
            for s in result.selection_steps
        ],
    }

    checks = [_map_diagnostic(d) for d in diags if d.error is None]

    r2 = float(model.rsquared)
    f2 = r2 / (1 - r2) if r2 < 1.0 else float("inf")
    effect = EffectSize(
        name="Cohen's f\u00b2",
        value=round(f2, 4),
        interpretation=_f2_interpretation(f2),
    )

    interp = _build_interpretation(dep_var, indep_vars, model_type, stats)

    return AnalysisResult(
        test_key="panel_regression",
        test_name="Panel Regression (FE/RE)",
        n_obs=model.n_obs,
        statistics=stats,
        assumption_checks=checks,
        interpretation=interp,
        effect_size=effect,
        warnings=result.warnings,
    )


def _bplm_to_dict(bplm) -> dict | None:
    if bplm is None:
        return None
    return {
        "statistic": round(float(bplm.statistic), 4),
        "p_value": round(float(bplm.p_value), 4),
        "verdict": getattr(bplm, "verdict", None),
    }


def _hausman_to_dict(hausman) -> dict | None:
    if hausman is None:
        return None
    return {
        "statistic": round(float(hausman.statistic), 4),
        "p_value": round(float(hausman.p_value), 4),
        "verdict": getattr(hausman, "verdict", None),
        "dof": getattr(hausman, "dof", None),
    }


def _map_diagnostic(d) -> AssumptionCheck:
    status = _VERDICT_MAP.get(d.verdict, "amber")
    fix = None
    if status in ("amber", "fail"):
        if hasattr(d, "technical_note") and d.technical_note:
            fix = d.technical_note
    return AssumptionCheck(
        name=d.test_name,
        status=status,
        detail=d.plain_explanation,
        fix_suggestion=fix,
    )


def _f2_interpretation(f2: float) -> str:
    if f2 < 0.02:
        return "negligible"
    if f2 < 0.15:
        return "small"
    if f2 < 0.35:
        return "medium"
    return "large"


def _build_interpretation(
    dep_var: str, indep_vars: list[str], model_type: str, stats: dict
) -> Interpretation:
    model_label = {"fe": "Fixed Effects", "re": "Random Effects", "pooled_ols": "Pooled OLS"}
    label = model_label.get(model_type, model_type)
    r2 = stats["r_squared"]
    f_p = stats["f_pvalue"]
    sig = "statistically significant" if f_p < 0.05 else "not statistically significant"

    selection_log = ""
    steps = stats.get("selection_steps", [])
    if steps:
        parts = []
        for s in steps:
            chosen = s.get("chosen_model", "")
            model_name = {"fe": "FE", "re": "RE", "pooled_ols": "Pooled"}.get(chosen, chosen)
            parts.append(f"{s['test_name']} → {model_name}")
        selection_log = " Selection: " + " → ".join(parts) + "."

    plain = (
        f"A {label} panel model was estimated for {dep_var}. "
        f"The model explains {r2 * 100:.1f}% of the within-entity variation "
        f"and is {sig} (p = {f_p:.3f}).{selection_log}"
    )

    apa = (
        f"A panel data regression was conducted predicting {dep_var} from "
        f"{', '.join(indep_vars)} using {label}. "
        f"The model explained {r2 * 100:.1f}% of the variance, "
        f"R\u00b2 = {r2:.3f}, F({len(indep_vars)}, {stats['n_obs'] - len(indep_vars) - 1}) "
        f"= {stats['f_statistic']:.2f}, p {'< .001' if f_p < 0.001 else f'= {f_p:.3f}'}.{selection_log}"
    )

    technical = (
        f"Model: {label} | R\u00b2 = {r2:.4f}, Adj. R\u00b2 = {stats['adj_r_squared']:.4f}, "
        f"F({len(indep_vars)}, {stats['n_obs'] - len(indep_vars) - 1}) = {stats['f_statistic']:.4f}, "
        f"p = {f_p:.4f}, N = {stats['n_obs']}, SE = {stats['se_type']}{selection_log}"
    )

    return Interpretation(plain=plain, apa=apa, technical=technical)
