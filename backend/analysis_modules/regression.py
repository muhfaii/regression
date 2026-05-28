"""OLS regression wrapper — the only analysis module that imports regassist.

Maps regassist.pipeline.PipelineResult → backend.analysis_modules.base.AnalysisResult.
"""
from __future__ import annotations

import math

import pandas as pd
from regassist.ingest import IngestResult, ColumnInfo as IngestColumnInfo
from regassist.pipeline import run_cross_sectional_pipeline

from .base import AnalysisResult, AssumptionCheck, EffectSize, Interpretation
from .multicomp import adjust_pvalues

_VERDICT_MAP = {"pass": "pass", "borderline": "amber", "fail": "fail"}


def run_ols(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
    robust_se_override: str | None = None,
    options=None,
) -> AnalysisResult:
    # Build a minimal IngestResult so the pipeline doesn't crash
    ingest = IngestResult(
        df=df,
        row_count=len(df),
        columns=[IngestColumnInfo(name=c, dtype=str(df[c].dtype), missing_count=0, missing_pct=0.0) for c in df.columns],
    )

    result = run_cross_sectional_pipeline(
        df=df,
        dep_var=dep_var,
        indep_vars=indep_vars,
        ingest_result=ingest,
        robust_se_override=robust_se_override,
    )

    model = result.model
    diags = result.diagnostics

    # --- statistics ---
    ci = model.conf_int  # pd.DataFrame with columns "lower_95", "upper_95"
    coef_table = {}
    for var in indep_vars:
        if var in model.params.index:
            p_val = float(model.pvalues[var])
            coef_table[var] = {
                "coef": round(float(model.params[var]), 4),
                "se": round(float(model.bse[var]), 4),
                "t": round(float(model.tvalues[var]), 4),
                "p": round(float(p_val), 4),
                "ci_low": round(float(ci.loc[var, "lower_95"]), 4),
                "ci_high": round(float(ci.loc[var, "upper_95"]), 4),
                "significant": p_val < 0.05,
            }

    # Descriptive stats for model variables
    desc_stats = _compute_desc_stats(df, dep_var, indep_vars)

    # VIF per-variable table from diagnostics
    vif_table = _extract_vif_table(diags)

    # Remediation data (cross-patterns + per-test remedies)
    remediation = _extract_remediation(result.remediation)

    stats = {
        "r_squared": round(float(model.rsquared), 4),
        "adj_r_squared": round(float(model.rsquared_adj), 4),
        "f_statistic": round(float(model.fvalue), 4),
        "f_pvalue": round(float(model.f_pvalue), 4),
        "n_obs": model.n_obs,
        "coefficients": coef_table,
        "intercept": round(float(model.params.get("const", float("nan"))), 4),
        "se_type": model.se_variant or "classical",
        "se_justification": model.se_justification,
        "se_citation": model.se_citation,
        "desc_stats": desc_stats,
        "vif_table": vif_table,
        "remediation": remediation,
    }

    p_adjust_method = getattr(options, "p_adjust", "none") if options else "none"
    if p_adjust_method and p_adjust_method != "none":
        p_values = [coef_table[var]["p"] for var in indep_vars if var in coef_table]
        if p_values:
            p_adj = adjust_pvalues(p_values, p_adjust_method)
            idx = 0
            for var in indep_vars:
                if var in coef_table:
                    coef_table[var]["p_adjusted"] = round(float(p_adj[idx]), 4)
                    idx += 1
        stats["p_adjust_method"] = p_adjust_method

    # --- assumption checks ---
    checks = [_map_diagnostic(d) for d in diags if d.error is None]

    # --- effect size: f² = R² / (1 - R²) ---
    r2 = float(model.rsquared)
    f2 = r2 / (1 - r2) if r2 < 1.0 else float("inf")
    effect = EffectSize(
        name="Cohen's f²",
        value=round(f2, 4),
        interpretation=_f2_interpretation(f2),
    )

    # --- interpretation ---
    interp = _build_interpretation(dep_var, indep_vars, stats)

    return AnalysisResult(
        test_key="ols_regression",
        test_name="OLS Regression",
        n_obs=model.n_obs,
        statistics=stats,
        assumption_checks=checks,
        interpretation=interp,
        effect_size=effect,
        warnings=result.warnings,
    )


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


def _build_interpretation(dep_var: str, indep_vars: list[str], stats: dict) -> Interpretation:
    r2 = stats["r_squared"]
    f_p = stats["f_pvalue"]
    sig = "statistically significant" if f_p < 0.05 else "not statistically significant"

    plain = (
        f"The regression model explains {r2 * 100:.1f}% of the variation in {dep_var}. "
        f"The overall model is {sig} (p = {f_p:.3f})."
    )

    apa = (
        f"A multiple linear regression was conducted to predict {dep_var} from "
        f"{', '.join(indep_vars)}. The model explained {r2 * 100:.1f}% of the variance "
        f"in {dep_var}, R² = {r2:.3f}, F({len(indep_vars)}, {stats['n_obs'] - len(indep_vars) - 1}) "
        f"= {stats['f_statistic']:.2f}, p {'< .001' if f_p < 0.001 else f'= {f_p:.3f}'}."
    )

    technical = (
        f"R² = {r2:.4f}, Adj. R² = {stats['adj_r_squared']:.4f}, "
        f"F({len(indep_vars)}, {stats['n_obs'] - len(indep_vars) - 1}) = {stats['f_statistic']:.4f}, "
        f"p = {f_p:.4f}, N = {stats['n_obs']}, SE type = {stats['se_type']}"
    )

    return Interpretation(plain=plain, apa=apa, technical=technical)


def _compute_desc_stats(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
) -> list[dict]:
    cols = [dep_var] + list(indep_vars)
    stats = []
    for col in cols:
        if col not in df.columns:
            continue
        s = df[col].dropna()
        stats.append({
            "variable": col,
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std()), 4),
            "min": round(float(s.min()), 4),
            "median": round(float(s.median()), 4),
            "max": round(float(s.max()), 4),
            "missing": int(df[col].isnull().sum()),
        })
    return stats


def _extract_vif_table(diags: list) -> list[dict] | None:
    for d in diags:
        if d.test_id == "vif" and hasattr(d, "details") and d.details.get("per_variable"):
            return d.details["per_variable"]
    return None


def _extract_remediation(remediation) -> dict | None:
    if not remediation or not remediation.has_issues:
        return None
    return {
        "patterns": [
            {
                "id": p.id,
                "severity": p.severity,
                "interpretation": p.interpretation,
                "recommendation": p.recommendation,
                "triggered_by": p.triggered_by,
            }
            for p in remediation.patterns
        ],
        "per_test": [
            {
                "test_id": t.test_id,
                "test_name": t.test_name,
                "verdict": t.verdict,
                "remedies": [
                    {
                        "priority": r.priority,
                        "kind": r.kind,
                        "description": r.description,
                        "why": r.why,
                    }
                    for r in t.remedies
                ],
                "honest_caveat": t.honest_caveat,
            }
            for t in remediation.per_test
        ],
    }
