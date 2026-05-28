"""Analysis endpoints: /api/analysis/*"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.analysis_modules import (
    anova,
    chi_square,
    correlation,
    descriptive,
    logistic,
    mediation,
    moderation,
    nonparametric,
    panel,
    power_analysis,
    regression,
    reliability,
    t_tests,
)
from backend.schemas.analysis import RunRequest, ValidateConfigRequest
from backend.schemas.results import AnalysisResult
from backend.services import session_store
from backend.services.column_inference import _classify_type

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


# ---------------------------------------------------------------------------
# Runner shims — each takes (df, config, options) → AnalysisResult
# ---------------------------------------------------------------------------

def _run_ols(df, config, options):
    dep_var = config.get("dep_var")
    indep_vars = config.get("indep_vars", [])
    if not dep_var or not indep_vars:
        raise ValueError("dep_var and at least one indep_var are required.")
    return regression.run_ols(df, dep_var, indep_vars, options=options)


_RUNNERS = {
    "descriptive": descriptive.run,
    "independent_t": t_tests.run_independent_t,
    "paired_t": t_tests.run_paired_t,
    "one_way_anova": anova.run,
    "factorial_anova": anova.run_factorial,
    "mann_whitney": nonparametric.run_mann_whitney,
    "wilcoxon": nonparametric.run_wilcoxon,
    "kruskal_wallis": nonparametric.run_kruskal_wallis,
    "correlation": correlation.run,
    "chi_square": chi_square.run,
    "ols_regression": _run_ols,
    "panel_regression": panel.run,
    "logistic_regression": logistic.run,
    "moderation": moderation.run,
    "mediation": mediation.run,
    "reliability": reliability.run,
    "power_analysis": power_analysis.run,
}

# Slot type requirements — mirrors TEST_CATALOG in frontend/src/constants/tests.ts
_SLOT_TYPES: dict[str, dict[str, str]] = {
    "descriptive": {"variables": "any"},
    "independent_t": {"outcome": "continuous", "group": "categorical"},
    "paired_t": {"col_a": "continuous", "col_b": "continuous"},
    "one_way_anova": {"outcome": "continuous", "group": "categorical"},
    "factorial_anova": {"outcome": "continuous", "factors": "categorical"},
    "mann_whitney": {"outcome": "continuous", "group": "categorical"},
    "wilcoxon": {"col_a": "continuous", "col_b": "continuous"},
    "kruskal_wallis": {"outcome": "continuous", "group": "categorical"},
    "correlation": {"variables": "continuous"},
    "chi_square": {"col_a": "categorical", "col_b": "categorical"},
    "ols_regression": {"dep_var": "continuous", "indep_vars": "any"},
    "panel_regression": {"dep_var": "continuous", "indep_vars": "any", "entity_col": "any", "time_col": "any"},
    "logistic_regression": {"outcome": "categorical", "predictors": "any"},
    "moderation": {"outcome": "continuous", "predictor": "any", "moderator": "any", "covariates": "any"},
    "mediation": {"outcome": "continuous", "predictor": "any", "mediator": "any", "covariates": "any"},
    "reliability": {"variables": "any"},
}


@router.post("/run", response_model=AnalysisResult)
async def run_analysis(req: RunRequest) -> AnalysisResult:
    session = session_store.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    runner = _RUNNERS.get(req.test_key)
    if runner is None:
        raise HTTPException(status_code=422, detail=f"Unknown test: {req.test_key!r}")

    try:
        result = runner(session.df, req.config, req.options)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    session_store.save_result(req.session_id, result.result_id, result.__dict__)

    return AnalysisResult(
        result_id=result.result_id,
        test_key=result.test_key,
        test_name=result.test_name,
        n_obs=result.n_obs,
        statistics=result.statistics,
        effect_size=result.effect_size.__dict__ if result.effect_size else None,
        assumption_checks=[a.__dict__ for a in result.assumption_checks],
        interpretation=result.interpretation.__dict__,
        warnings=result.warnings,
    )


@router.post("/validate-config")
async def validate_config(req: ValidateConfigRequest) -> dict:
    session = session_store.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    slot_types = _SLOT_TYPES.get(req.test_key, {})
    if not slot_types:
        return {"conflicts": []}

    # Build effective column type map (inferred, overridden by client overrides)
    df = session.df
    inferred: dict[str, str] = {col: _classify_type(df[col]) for col in df.columns}
    effective: dict[str, str] = {**inferred, **req.column_overrides}

    conflicts = []
    for slot_key, required_type in slot_types.items():
        if required_type == "any":
            continue
        value = req.config.get(slot_key)
        if value is None:
            continue
        col_names = value if isinstance(value, list) else [value]
        for col in col_names:
            actual = effective.get(col)
            if actual and actual != required_type:
                conflicts.append({
                    "slot": slot_key,
                    "column": col,
                    "required_type": required_type,
                    "actual_type": actual,
                })

    return {"conflicts": conflicts}


@router.get("/results/{result_id}")
async def get_result(session_id: str, result_id: str) -> dict:
    result = session_store.get_result(session_id, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    return result
