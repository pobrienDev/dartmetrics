# DartMetrics

A darts league, scoring, and player analytics platform.

Records 501 matches at per-dart granularity and derives player statistics
(three-dart average, checkout percentage, 180 counts, head-to-head) from
raw throw data.

**Status:** Phase 0 complete — scoring rules, domain engine, core entities,
PostgreSQL schema, and test suite.

## Stack

- Backend: FastAPI (upcoming), SQLAlchemy 2.x, Alembic, PostgreSQL
- Frontend: React + TypeScript (later phase)
- Tooling: Docker, pytest, GitHub Actions (upcoming)

## Supported 501 rules

DartMetrics implements standard steel-tip **501, straight-in, double-out**:

- Each leg starts with both players on 501. No double is required to begin
  scoring (straight-in).
- Players alternate visits of up to three darts. The leg's starting player
  is chosen at setup.
- Board values: singles 1–20, doubles D1–D20, triples T1–T20, outer bull
  (25), inner bull (50). The inner bull counts as **double 25** and is a
  legal finishing dart.
- A leg is won only when a dart brings the remaining score to **exactly 0**
  and that dart is a **double or the inner bull**.
- A visit **busts** when a dart takes the remaining score below 0, to
  exactly 1, or to 0 without finishing on a double. A bust discards the
  whole visit: the player returns to the score they had before it. The
  bust darts stay recorded for audit, scoring 0 effective points.
- Matches are **best-of-N legs** where N is a positive odd number; the
  winner is the first to `floor(N/2) + 1` legs.

The full rule interpretation, entity model, and acceptance cases live in
the Phase 0 specification; the scoring engine's unit tests mirror its
acceptance matrix one-to-one (`app/tests/unit/test_engine.py`, cases
S01–S16).

### Design principles

- **The backend is the source of truth.** Scoring is a pure domain engine
  (`app/scoring/`) with no framework or database dependencies; services
  persist its results transactionally.
- **Store raw events, derive statistics.** Every dart is stored
  (`dart_throws` → `turns` → `legs` → `matches`), so statistics can always
  be recomputed and audited.
- **The database defends the rules.** Check constraints reject impossible
  states (a fourth dart, a bust that changes the score, a remaining score
  of 1) even if application code is bypassed.

## Local development

Requirements: Python 3.12+, Docker Desktop.

```
# 1. Configuration (defaults work for local development)
copy .env.example .env

# 2. Start PostgreSQL
docker compose up -d

# 3. Backend environment
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -e . --group dev

# 4. Apply database migrations
.venv\Scripts\alembic upgrade head

# 5. Run the tests (40 unit + 4 PostgreSQL integration)
.venv\Scripts\pytest
```

Integration tests skip automatically if PostgreSQL is not running.

## Project layout

```
backend/
  app/
    scoring/      pure 501 domain engine (no framework dependencies)
    auth/         User model (accounts)
    players/      Player model (competitors; guests supported)
    matches/      Match, Leg, LegPlayerState, Turn, DartThrow + turn service
    common/       domain error types
    tests/        unit and integration suites
  alembic/        database migrations
docker-compose.yml  local PostgreSQL
```
