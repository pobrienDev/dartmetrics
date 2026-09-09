"""DartMetrics API entry point.

Run locally with:
    uvicorn app.main:app --reload
"""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.router import me_router
from app.auth.router import router as auth_router
from app.matches.router import router as matches_router
from app.players.router import router as players_router
from app.statistics.router import router as statistics_router
from app.common.errors import DomainError
from app.common.ratelimit import limiter
from app.config import get_settings
from app.db import get_db


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description="Darts 501 scoring and player analytics.",
    )

    # Rate limiting: slowapi keeps counters in process memory, which is
    # sufficient for a single API instance. Only the auth routes declare
    # limits (see app/auth/router.py).
    limiter.enabled = settings.rate_limit_enabled
    app.state.limiter = limiter

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
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

    @app.exception_handler(RateLimitExceeded)
    def handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        """Too many attempts from one client — same envelope shape as
        every other error so the frontend needs no special case."""
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many attempts; please wait a minute and try again.",
                }
            },
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(IntegrityError)
    def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        """Backstop: a database constraint rejected a write that raced
        past application validation (e.g. two visits recorded at the
        same instant). The transaction rolled back; clients should
        refetch state and retry. Never a raw 500."""
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "CONFLICT",
                    "message": "The action conflicted with another change; refresh and retry.",
                }
            },
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

    # Production only: the container also serves the React build, so one
    # origin answers both the app and the API. Registered last so every
    # API route above wins over the catch-all.
    if settings.static_path is not None:
        _mount_frontend(app, settings.static_path)

    return app


class _ImmutableStaticFiles(StaticFiles):
    """Vite names bundled files by content hash, so they can be cached
    forever: a new deploy references new names from a fresh index.html."""

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def _mount_frontend(app: FastAPI, static_path: Path) -> None:
    """Serve the single-page app from Vite's dist/ directory.

    Hashed bundles live under /assets. Any other non-API path returns
    index.html so React Router owns the URL — /matches/<id> must load on
    a refresh or a shared link. index.html itself is never cached, so
    browsers pick up a new deploy on the next navigation.
    """
    static_root = static_path.resolve()
    index_html = static_root / "index.html"
    assets = static_root / "assets"
    if assets.is_dir():
        app.mount("/assets", _ImmutableStaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            # An unknown API path is a 404, never the app shell.
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (static_root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(static_root):
            return FileResponse(candidate)  # favicon.svg and other top-level files
        return FileResponse(index_html, headers={"Cache-Control": "no-cache"})


app = create_app()
