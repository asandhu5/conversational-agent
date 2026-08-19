import dataclasses

import pytest

import app as app_module
from backend.store import SessionStore
from scripts.seed_demo_data import seed_if_needed


@pytest.fixture
def client():
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


@pytest.fixture
def unconfigured_tavus(monkeypatch):
    fake = dataclasses.replace(app_module.config, tavus_api_key="", tavus_replica_id="", tavus_persona_id="")
    monkeypatch.setattr(app_module, "config", fake)
    return fake


@pytest.fixture
def seeded_demo_session(tmp_path, monkeypatch, fake_ml_pipelines):
    temp_store = SessionStore(tmp_path / "sessions")
    monkeypatch.setattr(app_module, "store", temp_store)
    seeded = seed_if_needed(temp_store, fixtures_dir=app_module.config.data_dir.parent / "tests" / "fixtures")
    assert seeded > 0
    session_id = temp_store.list_sessions()[0]["id"]
    return session_id


def test_index_page_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Interview Coach" in resp.data


def test_history_page_loads_empty(client, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "store", SessionStore(tmp_path / "sessions"))
    resp = client.get("/history")
    assert resp.status_code == 200
    assert b"No interviews yet" in resp.data


def test_unknown_session_redirects_to_index(client):
    assert client.get("/report/does-not-exist").status_code == 302
    assert client.get("/interview/does-not-exist").status_code == 302


def test_api_start_without_tavus_config_returns_400(client, unconfigured_tavus):
    resp = client.post("/api/start", json={"role": "ml-engineer", "candidate_name": "Alex"})
    assert resp.status_code == 400
    assert "aren't configured" in resp.get_json()["error"]


def test_report_renders_for_seeded_session(client, seeded_demo_session):
    resp = client.get(f"/report/{seeded_demo_session}")
    assert resp.status_code == 200
    assert b"chart-sentiment" in resp.data
    assert b"Coach" in resp.data


def test_history_lists_seeded_session(client, seeded_demo_session):
    resp = client.get("/history")
    assert resp.status_code == 200
    assert b"Machine Learning Engineer" in resp.data


def test_export_report_markdown(client, seeded_demo_session):
    resp = client.get(f"/api/export/{seeded_demo_session}/report")
    assert resp.status_code == 200
    assert resp.data.startswith(b"# Interview Report")


def test_export_transcript(client, seeded_demo_session):
    resp = client.get(f"/api/export/{seeded_demo_session}/transcript")
    assert resp.status_code == 200
    assert b"Q1:" in resp.data


def test_demo_route_redirects_to_a_report(client, seeded_demo_session):
    resp = client.get("/demo")
    assert resp.status_code == 302
    assert "/report/" in resp.headers["Location"]
