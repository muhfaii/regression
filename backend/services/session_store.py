"""In-memory session store keyed by session_id UUID.

Each session holds the uploaded DataFrame and dataset metadata.
A background cleanup task removes sessions older than 30 minutes.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field

import pandas as pd

SESSION_TTL = 30 * 60  # seconds


@dataclass
class Session:
    df: pd.DataFrame
    filename: str
    created_at: float = field(default_factory=time.time)
    results: dict = field(default_factory=dict)  # result_id → dict


_store: dict[str, Session] = {}


def create_session(df: pd.DataFrame, filename: str) -> str:
    session_id = str(uuid.uuid4())
    _store[session_id] = Session(df=df, filename=filename)
    return session_id


def get_session(session_id: str) -> Session | None:
    return _store.get(session_id)


def save_result(session_id: str, result_id: str, result: dict) -> None:
    session = _store.get(session_id)
    if session:
        session.results[result_id] = result


def get_result(session_id: str, result_id: str) -> dict | None:
    session = _store.get(session_id)
    if session:
        return session.results.get(result_id)


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(60)
        cutoff = time.time() - SESSION_TTL
        expired = [sid for sid, s in _store.items() if s.created_at < cutoff]
        for sid in expired:
            del _store[sid]
