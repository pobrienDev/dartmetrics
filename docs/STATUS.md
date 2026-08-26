# Development status

> Living document: where the project stands, key decisions, and what
> comes next. Update at the end of significant work sessions.

**Last updated:** 2026-08-26

## Where things stand

Phases 0-8 of the development plan are substantially complete. The app
is fully playable end to end: register → create match → live per-dart
scoring → winner screen → history → career statistics.

- **Backend** (FastAPI + SQLAlchemy + PostgreSQL): pure 501 scoring
  engine, per-dart schema (7 tables, Alembic migration `a838f4f2385a`),
  Argon2 auth + JWT, player profiles with ownership rules, transactional
  match/visit/undo/abandon API with row locking, match listing,
  statistics + head-to-head. **130 tests** (unit + PostgreSQL
  integration with rollback isolation).
- **Frontend** (React 19 + TS + Vite + Tailwind v4): auth flow,
  dashboard with live KPI cards, new-match form, live scoring screen
  (5-column pad on phones, 7 on desktop; all touch targets ≥44px),
  match history with filters/pagination. **25 Vitest/RTL tests** plus
  **2 Playwright e2e** journeys.
- **CI** (.github/workflows/ci.yml): backend-tests, frontend-tests,
  e2e — three jobs with a PostgreSQL service. NOTE: pushed during a
  GitHub Actions major outage on 2026-08-26; verify the run backlog
  went green once Actions recovered.

## Source-of-truth documents

The Phase 0 specification (scoring rules + entity model) and the
Development Plan are Word documents kept outside the repo. **The Phase 0
spec is authoritative** where they differ (per-dart storage, not
visit-level). The README summarises the implemented 501 rules.

## Key decisions (chronological)

- Bulls modeled as segment 25: outer = single 25, inner = double 25
  (so `is_double` covers checkout legality with no special case).
- Store raw events (turns + dart_throws); derive all statistics at
  query time. Percentages are null, never 0%, on empty samples.
- Turn order derived from turns_taken parity — not stored.
- Checkout attempts inferred: dart thrown while score was
  double-finishable (even 2-40, or 50). Documented in
  `backend/app/matches/service.py`.
- Stateless JWT (60 min); logout is client-side token discard —
  server-side revocation deferred to V1 with refresh tokens (README
  "Authentication model").
- Matches start immediately on creation (no pre-match state);
  leg starters alternate automatically.
- Undo = latest visit in the active leg only; completed legs immutable.
- `created_at` stamped app-side (Postgres `now()` is transaction start
  time — rows created in one transaction would tie).
- Visit recording takes `SELECT FOR UPDATE` on leg player states;
  IntegrityError → 409 CONFLICT envelope (race found in browser testing).
- Alembic migration gotcha: `%` in CHECK constraints must be
  single-escaped in migration files (autogenerate writes `%%`, which
  double-escapes).
- email-validator rejects `.test` TLD addresses — tests use example.com.

## Development workflow

- Work in small, explained, verified steps; stop for confirmation at
  decision points; never silently deviate from the plan documents.
- Group related changes into coherent commits; push once per work chunk.
- Verify claims by running them (tests, live servers, real browser)
  before committing; document deviations and tradeoffs in the README.

## Game modes (in progress)

Rules for Cricket (race to close) and Halve It (house rules) are
specified in docs/GAME_MODES.md — that file is authoritative.
Completed: schema (game_type/game_config/game_state/single_band
migration `1f4e6601cae7`), Cricket engine + API + UI (marks grid,
game picker, cricket-aware undo via raw-dart replay), 501 statistics
scoped to x01 matches. Remaining: Halve It engine + API + UI
(different turn structure: both players play every numbered round,
no early end, halving on miss, exact-63 round, band-aware singles
input using dart_throws.single_band).

## Next up

1. Halve It implementation (see above).
2. Security checklist review + production config (CORS allowlist,
   secure cookie/token settings, rate limiting decision) — pairs with:
3. Phase 9 deployment: backend Dockerfile, managed PostgreSQL,
   public frontend + backend hosting, migrations in the deploy flow.
4. Phase 10 portfolio polish: README hero/screenshots, architecture
   diagram, seed/demo data, release tag v0.1.0.
5. Later (V1): refresh tokens + revocation, Elo, 301, leagues,
   trend charts, player comparison.

## Local setup

See the README "Local development" section — it is kept accurate and
was verified on a fresh environment. Requirements: Python 3.12+,
Node.js, Docker Desktop. Secrets live in an untracked `.env` created
from `.env.example` (generate your own SECRET_KEY).
