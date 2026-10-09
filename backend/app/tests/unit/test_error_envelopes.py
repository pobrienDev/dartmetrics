"""The global exception handlers' envelopes.

Every error the API sends is {"error": {"code", "message"}}. The
IntegrityError handler is the backstop for a write that raced past
application validation (the row lock makes that rare, see
integration/test_concurrency.py); nothing in the integration suite can
provoke it deterministically, so it is exercised here with a route
that raises the error the database would.
"""

from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.main import create_app


def test_integrity_error_becomes_a_409_conflict_envelope():
    app = create_app()
    router = APIRouter()

    @router.get("/api/v1/_raise-integrity-error")
    def boom() -> None:
        raise IntegrityError(
            "INSERT INTO turns ...", {}, Exception("duplicate key value violates uq_turns_leg_turn_number")
        )

    app.include_router(router)
    response = TestClient(app, raise_server_exceptions=False).get("/api/v1/_raise-integrity-error")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "CONFLICT",
            "message": "The action conflicted with another change; refresh and retry.",
        }
    }
