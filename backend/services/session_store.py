"""Session store with disk-backed persistence.

Sessions are cached in memory for fast access and persisted as pickle
files in data/sessions/ so they survive server restarts.
"""
from __future__ import annotations

import asyncio
import json
import os
import pickle
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

SESSION_TTL = 30 * 60  # seconds
_SESSIONS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"


@dataclass
class Session:
    df: pd.DataFrame
    filename: str
    created_at: float = field(default_factory=time.time)
    results: dict = field(default_factory=dict)  # result_id → dict
    user_id: str | None = None
    conversation_id: str | None = None
    steps: list = field(default_factory=list)  # reproducibility log: {timestamp, action, detail}


_store: dict[str, Session] = {}
_loaded_from_disk = False


def _ensure_dir() -> None:
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _pickle_path(session_id: str) -> Path:
    return _SESSIONS_DIR / f"{session_id}.pkl"


def _load_from_disk(session_id: str) -> Session | None:
    path = _pickle_path(session_id)
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            session = pickle.load(f)
        _store[session_id] = session
        return session
    except (pickle.UnpicklingError, EOFError, OSError):
        return None


def _save_to_disk(session_id: str, session: Session) -> None:
    _ensure_dir()
    path = _pickle_path(session_id)
    with open(path, "wb") as f:
        pickle.dump(session, f)


def _remove_from_disk(session_id: str) -> None:
    path = _pickle_path(session_id)
    if path.exists():
        path.unlink(missing_ok=True)


def _load_all_from_disk() -> None:
    global _loaded_from_disk
    if _loaded_from_disk:
        return
    _ensure_dir()
    cutoff = time.time() - SESSION_TTL
    loaded = 0
    for p in _SESSIONS_DIR.glob("*.pkl"):
        if p.stat().st_mtime < cutoff:
            p.unlink(missing_ok=True)
            continue
        sid = p.stem
        if sid not in _store:
            session = _load_from_disk(sid)
            if session:
                loaded += 1
    _loaded_from_disk = True


def create_session(
    df: pd.DataFrame,
    filename: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    session_id = str(uuid.uuid4())
    session = Session(
        df=df,
        filename=filename,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    _store[session_id] = session
    _save_to_disk(session_id, session)
    return session_id


def find_session_for_conversation(conversation_id: str) -> Session | None:
    """Find a session by its conversation_id."""
    _load_all_from_disk()
    for session in _store.values():
        if session.conversation_id == conversation_id:
            return session
    _ensure_dir()
    for p in _SESSIONS_DIR.glob("*.pkl"):
        if p.stem in _store:
            continue
        session = _load_from_disk(p.stem)
        if session and session.conversation_id == conversation_id:
            return session
    return None


def get_session(session_id: str) -> Session | None:
    if session_id in _store:
        return _store[session_id]
    return _load_from_disk(session_id)


def update_session_df(session_id: str, df: pd.DataFrame) -> None:
    session = get_session(session_id)
    if session:
        session.df = df
        _save_to_disk(session_id, session)


def log_step(session_id: str, action: str, detail: str) -> None:
    session = get_session(session_id)
    if session:
        session.steps.append({"timestamp": time.time(), "action": action, "detail": detail})
        _save_to_disk(session_id, session)


def save_result(session_id: str, result_id: str, result: dict) -> None:
    session = get_session(session_id)
    if session:
        session.results[result_id] = result
        _save_to_disk(session_id, session)


def get_result(session_id: str, result_id: str) -> dict | None:
    session = get_session(session_id)
    if session:
        return session.results.get(result_id)


async def save_share(token: str, result: dict) -> None:
    from backend.services import share_repo

    await share_repo.save_share(token, result)


async def get_share(token: str) -> dict | None:
    from backend.services import share_repo

    return await share_repo.get_share(token)


# Session-level share store — bundles multiple results + dataset filename
_share_session_store: dict[str, dict] = {}


def save_share_session(token: str, bundle: dict) -> None:
    _share_session_store[token] = bundle


def get_share_session(token: str) -> dict | None:
    return _share_session_store.get(token)


async def persist_result_to_db(session_id: str, result_id: str) -> None:
    """Persist an analysis result as a Message in the associated conversation."""
    from backend.services import conversation_repo

    session = get_session(session_id)
    if session is None or session.conversation_id is None:
        return

    result = session.results.get(result_id)
    if result is None:
        return

    await conversation_repo.create_message(
        session.conversation_id, "assistant", "result", json.loads(json.dumps(result, default=str))
    )


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(120)
        cutoff = time.time() - SESSION_TTL
        # Clean in-memory
        expired = [sid for sid, s in list(_store.items()) if s.created_at < cutoff]
        for sid in expired:
            del _store[sid]
        # Clean disk files
        _ensure_dir()
        for p in _SESSIONS_DIR.glob("*.pkl"):
            if p.stat().st_mtime < cutoff:
                p.unlink(missing_ok=True)
