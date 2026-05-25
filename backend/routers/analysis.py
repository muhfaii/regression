"""Analysis endpoints: /api/analysis/*"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.analysis_modules.regression import run_ols
from backend.schemas.analysis import RunRequest, ValidateConfigRequest
from backend.schemas.results import AnalysisResult
from backend.services import session_store

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

def _run_ols(df, config, options):
    dep_var = config.get("dep_var")
    indep_vars = config.get("indep_vars", [])
    if not dep_var or not indep_vars:
        raise ValueError("dep_var and at least one indep_var are required.")
    return run_ols(df, dep_var, indep_vars)


# Registry of available test runners — extended in Phase B/C
_RUNNERS = {
    "ols_regression": _run_ols,
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

    # Persist result in session for later retrieval / export
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
    # Phase B: add type-conflict checks here
    return {"conflicts": []}


@router.get("/results/{result_id}")
async def get_result(session_id: str, result_id: str) -> dict:
    result = session_store.get_result(session_id, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    return result
