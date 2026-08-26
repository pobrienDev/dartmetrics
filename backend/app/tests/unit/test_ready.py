"""Unit test: the readiness endpoint reports 503 when the database
is unreachable. Uses FastAPI dependency overrides so no real database
is involved."""

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


class BrokenSession:
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", None, Exception("connection refused"))

    def close(self):
        pass


def override_broken_db():
    yield BrokenSession()


def test_ready_returns_503_when_database_is_down():
    app.dependency_overrides[get_db] = override_broken_db
    try:
        client = TestClient(app)
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable", "database": "down"}
    finally:
        app.dependency_overrides.clear()
