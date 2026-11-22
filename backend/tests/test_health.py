"""Health endpoint tests: DB status must reflect a real connectivity check."""
from fastapi.testclient import TestClient

from app.api import router as router_module
from app.main import app

client = TestClient(app)


def test_health_reports_degraded_when_database_unreachable(monkeypatch):
    monkeypatch.setattr(router_module, "check_database_connection", lambda: (False, "OperationalError"))
    response = client.get("/api/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"]["status"] == "disconnected"
    assert body["application"] == "DIGI-VERSE"


def test_health_reports_connected_when_database_reachable(monkeypatch):
    monkeypatch.setattr(router_module, "check_database_connection", lambda: (True, None))
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"]["status"] == "connected"
    assert "environment" in body


def test_health_live_database_connection():
    """End-to-end check against the real configured PostgreSQL instance (no mocks)."""
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["application"] == "DIGI-VERSE"
    assert body["status"] == "healthy"
    assert body["database"]["status"] == "connected"
    assert body["database"]["error"] is None

