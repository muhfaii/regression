"""
Data structure detection — classifies an uploaded DataFrame as cross-sectional,
panel, time-series, or ambiguous.

Covers: spec §5.1 (detection logic), §5.2 (heuristics), §5.3 (user confirmation
data — the confirmation UI lives in app.py).

Detection approach
──────────────────
Score every column independently, then combine scores to classify:

  Cross-sectional  — no column looks like a repeated entity ID; no ordered
                     time column paired with repeated entities.
  Panel            — at least one "entity" column (low cardinality, many
                     repeats) AND at least one "time" column (date-like or
                     year-like integers).
  Time-series      — a monotonic time column exists, but no entity column
                     (each timestamp appears at most once → single series).
  Ambiguous        — signals are present but contradictory or too weak.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import numpy as np

# ── Thresholds ──────────────────────────────────────────────────────────────
_ENTITY_CARD_MIN  = 0.003   # cardinality ratio: at least this many unique values
_ENTITY_CARD_MAX  = 0.70    # but not too many (otherwise it looks like a key)
_ENTITY_MIN_REPS  = 2.0     # each entity must appear on average ≥ this many times
_DATE_PARSE_MIN   = 0.70    # fraction of non-null values that must parse as dates
_YEAR_MIN, _YEAR_MAX = 1900, 2100


# ── Column-level scoring ─────────────────────────────────────────────────────

@dataclass
class ColumnScore:
    name: str
    n_unique: int
    cardinality_ratio: float   # n_unique / n_rows
    mean_repeats: float        # n_rows / n_unique
    is_date_like: bool
    is_year_like: bool         # integers in plausible year range
    is_sequential: bool        # unique values form an arithmetic sequence
    repeat_balance: float      # 1 - CV of value_counts; 1 = perfectly balanced


    @property
    def looks_like_entity(self) -> bool:
        """True when the column plausibly identifies repeated units (firms, countries…)."""
        return (
            _ENTITY_CARD_MIN <= self.cardinality_ratio <= _ENTITY_CARD_MAX
            and self.mean_repeats >= _ENTITY_MIN_REPS
            and not self.is_date_like
            and not self.is_year_like
        )

    @property
    def looks_like_time(self) -> bool:
        """True when the column plausibly represents an ordered time dimension.

        Bare sequential integers (1, 2, 3 …) are intentionally excluded —
        they are indistinguishable from a row index or ID column. Only
        date-parsed strings and integers in a plausible year range qualify.
        """
        return self.is_date_like or self.is_year_like

    @property
    def all_unique(self) -> bool:
        return self.cardinality_ratio > 0.95


# ── Dataset-level result ─────────────────────────────────────────────────────

@dataclass
class DetectionResult:
    structure: str              # "cross_sectional" | "panel" | "time_series" | "ambiguous"
    confidence: str             # "high" | "medium" | "low"
    entity_col: str | None      # best entity candidate (panel only)
    time_col: str | None        # best time candidate (panel / time-series)
    n_entities: int | None      # estimated number of entities
    n_periods: int | None       # estimated number of time periods
    entity_candidates: list[str] = field(default_factory=list)
    time_candidates: list[str]  = field(default_factory=list)
    reasoning: list[str]        = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────────────

def detect_structure(df: pd.DataFrame) -> DetectionResult:
    """Score every column and classify the dataset structure.

    Args:
        df: The uploaded DataFrame (after file parsing, before missing-data
            strategy is applied — detection needs the raw column shapes).

    Returns:
        DetectionResult with the inferred structure and supporting detail.
    """
    n_rows = len(df)
    scores = {col: _score_column(df[col], n_rows) for col in df.columns}

    entity_candidates = [s for s in scores.values() if s.looks_like_entity]
    time_candidates   = [s for s in scores.values() if s.looks_like_time]

    # Sort candidates: entity by balance (most regular first),
    # time by preference: date > year > sequential
    entity_candidates.sort(key=lambda s: -s.repeat_balance)
    time_candidates.sort(
        key=lambda s: (-(s.is_date_like * 3 + s.is_year_like * 2 + s.is_sequential))
    )

    best_entity = entity_candidates[0].name if entity_candidates else None
    best_time   = time_candidates[0].name   if time_candidates   else None

    return _classify(
        df, scores, n_rows,
        entity_candidates=[s.name for s in entity_candidates],
        time_candidates=[s.name for s in time_candidates],
        best_entity=best_entity,
        best_time=best_time,
    )


# ── Column scorer ─────────────────────────────────────────────────────────────

def _score_column(series: pd.Series, n_rows: int) -> ColumnScore:
    non_null = series.dropna()
    n_unique = int(non_null.nunique())
    card = n_unique / n_rows if n_rows else 0.0
    mean_reps = n_rows / n_unique if n_unique else 0.0

    # Repeat balance: 1 - CV of value_counts (higher = more uniform repetition)
    vc = non_null.value_counts()
    if len(vc) > 1:
        cv = float(vc.std() / vc.mean()) if vc.mean() > 0 else 0.0
        balance = max(0.0, 1.0 - cv)
    else:
        balance = 1.0

    return ColumnScore(
        name=series.name,
        n_unique=n_unique,
        cardinality_ratio=card,
        mean_repeats=mean_reps,
        is_date_like=_is_date_like(non_null),
        is_year_like=_is_year_like(non_null),
        is_sequential=_is_sequential(non_null),
        repeat_balance=round(balance, 3),
    )


def _is_date_like(series: pd.Series) -> bool:
    """True if ≥70% of non-null values parse as dates."""
    if len(series) == 0:
        return False
    # Already datetime
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    # Try coercing a string/object column.
    # Sample up to 200 values to keep this fast and suppress format-inference warnings
    # by trying a fixed ISO format first, then falling back.
    if series.dtype == object or pd.api.types.is_string_dtype(series):
        sample = series.head(200)
        try:
            parsed = pd.to_datetime(sample, errors="coerce", format="ISO8601")
        except Exception:
            parsed = pd.to_datetime(sample, errors="coerce")
        return parsed.notna().mean() >= _DATE_PARSE_MIN
    return False


def _is_year_like(series: pd.Series) -> bool:
    """True if the column contains only integers in [1900, 2100]."""
    if not pd.api.types.is_numeric_dtype(series):
        return False
    unique_vals = series.dropna().unique()
    if len(unique_vals) == 0:
        return False
    int_vals = unique_vals[unique_vals == unique_vals.astype(int)]
    if len(int_vals) < len(unique_vals) * 0.95:
        return False   # not all integers
    return bool((int_vals >= _YEAR_MIN).all() and (int_vals <= _YEAR_MAX).all())


def _is_sequential(series: pd.Series) -> bool:
    """True if the unique values form a regular arithmetic sequence (step ≥ 1)."""
    if not pd.api.types.is_numeric_dtype(series):
        return False
    unique_sorted = np.sort(series.dropna().unique())
    if len(unique_sorted) < 3:
        return False
    diffs = np.diff(unique_sorted)
    if diffs.min() <= 0:
        return False   # not strictly increasing
    # All gaps equal (within float tolerance)
    return bool(np.allclose(diffs, diffs[0], rtol=0.01))


# ── Classifier ────────────────────────────────────────────────────────────────

def _classify(
    df: pd.DataFrame,
    scores: dict[str, ColumnScore],
    n_rows: int,
    entity_candidates: list[str],
    time_candidates: list[str],
    best_entity: str | None,
    best_time: str | None,
) -> DetectionResult:
    reasoning: list[str] = []

    # ── Panel: entity + time both found ──────────────────────────────────────
    if best_entity and best_time:
        e_score = scores[best_entity]
        t_score = scores[best_time]

        n_entities = int(df[best_entity].nunique())
        n_periods  = int(df[best_time].nunique())

        reasoning.append(
            f"'{best_entity}' looks like an entity column: "
            f"{n_entities} unique values, each appearing ~{e_score.mean_repeats:.1f} times "
            f"(cardinality {e_score.cardinality_ratio:.2f})."
        )
        reasoning.append(
            f"'{best_time}' looks like a time column "
            f"({'date-like' if t_score.is_date_like else 'year-like' if t_score.is_year_like else 'sequential'})."
        )

        confidence = (
            "high"   if e_score.repeat_balance > 0.8 and n_entities >= 3 and n_periods >= 3
            else "medium" if n_entities >= 2 and n_periods >= 2
            else "low"
        )
        return DetectionResult(
            structure="panel",
            confidence=confidence,
            entity_col=best_entity,
            time_col=best_time,
            n_entities=n_entities,
            n_periods=n_periods,
            entity_candidates=entity_candidates,
            time_candidates=time_candidates,
            reasoning=reasoning,
        )

    # ── Time-series: time column found, no entity column ─────────────────────
    if best_time and not best_entity:
        t_score = scores[best_time]
        n_periods = int(df[best_time].nunique())

        # Time-series: each timestamp appears at most once (or nearly so)
        if t_score.cardinality_ratio > 0.8:
            reasoning.append(
                f"'{best_time}' is a time column with {n_periods} unique values "
                f"and no repeated entity identifier found."
            )
            return DetectionResult(
                structure="time_series",
                confidence="medium",
                entity_col=None,
                time_col=best_time,
                n_entities=1,
                n_periods=n_periods,
                time_candidates=time_candidates,
                reasoning=reasoning,
            )

    # ── Cross-sectional: no entity, no time (or time-like column is ambiguous) ─
    if not best_entity:
        reasoning.append(
            "No column with repeated values consistent with an entity identifier was found."
        )
        if best_time:
            reasoning.append(
                f"'{best_time}' looks time-like but has no corresponding entity column. "
                "Treating as cross-sectional."
            )
        else:
            reasoning.append(
                "No date or year column was found. Data appears cross-sectional."
            )
        return DetectionResult(
            structure="cross_sectional",
            confidence="high" if not best_time else "medium",
            entity_col=None,
            time_col=best_time,
            n_entities=None,
            n_periods=None,
            time_candidates=time_candidates,
            reasoning=reasoning,
        )

    # ── Ambiguous ─────────────────────────────────────────────────────────────
    reasoning.append(
        "The data structure could not be determined automatically. "
        "An entity column may be present but no clear time dimension was found."
    )
    return DetectionResult(
        structure="ambiguous",
        confidence="low",
        entity_col=best_entity,
        time_col=None,
        n_entities=int(df[best_entity].nunique()) if best_entity else None,
        n_periods=None,
        entity_candidates=entity_candidates,
        time_candidates=time_candidates,
        reasoning=reasoning,
    )
