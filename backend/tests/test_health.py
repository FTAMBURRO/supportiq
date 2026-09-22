"""Tests for GET /api/health."""


def test_health_returns_200(client):
    response = client.get("/api/health")

    assert response.status_code == 200


def test_health_returns_ok_status(client):
    response = client.get("/api/health")

    assert response.get_json() == {"status": "ok"}
