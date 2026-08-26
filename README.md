# DartMetrics

A darts league, scoring, and player analytics platform.

Records 501 matches at per-dart granularity and derives player statistics
(three-dart average, checkout percentage, 180 counts, head-to-head) from
raw throw data.

**Status:** Phase 0 — scoring rules and core entities.

## Stack

- Backend: FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL
- Frontend: React + TypeScript (later phase)
- Tooling: Docker, pytest, GitHub Actions
