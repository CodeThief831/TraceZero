"""Tests for the FastAPI web endpoints using TestClient."""

from fastapi.testclient import TestClient

from humanlens.web.app import app

client = TestClient(app)


def test_home_and_health():
    r_home = client.get("/")
    assert r_home.status_code == 200
    assert "HumanLens" in r_home.text

    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    data = r_health.json()
    assert data["status"] == "ok"
    assert "fakespot" in data["models"]


def test_api_scan_and_humanize_fast_mode():
    sample = (
        "Furthermore, it is crucial to leverage robust encryption across all endpoints. "
        "Additionally, teams do not want downtime."
    )
    r_scan = client.post("/api/scan", json={"text": sample, "use_neural": False, "use_perplexity": False})
    assert r_scan.status_code == 200
    assert r_scan.json()["overall_ai_score"] >= 20.0

    r_hum = client.post("/api/humanize", json={"text": sample, "rescore_neural": False})
    assert r_hum.status_code == 200
    payload = r_hum.json()
    assert payload["after_score"] <= payload["before_score"]
    assert "furthermore" not in payload["humanized_text"].lower()
