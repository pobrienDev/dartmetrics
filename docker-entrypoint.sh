#!/bin/sh
# Container entrypoint: migrate, then serve.
#
# Running `alembic upgrade head` here keeps the schema in the deploy flow
# on every host, including ones without a separate pre-deploy hook. It
# is a no-op when the database is already current. Set RUN_MIGRATIONS=0
# to skip it (e.g. when the platform runs migrations in its own step).
#
# --proxy-headers / --forwarded-allow-ips make uvicorn trust the
# platform's reverse proxy for the client IP and scheme, which the
# auth rate limiter relies on. The container is only reachable through
# that proxy, so trusting every upstream is safe here.
set -eu

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Applying database migrations..."
  alembic upgrade head
fi

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips '*'
