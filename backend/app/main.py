"""DartMetrics API entry point.

Run locally with:
    uvicorn app.main:app --reload
"""

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.router import me_router
from app.auth.router import router as auth_router
from app.matches.router import router as matches_router
from app.players.router import router as players_router
from app.statistics.router import router as statistics_router
from app.common.errors import DomainError
from app.config import get_settings
from app.db import get_db


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description="Darts 501 scoring and player analytics.",
    )

    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(players_router)
    app.include_router(matches_router)
    app.include_router(statistics_router)

    @app.exception_handler(DomainError)
    def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        """Every domain rule violation becomes the plan's error envelope:
        {"error": {"code": ..., "message": ...}} with a suitable status."""
        headers = {"WWW-Authenticate": "Bearer"} if exc.http_status == 401 else None
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": str(exc)}},
            headers=headers,
        )

    @app.get("/api/v1/health", tags=["system"])
    def health() -> dict[str, str]:
        """Liveness check: the process is up and serving HTTP."""
        return {"status": "ok"}

    @app.get("/api/v1/ready", tags=["system"])
    def ready(db: Session = Depends(get_db)) -> JSONResponse:
        """Readiness check: the app can reach PostgreSQL."""
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(
                status_code=503, content={"status": "unavailable", "database": "down"}
            )
        return JSONResponse(status_code=200, content={"status": "ready"})

    return app


app = create_app()
