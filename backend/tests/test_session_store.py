"""Durable session storage: D1 metadata + R2 Parquet, 7-day idle expiry."""
import asyncio
import io
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import session_store

CSV = b"score,group\n50,a\n55,b\n48,a\n60,b\n52,a\n58,b\n"


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def client(user):
    with TestClient(app, headers=user[1]) as c:
        yield c


def _upload(client):
    res = client.post("/api/data/upload", files={"file": ("data.csv", io.BytesIO(CSV), "text/csv")})
    assert res.status_code == 200
    return res.json()["session_id"]


def _run(client, session_id):
    res = client.post("/api/analysis/run", json={
        "session_id": session_id, "test_key": "descriptive", "config": {"variables": ["score"]},
    })
    assert res.status_code == 200
    return res.json()["result_id"]


def _simulate_restart():
    session_store._df_cache.clear()


def _age_session(fake_d1, session_id, days):
    old = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="microseconds")
    fake_d1.execute("UPDATE data_sessions SET last_used_at = ? WHERE id = ?", [old, session_id])


def test_session_survives_restart(client, fake_r2):
    session_id = _upload(client)
    assert client.post("/api/dataprep/missing", json={
        "session_id": session_id, "columns": ["score"], "strategy": "mean",
    }).status_code == 200
    result_id = _run(client, session_id)
    assert f"sessions/{session_id}.parquet" in fake_r2

    _simulate_restart()

    log = client.get(f"/api/export/log/{session_id}").json()
    assert [s["action"] for s in log["steps"]] == ["Import", "Data prep", "Analysis"]
    res = client.get(f"/api/analysis/results/{result_id}", params={"session_id": session_id})
    assert res.status_code == 200
    assert res.json()["interpretation"]["plain"]
    assert client.post(f"/api/export/report/{session_id}").status_code == 200
    assert client.post(f"/api/export/word/{result_id}", params={"session_id": session_id}).status_code == 200
    # The DataFrame reloads from R2 and analyses still run on it.
    _run(client, session_id)


def test_session_share_link_survives_restart(client):
    session_id = _upload(client)
    _run(client, session_id)
    token = client.post(f"/api/export/share-session/{session_id}").json()["token"]

    _simulate_restart()

    res = client.get(f"/api/share/session/{token}")
    assert res.status_code == 200
    assert res.json()["filename"] == "data.csv"
    assert len(res.json()["results"]) == 1


def test_session_expires_after_seven_idle_days(client, fake_d1):
    session_id = _upload(client)
    _age_session(fake_d1, session_id, days=8)
    assert client.get(f"/api/export/log/{session_id}").status_code == 404


def test_use_resets_idle_clock(client, fake_d1):
    session_id = _upload(client)
    _age_session(fake_d1, session_id, days=6)
    assert client.get(f"/api/export/log/{session_id}").status_code == 200
    (last_used,) = fake_d1.execute(
        "SELECT last_used_at FROM data_sessions WHERE id = ?", [session_id]
    ).fetchone()
    assert datetime.fromisoformat(last_used) > datetime.now(timezone.utc) - timedelta(minutes=1)


def test_cleanup_deletes_expired_sessions(client, fake_d1, fake_r2):
    expired = _upload(client)
    _run(client, expired)
    active = _upload(client)
    _age_session(fake_d1, expired, days=8)

    assert asyncio.run(session_store.delete_expired_sessions()) == 1

    remaining = [r[0] for r in fake_d1.execute("SELECT id FROM data_sessions")]
    assert remaining == [active]
    for table in ("session_steps", "session_results"):
        (n,) = fake_d1.execute(f"SELECT COUNT(*) FROM {table} WHERE session_id = ?", [expired]).fetchone()
        assert n == 0
    assert f"sessions/{expired}.parquet" not in fake_r2
    assert f"sessions/{active}.parquet" in fake_r2


def test_parquet_handles_mixed_types_and_non_string_columns(user):
    df = pd.DataFrame({0: [1, 2, 3], "mixed": [1, "two", None], "dates": pd.date_range("2024-01-01", periods=3)})

    async def roundtrip():
        sid = await session_store.create_session(df, "x.xlsx", user_id=user[0].id)
        _simulate_restart()
        return await session_store.get_owned_session(sid, user[0].id)

    session = asyncio.run(roundtrip())
    assert list(session.df.columns) == ["0", "mixed", "dates"]
    assert session.df["0"].tolist() == [1, 2, 3]
    assert session.df["mixed"].tolist() == ["1", "two", None]
    assert pd.api.types.is_datetime64_any_dtype(session.df["dates"])
