# syntax=docker/dockerfile:1
# Production image: the FastAPI backend serving the built React app.
# One container, one origin, so no CORS configuration is needed.
#
#   docker build -t dartmetrics .
#   docker run --rm -p 8000:8000 --env-file .env dartmetrics
#
# The entrypoint applies Alembic migrations before starting uvicorn.

# ---- Stage 1: build the frontend -------------------------------------------
FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: the API image --------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so source edits don't invalidate this layer.
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install .

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
