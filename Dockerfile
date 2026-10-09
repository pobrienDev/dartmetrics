# syntax=docker/dockerfile:1
# Production image: the FastAPI backend serving the built React app.
# One container, one origin, so no CORS configuration is needed.
#
#   docker build -t dartmetrics .
#   docker run --rm -p 8000:8000 --env-file .env dartmetrics
#
# The entrypoint applies Alembic migrations before starting uvicorn.

# Base images are pinned by digest (multi-arch manifest lists), so a build
# today and a build next month start from the same bytes. Bump them on
# purpose: `docker pull <tag>` then `docker image inspect --format
# '{{index .RepoDigests 0}}' <tag>`.
#   node:24-alpine = Node 24.21.0, python:3.12-slim = Python 3.12.15,
#   ghcr.io/astral-sh/uv = uv 0.12.24 (all as of 2026-10-09)

# ---- Stage 1: build the frontend -------------------------------------------
FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: the API image --------------------------------------------------
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
COPY --from=ghcr.io/astral-sh/uv@sha256:3af4716e991d6956a41e573eab705d0ee08500cd829ed30293eb8472f372c65a /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first so source edits don't invalidate this layer.
# Only the manifest and the lock file are in the image at this point, so
# Docker reuses the layer until the dependency set itself changes.
# --locked installs exactly the versions in uv.lock (the same ones CI
# tested) and fails if the lock no longer matches pyproject.toml.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# The application itself. Its dependencies are already installed, so this
# layer is small and quick to rebuild after a source edit.
COPY backend/app ./app
RUN uv sync --locked --no-dev --no-editable
ENV PATH="/app/.venv/bin:$PATH"

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# The frontend build; STATIC_DIR tells the app to serve it.
COPY --from=frontend /build/dist ./static
ENV STATIC_DIR=/app/static

RUN useradd --create-home --uid 1000 appuser \
    && chmod +x /usr/local/bin/docker-entrypoint.sh
USER appuser

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
