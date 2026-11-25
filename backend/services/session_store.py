"""Durable dataset sessions.

Each session's DataFrame is stored in R2 as Parquet (sessions/<id>.parquet);
metadata, the reproducibility log and analysis results are stored in D1.
Sessions expire after SESSION_TTL of inactivity. Recently used DataFrames
are cached in process memory so repeated requests skip the R2 download.
"""
from __future__ import annotations

import asyncio
import dataclasses
import io
import json
import logging
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from backend.services import d1, r2

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(days=7)
CLEANUP_INTERVAL = 60 * 60  # seconds
_DF_CACHE_SIZE = 8


@dataclass
class Session:
    id: str
    df: pd.DataFrame
    filename: str
    user_id: str
    conversation_id: str | None = None
    results: dict = field(default_factory=dict)  # result_id → dict
    steps: list = field(default_factory=list)  # reproducibility log: {timestamp, action, detail}


_df_cache: OrderedDict[str, pd.DataFrame] = OrderedDict()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="microseconds")


def _object_key(session_id: str) -> str:
    return f"sessions/{session_id}.parquet"


def _to_parquet(df: pd.DataFrame) -> tuple[bytes, pd.DataFrame]:
    """Serialize df to Parquet; returns the bytes and the frame actually stored.

    Parquet needs string column names and one type per column, so non-string
    names become strings and mixed-type text columns have their non-null
    values converted to strings.
    """
    if not all(isinstance(c, str) for c in df.columns):
        df = df.rename(columns=str)
    try:
        return df.to_parquet(), df
    except (ValueError, TypeError):  # pyarrow's ArrowInvalid / ArrowTypeError
        mixed = [
            c for c in df.columns
            if df[c].dtype == object and pd.api.types.infer_dtype(df[c], skipna=True).startswith("mixed")
        ]
        if not mixed:
            raise
        df = df.copy()
        for c in mixed:
            df[c] = df[c].map(lambda v: v if _is_missing(v) else str(v))
        return df.to_parquet(), df


def _is_missing(value) -> bool:
    return value is None or value is pd.NA or (isinstance(value, float) and np.isnan(value))


def _json_default(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return str(obj)


def _dumps(value) -> str:
    return json.dumps(value, default=_json_default)


def _cache_df(session_id: str, df: pd.DataFrame) -> None:
    _df_cache[session_id] = df
    _df_cache.move_to_end(session_id)
    while len(_df_cache) > _DF_CACHE_SIZE:
        _df_cache.popitem(last=False)


async def _store_df(session_id: str, df: pd.DataFrame) -> None:
    data, stored = await asyncio.to_thread(_to_parquet, df)
    await r2.put_object(_object_key(session_id), data)
    _cache_df(session_id, stored)


async def _load_df(session_id: str) -> pd.DataFrame | None:
    if session_id in _df_cache:
        _df_cache.move_to_end(session_id)
        return _df_cache[session_id]
    data = await r2.get_object(_object_key(session_id))
    if data is None:
        return None
    df = await asyncio.to_thread(pd.read_parquet, io.BytesIO(data))
    _cache_df(session_id, df)
    return df


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

async def create_session(
    df: pd.DataFrame,
    filename: str,
    user_id: str,
    conversation_id: str | None = None,
) -> str:
    session_id = str(uuid.uuid4())
    await _store_df(session_id, df)
    now = _iso(_now())
    await d1.d1_execute(
        """INSERT INTO data_sessions (id, user_id, conversation_id, filename, created_at, last_used_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [session_id, user_id, conversation_id, filename, now, now],
    )
    return session_id


async def _load_session(row: dict) -> Session | None:
    session_id = row["id"]
    df = await _load_df(session_id)
    if df is None:
        return None
    await d1.d1_execute(
        "UPDATE data_sessions SET last_used_at = ? WHERE id = ?", [_iso(_now()), session_id]
    )
    steps = await d1.d1_query(
        "SELECT timestamp, action, detail FROM session_steps WHERE session_id = ? ORDER BY timestamp, rowid",
        [session_id],
    )
    results = await d1.d1_query(
        "SELECT id, payload FROM session_results WHERE session_id = ? ORDER BY created_at, rowid",
        [session_id],
    )
    return Session(
        id=session_id,
        df=df,
        filename=row["filename"],
        user_id=row["user_id"],
        conversation_id=row["conversation_id"],
        results={r["id"]: json.loads(r["payload"]) for r in results},
        steps=[dict(s) for s in steps],
    )


def _cutoff() -> str:
    return _iso(_now() - SESSION_TTL)


async def get_owned_session(session_id: str, user_id: str) -> Session | None:
    """Return the session only if it exists, is unexpired and belongs to `user_id`."""
    rows = await d1.d1_query(
        "SELECT * FROM data_sessions WHERE id = ? AND user_id = ? AND last_used_at > ?",
        [session_id, user_id, _cutoff()],
    )
    return await _load_session(rows[0]) if rows else None


async def find_session_for_conversation(conversation_id: str) -> Session | None:
    """Most recently used unexpired session linked to a conversation."""
    rows = await d1.d1_query(
        """SELECT * FROM data_sessions WHERE conversation_id = ? AND last_used_at > ?
           ORDER BY last_used_at DESC LIMIT 1""",
        [conversation_id, _cutoff()],
    )
    return await _load_session(rows[0]) if rows else None


async def update_session_df(session_id: str, df: pd.DataFrame) -> None:
    await _store_df(session_id, df)


async def log_step(session_id: str, action: str, detail: str) -> None:
    await d1.d1_execute(
        "INSERT INTO session_steps (session_id, timestamp, action, detail) VALUES (?, ?, ?, ?)",
        [session_id, time.time(), action, detail],
    )


async def save_result(session_id: str, result_id: str, result: dict) -> None:
    await d1.d1_execute(
        "INSERT INTO session_results (id, session_id, payload, created_at) VALUES (?, ?, ?, ?)",
        [result_id, session_id, _dumps(result), _iso(_now())],
    )


async def persist_result_to_db(session_id: str, result_id: str) -> None:
    """Persist an analysis result as a Message in the associated conversation."""
    from backend.services import conversation_repo

    rows = await d1.d1_query(
        """SELECT s.conversation_id, r.payload FROM data_sessions s
           JOIN session_results r ON r.session_id = s.id
           WHERE s.id = ? AND r.id = ?""",
        [session_id, result_id],
    )
    if not rows or rows[0]["conversation_id"] is None:
        return
    await conversation_repo.create_message(
        rows[0]["conversation_id"], "assistant", "result", json.loads(rows[0]["payload"])
    )


# ---------------------------------------------------------------------------
# Share links
# ---------------------------------------------------------------------------

async def save_share(token: str, result: dict) -> None:
    from backend.services import share_repo

    await share_repo.save_share(token, json.loads(_dumps(result)))


async def get_share(token: str) -> dict | None:
    from backend.services import share_repo

    return await share_repo.get_share(token)


async def save_share_session(token: str, bundle: dict) -> None:
    """Session-level share: bundles multiple results + dataset filename."""
    await d1.d1_execute(
        "INSERT INTO session_share_tokens (token, payload, created_at) VALUES (?, ?, ?)",
        [token, _dumps(bundle), _iso(_now())],
    )


async def get_share_session(token: str) -> dict | None:
    rows = await d1.d1_query("SELECT payload FROM session_share_tokens WHERE token = ?", [token])
    return json.loads(rows[0]["payload"]) if rows else None


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------

async def delete_expired_sessions() -> int:
    rows = await d1.d1_query(
        "SELECT id FROM data_sessions WHERE last_used_at <= ? LIMIT 100", [_cutoff()]
    )
    for row in rows:
        sid = row["id"]
        await r2.delete_object(_object_key(sid))
        await d1.d1_execute("DELETE FROM session_steps WHERE session_id = ?", [sid])
        await d1.d1_execute("DELETE FROM session_results WHERE session_id = ?", [sid])
        await d1.d1_execute("DELETE FROM data_sessions WHERE id = ?", [sid])
        _df_cache.pop(sid, None)
    return len(rows)


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        try:
            await delete_expired_sessions()
        except Exception:
            logger.exception("Expired-session cleanup failed; will retry next interval.")
