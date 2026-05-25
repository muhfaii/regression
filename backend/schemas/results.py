from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AssumptionCheck(BaseModel):
    name: str
    status: Literal["pass", "amber", "fail"]
    detail: str
    fix_suggestion: str | None = None


class EffectSize(BaseModel):
    name: str
    value: float
    interpretation: str


class Interpretation(BaseModel):
    plain: str
    apa: str
    technical: str


class AnalysisResult(BaseModel):
    result_id: str
    test_key: str
    test_name: str
    n_obs: int
    statistics: dict  # test-specific numeric values
    effect_size: EffectSize | None = None
    assumption_checks: list[AssumptionCheck]
    interpretation: Interpretation
    warnings: list[str] = []
