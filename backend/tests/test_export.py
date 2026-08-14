"""Integration tests for reproducibility log, report, and session-share endpoints."""
import io

import pytest
from fastapi.testclient import TestClient

from backend.main import app

CSV = b"score,pre,post\n50,40,45\n55,42,47\n48,38,44\n60,45,50\n52,41,46\n58,44,49\n49,39,43\n62,46,52\n51,40,45\n57,43,48\n"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session_id(client):
    res = client.post("/api/data/upload", files={"file": ("data.csv", io.BytesIO(CSV), "text/csv")})
    assert res.status_code == 200
    return res.json()["session_id"]


def _run_descriptive(client, session_id):
    res = client.post("/api/analysis/run", json={
        "session_id": session_id,
        "test_key": "descriptive",
        "config": {"variables": ["score"]},
    })
    assert res.status_code == 200
    return res.json()


def test_log_records_import_and_analysis_steps(client, session_id):
    _run_descriptive(client, session_id)
    res = client.get(f"/api/export/log/{session_id}")
    assert res.status_code == 200
    body = res.json()
    actions = [s["action"] for s in body["steps"]]
    assert actions == ["Import", "Analysis"]
    assert "data.csv" in body["steps"][0]["detail"]
    assert "Descriptive Statistics" in body["steps"][1]["detail"]


def test_log_records_dataprep_step(client, session_id):
    res = client.post("/api/dataprep/missing", json={
        "session_id": session_id, "columns": ["score"], "strategy": "mean",
    })
    assert res.status_code == 200
    log = client.get(f"/api/export/log/{session_id}").json()
    assert log["steps"][-1]["action"] == "Data prep"


def test_log_download_returns_text(client, session_id):
    _run_descriptive(client, session_id)
    res = client.get(f"/api/export/log/{session_id}/download")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    text = res.text
    assert "Import" in text
    assert "Analysis" in text


def test_log_unknown_session_404(client):
    res = client.get("/api/export/log/does-not-exist")
    assert res.status_code == 404


def test_report_bundles_multiple_results(client, session_id):
    r1 = _run_descriptive(client, session_id)
    r2 = client.post("/api/analysis/run", json={
        "session_id": session_id,
        "test_key": "correlation",
        "config": {"variables": ["pre", "post"]},
    }).json()

    res = client.post(f"/api/export/report/{session_id}", json={})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(res.content) > 0

    # Selecting a subset should still succeed
    res2 = client.post(f"/api/export/report/{session_id}", json={"result_ids": [r1["result_id"]]})
    assert res2.status_code == 200


def test_report_no_results_returns_422(client, session_id):
    res = client.post(f"/api/export/report/{session_id}", json={})
    assert res.status_code == 422


def test_session_share_roundtrip(client, session_id):
    _run_descriptive(client, session_id)
    client.post("/api/analysis/run", json={
        "session_id": session_id,
        "test_key": "correlation",
        "config": {"variables": ["pre", "post"]},
    })

    res = client.post(f"/api/export/share-session/{session_id}", json={})
    assert res.status_code == 200
    token = res.json()["token"]
    assert res.json()["url"] == f"/share/session/{token}"

    res2 = client.get(f"/api/share/session/{token}")
    assert res2.status_code == 200
    bundle = res2.json()
    assert bundle["filename"] == "data.csv"
    assert len(bundle["results"]) == 2


def test_session_share_unknown_token_404(client):
    res = client.get("/api/share/session/does-not-exist")
    assert res.status_code == 404
