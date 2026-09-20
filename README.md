<p align="center">
  <img src="frontend/public/favicon.svg" width="72" alt="" />
</p>

<h1 align="center">DartMetrics</h1>

<p align="center">
  <strong>Every dart, counted.</strong><br />
  501, Cricket and Halve It scored dart by dart, with the averages, checkouts
  and 180s that fall out of the raw throws. Play a friend, a guest, or one of
  five bots.
</p>

<p align="center">
  <a href="https://dartmetrics.onrender.com"><strong>Live demo</strong></a> ·
  <a href="https://github.com/pobrienDev/dartmetrics/actions/workflows/ci.yml"><img src="https://github.com/pobrienDev/dartmetrics/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-10b981" alt="MIT license" /></a>
</p>

<p align="center">
  <img src="docs/screenshots/scoring-checkout.png" width="800" alt="Live scoring: Sam on 141 with the suggested checkout T20 T19 D12 shown under the score" />
</p>

> **Try it:** https://dartmetrics.onrender.com — register an account and
> play a best-of-1 against a bot; it takes about two minutes. It runs on
> free tiers, so the first request after 15 idle minutes takes about a
> minute while the container wakes.

## What it does

- **Three game modes.** 501 double-out, Cricket (race to close), and
  Halve It (house rules, nine rounds, start on 40). Rules for the
  latter two are specified in [docs/GAME_MODES.md](docs/GAME_MODES.md).
- **Per-dart scoring.** Every dart is stored, not just visit totals, so
  three-dart averages, first-nine averages, checkout percentages,
  highest visits and 180 counts are derived from the raw throws and can
  always be recomputed.
- **Live scoring that helps.** The score counts down as each dart goes
  in, a checkout suggestion appears whenever a finish is on, and busts,
  180s and checkouts each get their moment. Undo removes the last visit.
- **Five bot opponents**, Noob to Pro, driven by a pure throw simulator
  with tuned accuracy tables. Bot visits go through the same rules and
  statistics as human ones.
- **Match summaries and history.** Scoreline, per-player numbers and a
  leg-by-leg breakdown for every match; a filterable, paginated history.
- **A backend that defends the rules.** Pure scoring engines, a
  transactional turn service with row locking, and database check
  constraints that reject impossible states even if the app is bypassed.

## Screenshots

| Dashboard | Match summary |
|---|---|
| ![Dashboard with career KPIs and a match to resume](docs/screenshots/dashboard.png) | ![Match summary: scoreline, per-player stats, legs](docs/screenshots/summary.png) |

| Running score mid-visit | A 180 |
|---|---|
| ![Live score during a visit](docs/screenshots/scoring-live.png) | ![ONE HUNDRED AND EIGHTY](docs/screenshots/scoring-180.png) |

| Match history | New match | On a phone |
|---|---|---|
| ![History](docs/screenshots/history.png) | ![New match form](docs/screenshots/new-match.png) | ![Scoring on a phone](docs/screenshots/scoring-phone.png) |

<details>
<summary>Sign-in page</summary>

![Sign-in page with the dartboard](docs/screenshots/login.png)

</details>

## Architecture

```mermaid
flowchart LR
    subgraph Browser
        SPA["React 19 + TypeScript<br/>Vite · Tailwind v4 · TanStack Query"]
    end

    subgraph Container["One container (Render)"]
        direction TB
        API["FastAPI routers<br/>/api/v1/auth · players · matches · statistics"]
        SVC["Services<br/>turn service (row-locked, transactional)<br/>bot service · statistics"]
        ENG["Pure scoring engines<br/>501 · Cricket · Halve It · bot simulator<br/>(no framework, no DB)"]
        STATIC["Static SPA build<br/>index.html + hashed assets"]
        API --> SVC --> ENG
    end

    DB[("PostgreSQL (Neon)<br/>users · players · matches · legs<br/>leg_player_states · turns · dart_throws")]

    SPA -- "same-origin JSON + Bearer JWT" --> API
    SPA -. "served by" .-> STATIC
    SVC -- "SQLAlchemy 2 · Alembic" --> DB
```

Three ideas hold it together:

- **The backend is the source of truth.** Scoring is a pure domain engine
  (`backend/app/scoring/`) with no framework or database dependencies;
  services persist its results transactionally. The frontend mirrors a
  few rules only to decide when a visit is complete, and re-renders from
  the server's answer.
- **Store raw events, derive statistics.** `dart_throws` → `turns` →
  `legs` → `matches`. Nothing aggregated is stored, so every statistic
  can be recomputed and audited, and new ones need no migration.
- **The database defends the rules.** Check constraints reject a fourth
  dart, a bust that changes the score, or a remaining score of 1, even
  if application code is bypassed.

**Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Argon2 + JWT,
slowapi · React 19, TypeScript, Vite, Tailwind v4, TanStack Query,
React Router · pytest, Vitest, Playwright, GitHub Actions · Docker,
Render, Neon.

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
finish is on, the current Halve It round's target; in Cricket it
plays casual free-for-all, picking any open target at random rather
than marching from 20 down to the bull) and then simulates where the
dart lands from the difficulty's accuracy table. Missed triples
mostly drop into the big single; wilder misses stray into
neighbouring segments, landing in the neighbour's ring only about as
often as the bot hits the ring it aimed at; the worst bots sometimes
miss the board. Aiming at T20, the bots average about 24, 40, 63, 81
and 100 per three darts respectively.

Bot visits are recorded through the same turn service as human ones
(`POST /api/v1/matches/{id}/bot-visit`, called by the scoring screen
whenever the bot is up). Undo against a bot removes the bot's reply
and your visit before it, so you land back on the score you want to
re-enter.

## Authentication model

- Passwords are hashed with **Argon2id** (via pwdlib); plaintext never
  touches the database.
- Login issues a **stateless JWT access token** (HS256, 8-hour
  lifetime, `ACCESS_TOKEN_EXPIRE_MINUTES`) sent as an
  `Authorization: Bearer` header. Eight hours covers an evening of
  matches; the original 60 minutes expired mid-game.
- **Logout is client-side**: discard the token. There is deliberately no
  server-side logout endpoint — stateless tokens cannot be individually
  revoked without a denylist, and with a bounded lifetime the added
  infrastructure isn't justified for the MVP. Server-side revocation is
  planned for V1 together with refresh tokens.
- Deactivating a user takes effect immediately regardless of token
  lifetime, because every authenticated request re-checks `is_active`.
- **When a token stops working mid-session** (expiry or deactivation),
  the first 401 clears it, the app signs out, and the login page
  returns the user to the page they were on afterwards, so a match in
  progress can be resumed.

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
  8 hours. Moving to an HttpOnly cookie is planned for V1 alongside
  refresh tokens, since it also needs CSRF protection.
- **The OpenAPI docs (`/docs`) are public on purpose** — the API surface
  is documented, not secret, and every route needs a valid token.
- **Behind a reverse proxy**, run uvicorn with `--proxy-headers` and
  `--forwarded-allow-ips` so the rate limiter sees real client
  addresses. TLS termination and security headers (HSTS etc.) belong to
  that proxy layer.

## Local development

Requirements: Python 3.12+, Node.js 20+, Docker Desktop.

```bash
# 1. Configuration (defaults work for local development)
cp .env.example .env            # Windows: copy .env.example .env

# 2. Start PostgreSQL
docker compose up -d

# 3. Backend
cd backend
python -m venv .venv
.venv/bin/pip install -e . --group dev      # Windows: .venv\Scripts\pip ...
.venv/bin/alembic upgrade head
.venv/bin/pytest                            # 265 tests; integration tests skip without PostgreSQL
.venv/bin/uvicorn app.main:app --reload     # http://localhost:8000, docs at /docs

# 4. Frontend (second terminal)
cd frontend
npm ci
npm run dev                                 # http://localhost:5173, proxies /api to :8000
npm test                                    # Vitest
npx playwright test                         # end-to-end, needs both servers
```

### Sample data (local)

```bash
cd backend && .venv/bin/python -m app.seed_demo          # --reset rebuilds it
```

Creates a local account, `demo@dartmetrics.app` / `demo-darts`, with a
month of simulated 501, Cricket and Halve It matches against guests and
bots, plus one match to resume. Every visit is played through the real
services with darts from the bot simulator, so the history obeys every
rule. Useful for developing against populated screens and for the
screenshot tour below; the live site has no shared demo account.

### Screenshots

```bash
cd frontend && node scripts/screenshots.mjs
```

Re-seeds nothing itself: seed first, run both dev servers, and it drives
the app through Google Chrome to refresh `docs/screenshots/`.

## Deployment

The app ships as **one container**: a multi-stage `Dockerfile` builds the
React app with Node, then installs the backend on `python:3.12-slim` and
copies the build into the image. FastAPI serves the bundle (`STATIC_DIR`)
next to the API, so the deployed site is same-origin and needs no CORS.
The container runs as a non-root user.

On start, `docker-entrypoint.sh` applies Alembic migrations
(`alembic upgrade head`, a no-op when the schema is current) and then
starts uvicorn on `$PORT` (default 8000) with proxy headers trusted, so
the auth rate limiter sees real client addresses behind the platform's
load balancer. Set `RUN_MIGRATIONS=0` if the host runs migrations in its
own pre-deploy step.

`DATABASE_URL` accepts the `postgres://` and `postgresql://` forms that
managed databases hand out; the app pins the psycopg driver itself.

### Render + Neon (free)

The live site, https://dartmetrics.onrender.com, runs on Render's free web service with the database on Neon's
free PostgreSQL tier. Render's own free databases are deleted after 30
days; Neon's free tier (0.5 GB, 100 compute-hours a month, scales to
zero when idle) has no expiry, so the site can sit idle indefinitely.

1. **Neon:** create a project at https://neon.tech and copy its
   connection string (it looks like
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`).
2. **Render:** **New → Blueprint** in the dashboard, pick this
   repository. `render.yaml` describes the Docker web service; Render
   prompts for `DATABASE_URL` (paste the Neon string), generates a
   `SECRET_KEY`, and health-checks `/api/v1/health`.
3. The first deploy builds the image and the container applies the
   migrations against Neon on start. Every push to `main` redeploys.

Free web services sleep after 15 idle minutes; the first request
afterwards takes about a minute while the container starts. Neon
wakes in a second or two.

### Running the image locally

```
docker build -t dartmetrics .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgres://dartmetrics:dartmetrics_dev@host.docker.internal:5432/dartmetrics \
  -e SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))") \
  dartmetrics
```

Then open http://localhost:8000. This uses the PostgreSQL started by
`docker compose up -d`.

## Project layout

```
backend/
  app/
    scoring/      pure game engines + bot simulator (no framework dependencies)
    auth/         accounts, Argon2 + JWT
    players/      players: linked to a user, guests, and the five bots
    matches/      Match, Leg, LegPlayerState, Turn, DartThrow + the turn service
    statistics/   career stats, head-to-head, match summaries
    common/       domain errors, security helpers, rate limiter
    seed_demo.py  demo account + history
    tests/        unit and PostgreSQL integration suites
  alembic/        database migrations
frontend/
  src/pages/      dashboard, new match, live scoring, summary, history, auth
  src/components/ app header, auth layout, dartboard, logo
  src/utils/      checkout table, cricket marks, dart helpers
  e2e/            Playwright journey
  scripts/        README screenshot tour
docs/             game mode rules, project status, screenshots
Dockerfile          production image: frontend build + backend, migrations on start
docker-entrypoint.sh
render.yaml         Render Blueprint (web service; database on Neon)
docker-compose.yml  local PostgreSQL
```

## License

MIT — see [LICENSE](LICENSE).
