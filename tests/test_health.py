import pytest


def test_health_and_frontend():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["version"]
    page = client.get("/")
    assert page.status_code == 200 and "Document extraction" in page.text
