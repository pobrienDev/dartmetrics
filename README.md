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

## Bot opponents

Any game mode can be played against a computer opponent. Five shared
bots exist, easiest to hardest: **Noob, Easy, Medium, Hard, Pro**.
Each is an ordinary guest player with `bot_difficulty` set, so bot
matches appear in history and statistics like any other.

The bot engine (`app/scoring/bot.py`) is pure: it chooses a sensible
aim (T20 while scoring, the right double or a setup shot when a
finish is on, the highest open Cricket target, the current Halve It
round's target) and then simulates where the dart lands from the
difficulty's accuracy table. Missed triples mostly drop into the big
single; wilder misses stray into neighbouring segments; the worst
bots sometimes miss the board. Aiming at T20, the bots average about
32, 47, 63, 81 and 100 per three darts respectively.

Bot visits are recorded through the same turn service as human ones
(`POST /api/v1/matches/{id}/bot-visit`, called by the scoring screen
whenever the bot is up). Undo against a bot removes the bot's reply
and your visit before it, so you land back on the score you want to
re-enter.

## Authentication model

- Passwords are hashed with **Argon2id** (via pwdlib); plaintext never
  touches the database.
- Login issues a **stateless JWT access token** (HS256, 60-minute
  lifetime) sent as an `Authorization: Bearer` header.
- **Logout is client-side**: discard the token. There is deliberately no
  server-side logout endpoint — stateless tokens cannot be individually
  revoked without a denylist, and with a 60-minute lifetime the added
  infrastructure isn't justified for the MVP. Server-side revocation is
  planned for V1 together with refresh tokens.
- Deactivating a user takes effect immediately regardless of token
  lifetime, because every authenticated request re-checks `is_active`.

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

## Security notes

- **Credential endpoints are rate limited** (`slowapi`, default 10
  requests per minute per client IP for login and register, tunable via
  `AUTH_RATE_LIMIT`). Argon2 verification is deliberately slow, so without
  a limit those two routes are both a brute-force and a CPU-exhaustion
  target. Over the limit returns `429 RATE_LIMITED` with `Retry-After`.
  Counters live in process memory, which suits a single API instance;
  a shared store would be needed to scale out.
- **The placeholder `SECRET_KEY` is refused at startup**, as is any key
  under 32 characters, so a copied `.env.example` cannot go to production
  with forgeable tokens.
- **CORS is off unless `CORS_ORIGINS` is set.** The dev proxy and a
  single-host deployment are same-origin and need nothing; a split
  frontend/API deployment lists its frontend origin there.
- **Match state and summaries are private** to the creator and the
  players in the match, the same rule that governs recording visits.
  Other signed-in users get `403 MATCH_ACCESS_DENIED`.
- **The access token is kept in `localStorage`.** That makes it readable
  by any script injected into the page. React escapes all rendered
  values and the app never renders raw HTML, and the token expires after
  60 minutes. Moving to an HttpOnly cookie is planned for V1 alongside
  refresh tokens, since it also needs CSRF protection.
- **The OpenAPI docs (`/docs`) are public on purpose** — the API surface
  is documented, not secret, and every route needs a valid token.
- **Behind a reverse proxy**, run uvicorn with `--proxy-headers` and
  `--forwarded-allow-ips` so the rate limiter sees real client
  addresses. TLS termination and security headers (HSTS etc.) belong to
  that proxy layer.

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
    scoring/      pure game engines + bot simulator (no framework dependencies)
    auth/         User model (accounts)
    players/      Player model (competitors; guests and bots supported)
    matches/      Match, Leg, LegPlayerState, Turn, DartThrow + turn service
    common/       domain error types
    tests/        unit and integration suites
  alembic/        database migrations
docker-compose.yml  local PostgreSQL
```
