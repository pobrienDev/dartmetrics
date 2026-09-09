# Development status

> Living document: where the project stands, key decisions, and what
> comes next. Update at the end of significant work sessions.

**Last updated:** 2026-09-08

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

## Game modes (complete)

Three playable game modes: 501, Cricket (race to close), and Halve It
(house rules). Rules are specified in docs/GAME_MODES.md — that file
is authoritative. Implementation: schema migration `1f4e6601cae7`
(game_type/game_config/game_state/single_band); per-game pure engines
in app/scoring/; the turn service dispatches by game type behind
shared validation; undo replays raw darts for Cricket and Halve It;
Halve It leg completion credits the higher score (winner can differ
from the final thrower) and ties extend into Red Bull rounds; 501
statistics are scoped to x01 matches. UI: game picker, Cricket marks
grid, Halve It round/score display with inner-outer band toggle.
Backend 182 tests, frontend 30 + 2 e2e.

**2026-09-08:** Halve It now starts both players on 40 instead of 0
(house rule: a missed opening round already halves something).
`STARTING_SCORE` in app/scoring/halve_it.py is the single source;
leg setup, undo replay and the state reader use it, and the game
picker hint says "start on 40". Legs created before this keep their
stored scores.

## Bot opponents (complete, 2026-09-08)

Five shared bot players (noob/easy/medium/hard/pro) live in the
players table with `bot_difficulty` set (migration `3c9d2b7e5a10`).
`GET /api/v1/players/bots` creates them on first use; the human
player list excludes them. The engine in app/scoring/bot.py is pure
(aim + accuracy-driven throw, seeded RNG in tests) and covers all
three game modes; `POST /matches/{id}/bot-visit` feeds its darts
through the normal turn service. The scoring screen auto-triggers the
bot after a 1.2 s pause and shows the darts it threw. Undo past a
bot reply also removes the preceding human visit. Accuracy tables are
tuned to ~32/47/63/81/100 three-dart averages when aiming T20.
Backend 229 tests, frontend 32 + 2 e2e.

## Next up

1. Security checklist review + production config (CORS allowlist,
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
