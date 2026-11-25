import os

os.environ.setdefault("JWT_SECRET", "test-secret")

import sqlite3  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from backend import middleware  # noqa: E402
from backend.models.conversation import Conversation, Message  # noqa: E402
from backend.models.user import User  # noqa: E402
from backend.services import conversation_repo, d1, limits, r2, session_store  # noqa: E402
from backend.services.auth import create_access_token  # noqa: E402


@pytest.fixture
def make_user(monkeypatch):
    """Create in-memory users; returns (user, auth_headers) with a real JWT."""
    users: dict[str, User] = {}

    async def fake_get_user_by_id(user_id):
        return users.get(user_id)

    monkeypatch.setattr(middleware, "get_user_by_id", fake_get_user_by_id)

    def _make(email="user@example.com"):
        user = User(email=email, password_hash="x")
        users[user.id] = user
        return user, {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _make


@pytest.fixture
def conversations(monkeypatch):
    """In-memory conversation repo; returns (make_conversation, messages)."""
    convs: dict[str, Conversation] = {}
    messages: list[Message] = []

    async def get_conversation(conversation_id, user_id):
        conv = convs.get(conversation_id)
        return conv if conv and conv.user_id == user_id else None

    async def create_message(conversation_id, role, content_type, payload):
        msg = Message(conversation_id=conversation_id, role=role, content_type=content_type, payload="{}")
        messages.append(msg)
        return msg

    async def list_messages(conversation_id):
        return [m for m in messages if m.conversation_id == conversation_id]

    monkeypatch.setattr(conversation_repo, "get_conversation", get_conversation)
    monkeypatch.setattr(conversation_repo, "create_message", create_message)
    monkeypatch.setattr(conversation_repo, "list_messages", list_messages)

    def _make(user):
        conv = Conversation(user_id=user.id)
        convs[conv.id] = conv
        return conv

    return _make, messages


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    for limiter in (limits.login_by_email, limits.login_by_ip, limits.register_by_ip, limits.chat_by_user):
        limiter._hits.clear()
    yield


_MIGRATIONS = sorted((Path(__file__).resolve().parents[2] / "migrations").glob("*.sql"))


@pytest.fixture(autouse=True)
def fake_d1(monkeypatch):
    """Back D1 with an in-memory SQLite database built from the real migrations."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    for path in _MIGRATIONS:
        conn.executescript(path.read_text())

    async def _run(sql, params=None):
        rows = conn.execute(sql, params or []).fetchall()
        conn.commit()
        return [dict(r) for r in rows]

    monkeypatch.setattr(d1, "_run", _run)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def fake_r2(monkeypatch):
    """Back R2 with a dict; also empties the session DataFrame cache."""
    objects: dict[str, bytes] = {}

    async def put_object(key, data):
        objects[key] = data

    async def get_object(key):
        return objects.get(key)

    async def delete_object(key):
        objects.pop(key, None)

    monkeypatch.setattr(r2, "put_object", put_object)
    monkeypatch.setattr(r2, "get_object", get_object)
    monkeypatch.setattr(r2, "delete_object", delete_object)
    session_store._df_cache.clear()
    yield objects
    session_store._df_cache.clear()
