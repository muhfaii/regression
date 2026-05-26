from __future__ import annotations

from pydantic import BaseModel


class AnalysisOptions(BaseModel):
    assumption_checks: bool = True
    effect_size: bool = True
    post_hoc: bool = False


class RunRequest(BaseModel):
    session_id: str
    test_key: str
    config: dict  # variable slot assignments, e.g. {"dep_var": "wage", "indep_vars": ["edu"]}
    options: AnalysisOptions = AnalysisOptions()


class ValidateConfigRequest(BaseModel):
    session_id: str
    test_key: str
    config: dict
    column_overrides: dict[str, str] = {}
