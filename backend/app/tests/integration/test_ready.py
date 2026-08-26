"""Integration test: readiness endpoint against real PostgreSQL.

Depends on the `engine` fixture so it skips (rather than fails) when
the database container is not running.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_ready_returns_200_with_real_database(engine):
    client = TestClient(app)
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
