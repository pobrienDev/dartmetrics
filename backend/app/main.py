"""DartMetrics API entry point.

Run locally with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description="Darts 501 scoring and player analytics.",
    )

    @app.get("/api/v1/health", tags=["system"])
    def health() -> dict[str, str]:
        """Liveness check used by deployment platforms and monitoring."""
        return {"status": "ok"}

    return app


app = create_app()
