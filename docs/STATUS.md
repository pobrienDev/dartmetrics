# Development status

> Living document: where the project stands, key decisions, and what
> comes next. Update at the end of significant work sessions.

**Last updated:** 2026-09-18 (casual Cricket bots, noob and easy retune)

## Where things stand

Phases 0-9 of the development plan are complete. The app is fully
playable end to end and live at https://dartmetrics.onrender.com:
register → create match → live per-dart scoring → winner screen →
history → career statistics.

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

**2026-09-10 bot retune (Halve It):** the easy bot felt too strong at
Halve It. Cause: a missed double/triple that strayed into a
neighbouring segment landed in that neighbour's *ring* a flat 40% of
the time at every difficulty, and aiming at the outer bull carried a
flat +12% bonus — so "any double", "any triple" and "green bull"
rounds were nearly skill-free (easy qualified on doubles 64% vs noob
62%). Fix in app/scoring/bot.py: neighbour-ring chance now equals the
bot's own ring hit chance, and the outer-bull bonus scales with
inner-bull skill. Noob/easy accuracy tables retuned (triple/double/
single up, scatter down) so T20 averages stay on 32/47; medium and up
unchanged. Simulated Halve It medians (9 rounds from 40): noob 11,
easy 33, medium 84, hard 195, pro 338 (were 17/44/92/197/324);
easy now qualifies on the any-double round 48% of the time (was 64%).
Second pass the same day, still too strong in play: the plain-single
hit rate (unconstrained by the T20 tuning, and what the four band
rounds run on) was 65% for easy and 50% for noob, well above a
scatter-model estimate of ~45% / ~35% for their averages. Lowered to
0.46 / 0.36 (band 0.55 / 0.50, inner bull 0.06 / 0.03). Halve It
medians now noob 9, easy 25 (easy ends on or below 40 in 67% of
games); medium and up untouched; T20 averages unchanged.

**2026-09-10 session expiry bug:** a Halve It match ran past the
60-minute token lifetime; the next visit failed with a raw "Invalid
or expired token." banner on the scoring screen and nothing signed
the user out. Fixed: the API client drops the token on any 401 while
signed in and dispatches `SESSION_EXPIRED_EVENT`; AuthContext signs
out; ProtectedRoute redirects to login with the current path in
router state; LoginPage explains and returns there after sign-in.
Token lifetime default raised 60 → 480 minutes (an evening of
matches), in config.py, .env.example, render.yaml and the README.
Also fixed: Halve It rows in the scoring page's Recent visits showed
x01-style "0 (0 → 0)"; they now show "+N" or "HALVED".

**2026-09-18 casual Cricket bots:** the bots played Cricket as a rigid
march, highest open number every dart and the bull last, so every leg
went 20, 19, 18, 17, 16, 15, Bull and felt robotic. Race-to-close has
no points, so the order gains nothing. `choose_cricket_aim` in
app/scoring/bot.py now picks any open target at random, stays on it
for the visit until it closes, and re-picks each visit; numbers still
aim at the triple and the bull at the inner ring. Simulated average
visits to close the board are unchanged at every difficulty (noob ~21,
easy ~13, medium ~9, hard ~7, pro ~6), so the bots are as beatable as
before, just less predictable. README and the unit tests updated
(six Cricket aiming tests replace the highest-first one). Commit
560c5ec.

**2026-09-18 noob retune:** the noob bot was still far too good for a
beginner: a 32 three-dart average, the aimed-at segment hit a third
of the time, a Cricket board closed in ~21 visits and a 501 leg in
~28, which is a competent pub player. Accuracy table lowered to
triple 0.03, double 0.05, single 0.28, inner/outer bull 0.02/0.08,
board miss 0.20, scatter 0.70 (was 0.06/0.07/0.36/0.03/0.12/0.12/
0.65; band unchanged at 0.50). Simulated: T20 average 24 (the
difficulty picker's hint is now "~25 avg"), segment hit rate 26%,
501 leg ~40 visits (worst of 400 seeds: 204 darts, inside the test's
400-dart bound), Cricket board ~30 visits, Halve It median 2 from
40. Easy and up untouched, so the noob→easy step is now 24→47; bring
easy down to ~40 if that gap plays badly.

**2026-09-18 easy retune:** easy brought down as well, to narrow that
step: triple 0.08, double 0.10, single 0.42, inner/outer bull
0.05/0.16, band 0.53, board miss 0.07, scatter 0.58 (was 0.11/0.14/
0.46/0.06/0.20/0.55/0.05/0.53). Simulated: T20 average 40 (hint now
"~40 avg"), segment hit rate 44%, plain-single rate 39%, 501 leg ~20
visits (was ~16), Cricket board ~16 visits (was ~13), Halve It median
17 from 40 (was 24; ends on or below 40 in 77% of games). The ladder
is now 24 / 40 / 63 / 81 / 100; medium and up untouched.

## Security hardening (complete, 2026-09-09)

Reviewed auth, config, access rules, error handling, and the API
client. Added: slowapi rate limit on login/register (10/min per IP,
`AUTH_RATE_LIMIT`, 429 `RATE_LIMITED` envelope); startup refusal of
the placeholder or a short `SECRET_KEY`; opt-in CORS allowlist
(`CORS_ORIGINS`, off by default because the app is same-origin);
match state/summary reads restricted to creator + participants
(previously any signed-in user could read any match by UUID). Accepted
tradeoffs are written up in the README "Security notes" section
(localStorage token, public /docs, proxy headers at deploy time).
Tests disable the limiter in the shared client fixture and re-enable
it in test_security_hardening.py.

## Phase 9 deployment (complete, 2026-09-09)

Decisions: host on **Render's free web service** via a Blueprint
(`render.yaml`), with the database on **Neon's free PostgreSQL** rather
than a Render database (Render's free databases are deleted after 30
days; Neon's free tier has no expiry and scales to zero). Serve the
frontend **from the API container** so production stays same-origin
(no CORS, one deploy). Options compared on 2026-09-09: Koyeb + Neon is
the free fallback if Render's cold starts annoy; Hetzner VPS (~€4/mo,
docker compose) is the paid upgrade path and the Dockerfile carries
over unchanged. Done so far:

- Multi-stage `Dockerfile` (Node builds Vite dist → python:3.12-slim
  image, non-root user) and `.dockerignore`.
- `docker-entrypoint.sh` runs `alembic upgrade head` then uvicorn on
  `$PORT` with `--proxy-headers --forwarded-allow-ips '*'`
  (`RUN_MIGRATIONS=0` opts out). Migrations live in the entrypoint
  rather than Render's `preDeployCommand` because that hook is not
  available on free instances.
- `STATIC_DIR` setting: FastAPI mounts `/assets` with immutable cache
  headers and serves `index.html` (no-cache) for every non-API path so
  React Router deep links survive refresh; `/api/*` unknowns stay 404.
- `DATABASE_URL` normalisation: `postgres://` / `postgresql://` become
  `postgresql+psycopg://` (managed databases hand out the bare form);
  query strings such as Neon's `?sslmode=require` pass through. Alembic's
  env.py uses the same helper and escapes `%` for ConfigParser.
- CI gained a `docker-build` job so the image cannot silently break.
- Verified locally: image built, ran against the compose database with
  a `postgres://` URL, migrations applied, register/login/dashboard
  worked in the browser through the container. Backend 248 tests.

**Live: https://dartmetrics.onrender.com** (Render web service
`dartmetrics`, Ohio, deployed from the `dartmetrics` Blueprint; Neon
project `dartmetrics`, AWS us-east-2, Postgres 16, direct connection
string as `DATABASE_URL`). First deploy from commit `2750367`: schema
migrated, health/ready green, SPA deep links and asset caching verified
through the public URL. Every push to `main` redeploys via the Blueprint
sync. The Neon password was rotated after setup.

## Visual overhaul, batch 1 (2026-09-09)

Reviewed every screen at desktop and phone widths before Phase 10 and
shipped the highest-impact set:

- **Dark theme across the app** with design tokens in
  `frontend/src/index.css` (`ink` greys, `felt` green, gold, bust red),
  Barlow Condensed for headings and scores, Inter for text (Google
  Fonts, with system fallbacks). Shared classes (`card`, `btn-*`,
  `input`, `choice-*`, `label`, `score-display`) are Tailwind v4
  `@utility` declarations — v4 refuses `@apply` on classes from a
  components layer.
- **Shared chrome:** `AppHeader` (logo, nav, New Match, sign out),
  `Logo`/`BoardGlyph`, `AuthLayout` with an SVG `Dartboard` on the
  login and register pages. New dartboard favicon; Vite's leftover
  icons.svg removed.
- **Scoring screen:** live remaining score while darts are entered;
  checkout hints from a standard-out table (`utils/checkouts.ts`,
  fits the darts left in the visit, null for bogey numbers); bust
  (shake, red), 180 (gold flash, "ONE HUNDRED AND EIGHTY!"), 100+
  (gold) and checkout (green flash) moments driven by the server's
  verdict; bot names lose the " Bot" suffix next to the BOT chip;
  Bull key restyled; winner screen links to the summary.
- **Match summary page** at `/matches/:id/summary`: scoreline, winner,
  per-player table (darts, average, high visit, 100+/140+/180s,
  checkout %) and leg-by-leg results. Backend summary now returns
  `game_type` and `legs[]` with per-player darts. History links
  finished matches here and in-progress ones to scoring.
- Dashboard: first-visit empty state (hidden when a match is
  resumable), display-font KPI cards.

Frontend 42 tests (+10: checkouts table, scoring feedback, summary
page), backend 249. Verified in the browser: live score, hint, 180
moment, bot reply, summary, phone layout. Playwright e2e left to CI
(no local browser binary installed).

Still on the visual list: bot darts animating in one at a time,
KPI sparklines/trends, page transitions, a match summary link from
the dashboard resume row.

## Phase 10 portfolio polish (2026-09-13)

- **README rewritten as a landing page:** hero with tagline, CI and
  license badges, live-demo link and demo credentials, a screenshot
  grid, a Mermaid architecture diagram, a "what it does" list, then the
  carried-over rules, bot, auth, security, local-dev and deployment
  sections. Local-dev commands now given for macOS/Linux with Windows
  variants.
- **Demo data:** `backend/app/seed_demo.py` creates
  `demo@dartmetrics.app` / `demo-darts` with 13 backdated matches
  (501, Cricket, Halve It vs guests and bots, played through the real
  services with bot-simulator darts from tuned personas) plus one live
  match with Sam on 321. `--reset` rebuilds; seeded RNG.
- **Screenshots:** `frontend/scripts/screenshots.mjs` drives the app
  with Playwright through the locally installed Google Chrome (no
  browser download) and writes nine PNGs to `docs/screenshots/`
  (2x desktop, 3x phone). Re-run after UI changes: seed, start both
  dev servers, run the script.
- Login hero: dartboard anchored bottom-right so the headline stays
  clear.
- Decided against a shared demo account on the live site (anyone could
  mess it up; a public password; synthetic history). The seed script
  stays as local sample data for development and screenshots; the
  README tells visitors to register and play a best-of-1 against a bot.
- **Shipped 2026-09-13:** tagged and released v0.1.0
  (https://github.com/pobrienDev/dartmetrics/releases/tag/v0.1.0) and
  made the repository public. Pre-publication audit: no secrets in any
  commit, fixtures on example.com, MIT license added.

## Next up

- Later (V1): refresh tokens + revocation, Elo, 301, leagues, trend
  charts, player comparison, bot darts animating in one at a time.

## Local setup

See the README "Local development" section — it is kept accurate and
was verified on a fresh environment. Requirements: Python 3.12+,
Node.js, Docker Desktop. Secrets live in an untracked `.env` created
from `.env.example` (generate your own SECRET_KEY).
