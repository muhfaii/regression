from __future__ import annotations

from pydantic import BaseModel


class AnalysisOptions(BaseModel):
    assumption_checks: bool = True
    effect_size: bool = True
    post_hoc: bool = False
    se_type: str = "auto"
    p_adjust: str = "none"
    extras: dict = {}


class RunRequest(BaseModel):
    session_id: str
    test_key: str
    config: dict  # variable slot assignments, e.g. {"dep_var": "wage", "indep_vars": ["edu"]}
    options: AnalysisOptions = AnalysisOptions()
    conversation_id: str | None = None  # if provided, persist result as a message


class ValidateConfigRequest(BaseModel):
    session_id: str
    test_key: str
    config: dict
    column_overrides: dict[str, str] = {}
