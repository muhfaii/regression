"""Auth, ownership, size-limit and rate-limit checks for the API."""
import io
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import auth as auth_router
from backend.routers import chat as chat_router
from backend.services import limits

CSV = b"score,pre\n50,40\n55,42\n48,38\n60,45\n52,41\n"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _upload(client, headers, conversation_id=None):
    params = {"conversation_id": conversation_id} if conversation_id else {}
    return client.post(
        "/api/data/upload",
        params=params,
        headers=headers,
        files={"file": ("data.csv", io.BytesIO(CSV), "text/csv")},
    )


def _run(client, headers, session_id, conversation_id=None):
    body = {"session_id": session_id, "test_key": "descriptive", "config": {"variables": ["score"]}}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return client.post("/api/analysis/run", headers=headers, json=body)


# --- Authentication required -------------------------------------------------

@pytest.mark.parametrize("method,path", [
    ("post", "/api/data/upload"),
    ("post", "/api/data/paste"),
    ("get", "/api/data/samples/clean_wages"),
    ("post", "/api/dataprep/missing"),
    ("post", "/api/dataprep/merge"),
    ("post", "/api/analysis/run"),
    ("post", "/api/analysis/validate-config"),
    ("get", "/api/analysis/results/r1?session_id=s1"),
    ("post", "/api/export/word/r1?session_id=s1"),
    ("post", "/api/export/share/r1?session_id=s1"),
    ("get", "/api/export/log/s1"),
    ("get", "/api/export/log/s1/download"),
    ("post", "/api/export/report/s1"),
    ("post", "/api/export/share-session/s1"),
])
def test_session_endpoints_require_auth(client, method, path):
    res = getattr(client, method)(path)
    assert res.status_code in (401, 403)


# --- Session ownership -------------------------------------------------------

def test_other_user_cannot_access_session(client, make_user):
    _, alice = make_user("alice@example.com")
    _, bob = make_user("bob@example.com")

    session_id = _upload(client, alice).json()["session_id"]
    result_id = _run(client, alice, session_id).json()["result_id"]

    assert _run(client, bob, session_id).status_code == 404
    assert client.post("/api/dataprep/missing", headers=bob, json={
        "session_id": session_id, "columns": ["score"], "strategy": "mean",
    }).status_code == 404
    assert client.get(f"/api/export/log/{session_id}", headers=bob).status_code == 404
    assert client.get(
        f"/api/analysis/results/{result_id}", params={"session_id": session_id}, headers=bob,
    ).status_code == 404
    assert client.post(
        f"/api/export/share/{result_id}", params={"session_id": session_id}, headers=bob,
    ).status_code == 404
    assert client.post(f"/api/export/report/{session_id}", headers=bob).status_code == 404

    # The owner still has access.
    assert client.get(f"/api/export/log/{session_id}", headers=alice).status_code == 200


# --- Conversation ownership --------------------------------------------------

def test_cannot_attach_session_to_another_users_conversation(client, make_user, conversations):
    make_conversation, messages = conversations
    alice_user, alice = make_user("alice@example.com")
    _, bob = make_user("bob@example.com")
    alice_conv = make_conversation(alice_user)

    assert _upload(client, bob, alice_conv.id).status_code == 404
    assert client.post(
        "/api/data/paste", params={"conversation_id": alice_conv.id}, headers=bob, json={"text": "a,b\n1,2\n"},
    ).status_code == 404
    assert client.get(
        "/api/data/samples/clean_wages", params={"conversation_id": alice_conv.id}, headers=bob,
    ).status_code == 404
    assert messages == []


def test_owner_can_attach_session_and_persist_results(client, make_user, conversations):
    make_conversation, messages = conversations
    alice_user, alice = make_user("alice@example.com")
    conv = make_conversation(alice_user)

    res = _upload(client, alice, conv.id)
    assert res.status_code == 200
    assert _run(client, alice, res.json()["session_id"], conv.id).status_code == 200
    assert [m.conversation_id for m in messages] == [conv.id]


# --- Size limits -------------------------------------------------------------

def test_upload_over_limit_rejected(client, make_user, monkeypatch):
    _, headers = make_user()
    monkeypatch.setattr(limits, "MAX_UPLOAD_BYTES", 10)
    assert _upload(client, headers).status_code == 413


def test_paste_over_limit_rejected(client, make_user, monkeypatch):
    _, headers = make_user()
    monkeypatch.setattr(limits, "MAX_PASTE_CHARS", 5)
    res = client.post("/api/data/paste", headers=headers, json={"text": "a,b\n1,2\n"})
    assert res.status_code == 413


# --- Rate limits -------------------------------------------------------------

def test_login_rate_limited_per_email(client, monkeypatch):
    async def no_user(email):
        return None

    monkeypatch.setattr(auth_router, "get_user_by_email", no_user)
    body = {"email": "victim@example.com", "password": "wrong"}
    for _ in range(limits.login_by_email.max_calls):
        assert client.post("/api/auth/login", json=body).status_code == 401
    res = client.post("/api/auth/login", json=body)
    assert res.status_code == 429
    assert "retry-after" in res.headers


def test_register_rate_limited_per_ip(client, monkeypatch):
    async def existing_user(email):
        return object()

    monkeypatch.setattr(auth_router, "get_user_by_email", existing_user)
    headers = {"X-Infera-Client-IP": "203.0.113.7"}
    for i in range(limits.register_by_ip.max_calls):
        res = client.post("/api/auth/register", headers=headers, json={"email": f"u{i}@example.com", "password": "pw"})
        assert res.status_code == 409
    res = client.post("/api/auth/register", headers=headers, json={"email": "x@example.com", "password": "pw"})
    assert res.status_code == 429
    # A different client IP is unaffected.
    res = client.post(
        "/api/auth/register", headers={"X-Infera-Client-IP": "203.0.113.8"},
        json={"email": "y@example.com", "password": "pw"},
    )
    assert res.status_code == 409


def test_chat_rate_limited_per_user(client, make_user, conversations, monkeypatch):
    make_conversation, _ = conversations
    user, headers = make_user()
    conv = make_conversation(user)

    async def fake_llm(messages, session_info):
        return "ok"

    monkeypatch.setattr(chat_router.llm_service, "is_configured", lambda: True)
    monkeypatch.setattr(chat_router.llm_service, "generate_chat_response", fake_llm)

    body = {"conversation_id": conv.id, "message": "hi"}
    for _ in range(limits.chat_by_user.max_calls):
        assert client.post("/api/chat", headers=headers, json=body).status_code == 200
    assert client.post("/api/chat", headers=headers, json=body).status_code == 429


# --- JWT secret --------------------------------------------------------------

def test_missing_jwt_secret_fails_startup():
    env = {k: v for k, v in os.environ.items() if k != "JWT_SECRET"}
    proc = subprocess.run(
        [sys.executable, "-c", "import backend.services.auth"],
        env=env, capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "JWT_SECRET" in proc.stderr
