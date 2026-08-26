"""DartMetrics API entry point.

Run locally with:
    uvicorn app.main:app --reload
"""

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description="Darts 501 scoring and player analytics.",
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
