"""Shared data contracts for all analysis modules."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class AssumptionCheck:
    name: str
    status: Literal["pass", "amber", "fail"]
    detail: str
    fix_suggestion: str | None = None


@dataclass
class EffectSize:
    name: str
    value: float
    interpretation: str  # "small" | "medium" | "large"


@dataclass
class Interpretation:
    plain: str
    apa: str
    technical: str


@dataclass
class AnalysisResult:
    test_key: str
    test_name: str
    n_obs: int
    statistics: dict
    assumption_checks: list[AssumptionCheck]
    interpretation: Interpretation
    effect_size: EffectSize | None = None
    warnings: list[str] = field(default_factory=list)
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def cohen_d_interpretation(d: float) -> str:
    d = abs(d)
    if d < 0.2:
        return "negligible"
    if d < 0.5:
        return "small"
    if d < 0.8:
        return "medium"
    return "large"


def r_interpretation(r: float) -> str:
    r = abs(r)
    if r < 0.1:
        return "negligible"
    if r < 0.3:
        return "small"
    if r < 0.5:
        return "medium"
    return "large"
