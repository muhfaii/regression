"""
Remediation engine — maps diagnostic failures to ranked remedies and
detects cross-diagnostic patterns.

Covers: FR-6.1 (ranked remedies), FR-6.2 (quick_fix vs thinking_fix),
        FR-6.4 (why each remedy works), FR-5.4 (cross-pattern detection).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from regassist.diagnostics import DiagnosticResult
from regassist.estimate import FittedModel

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "diagnostics.yaml"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class Remedy:
    priority: int
    kind: str         # "quick_fix" | "thinking_fix"
    description: str
    why: str


@dataclass
class PerTestRemediation:
    """Remedies for a single failed or borderline diagnostic."""
    test_id: str
    test_name: str
    verdict: str      # "fail" | "borderline"
    remedies: list[Remedy]
    honest_caveat: str


@dataclass
class CrossPattern:
    """A meta-finding triggered when multiple diagnostics co-fail."""
    id: str
    severity: str     # "high" | "medium" | "low"
    interpretation: str
    recommendation: str
    triggered_by: list[str]   # test_ids that contributed


@dataclass
class RemediationReport:
    per_test: list[PerTestRemediation]   # one entry per non-passing diagnostic
    patterns: list[CrossPattern]      # cross-diagnostic patterns detected

    @property
    def has_issues(self) -> bool:
        return bool(self.per_test)

    @property
    def failed_ids(self) -> set[str]:
        return {r.test_id for r in self.per_test}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_remediation(
    diagnostic_results: list[DiagnosticResult],
    model: FittedModel,
    config_path: Path | str | None = None,
) -> RemediationReport:
    """Build the full remediation report for a set of diagnostic results.

    Only non-passing (fail or borderline) diagnostics receive remedies.
    Cross-patterns are checked regardless of individual verdict.

    Args:
        diagnostic_results: Output of run_diagnostics().
        model:              The FittedModel (used for n-dependent advice).
        config_path:        Config path override for tests.

    Returns:
        RemediationReport with per-test remedies and cross-patterns.
    """
    cfg = _load_config(config_path or _CONFIG_PATH)
    cfg_by_id = {entry["id"]: entry for entry in cfg["diagnostics"]}

    non_passing = [r for r in diagnostic_results if r.verdict != "pass"]

    per_test = []
    for result in non_passing:
        entry = cfg_by_id.get(result.test_id)
        if entry is None or not entry.get("remedies"):
            continue
        remedies = [
            Remedy(
                priority=rem["priority"],
                kind=rem["kind"],
                description=_inject_context(rem["description"], model),
                why=_inject_context(rem["why"], model),
            )
            for rem in sorted(entry["remedies"], key=lambda r: r["priority"])
        ]
        per_test.append(PerTestRemediation(
            test_id=result.test_id,
            test_name=result.test_name,
            verdict=result.verdict,
            remedies=remedies,
            honest_caveat=entry.get("honest_caveat", "").strip(),
        ))

    patterns = _detect_patterns(diagnostic_results, cfg.get("cross_patterns", []))

    return RemediationReport(per_test=per_test, patterns=patterns)


# ---------------------------------------------------------------------------
# Cross-pattern detection
# ---------------------------------------------------------------------------

def _detect_patterns(
    results: list[DiagnosticResult],
    pattern_configs: list[dict],
) -> list[CrossPattern]:
    """Fire each pattern whose trigger conditions are all satisfied."""
    verdict_by_id = {r.test_id: r.verdict for r in results}
    fired = []

    for pc in pattern_configs:
        triggers = pc.get("triggers", [])
        matched_ids = []

        for trigger in triggers:
            tid = trigger["test_id"]
            required = trigger["verdict"]
            actual = verdict_by_id.get(tid)
            if actual is None:
                break   # test wasn't run; pattern can't fire
            if not _verdict_matches(actual, required):
                break
            matched_ids.append(tid)
        else:
            # All triggers satisfied
            fired.append(CrossPattern(
                id=pc["id"],
                severity=pc.get("severity", "medium"),
                interpretation=pc["interpretation"].strip(),
                recommendation=pc["recommendation"].strip(),
                triggered_by=matched_ids,
            ))

    return fired


def _verdict_matches(actual: str, required: str) -> bool:
    """Check whether an actual verdict satisfies a trigger condition.

    Supported required values:
      "fail"              — exact match
      "borderline"        — exact match
      "not_pass"          — fail OR borderline
      "fail_or_borderline" — alias for not_pass
    """
    if required == "fail":
        return actual == "fail"
    if required == "borderline":
        return actual == "borderline"
    if required in ("not_pass", "fail_or_borderline"):
        return actual in ("fail", "borderline")
    return actual == required


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_config(path: Path | str) -> dict:
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _inject_context(text: str, model: FittedModel) -> str:
    """Replace {n_obs} placeholder with the actual sample size."""
    return text.strip().replace("{n_obs}", str(model.n_obs))
