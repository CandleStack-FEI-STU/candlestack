# Architecture

The CandleStack backend is one Python service: a FastAPI application that serves the HTTP API
under `/api`. In this milestone it has three modules: `core` (configuration, logging, errors,
Redis, Postgres and HTTP clients, CSRF protection, health, Sentry), `data` (market data:
instrument catalog and candles from Binance and Alpaca, see [data.md](data.md)) and `accounts`
(users, GitHub and Google sign-in, sessions, the beta list). Postgres stores what users create,
accounts and sessions so far; market data is not stored: the sources are the truth and Redis is
a cache that can be lost at any time. The backtest is being built next to them
(`signals`, `engine`, `metrics` and the `candlestack-bt` command in `cli`, see
[Modules](#modules) and the contract in [engine.md](engine.md)); it runs from the command line,
not in the service.

## Runtime

prod and stage run the same containers on one VM. Deployment, hosts, secrets and backups are
described in [infra/README.md](../infra/README.md).

```mermaid
flowchart LR
    browser["Browser or API client"] -->|HTTPS| cf["Cloudflare<br/>TLS, Access (stage)"]
    cf --> tunnel["Cloudflare Tunnel"]
    subgraph vm["VM (no inbound ports)"]
        tunnel --> cloudflared["cloudflared"]
        cloudflared --> caddy["edge Caddy<br/>routes by hostname"]
        subgraph envbox["one environment: prod or stage"]
            caddy -->|"/api/*"| backend["backend<br/>FastAPI on granian :8000"]
            caddy -->|"everything else"| frontend["frontend<br/>static page, Caddy :8080"]
            backend --> redis[("redis<br/>cache only")]
            backend --> postgres[("postgres<br/>users, sessions")]
        end
    end
    backend -->|HTTPS| binance["Binance<br/>REST + data.binance.vision"]
    backend -->|HTTPS| alpaca["Alpaca<br/>trading API + market data"]
    backend -->|"HTTPS, sign-in"| oauth["GitHub and Google<br/>OAuth"]
    backend -.->|"HTTPS, prod and stage"| sentry["Sentry (EU)<br/>errors, traces, profiles, logs"]
```

| Container | Image | Notes |
| --- | --- | --- |
| `backend` | `ghcr.io/candlestack-fei-stu/candlestack/backend` | calls Binance and Alpaca; gets the environment's Alpaca keys at deploy time |
| `frontend` | `ghcr.io/candlestack-fei-stu/candlestack/frontend` | the web app, static files served by Caddy |
| `redis` | `redis:8-alpine` | private network of the environment, no persistence, `allkeys-lru` |
| `postgres` | `postgres:18-alpine` | private network of the environment, data in a volume; migrated by a one-shot `migrate` container (the backend image, `alembic upgrade head`) before the backend starts; prod and stage dump it every night (`backup`) |

## HTTP surface

| Path | What |
| --- | --- |
| `GET /api/health` | liveness + Redis + Postgres; used by deploys and the ops page; not versioned |
| `GET /api/health/sources` | reachability of Binance and Alpaca (cached 60 s) |
| `GET /api/v1/data/...` | instruments and candles, see [data.md](data.md) |
| `GET /api/v1/auth/{provider}/start?next=<path>` | sign-in with `github` or `google`: redirects to the provider |
| `GET /api/v1/auth/{provider}/callback` | where the provider returns; sets the session cookie and redirects to `next` (default `/dashboard`), or to `/signin?error=denied` (not on the beta list) or `/signin?error=failed`; not in the API reference |
| `GET /api/v1/auth/denied` | the account this browser was just turned away with (email, provider), for the sign-in page |
| `POST /api/v1/auth/sign-out` | ends this browser's session |
| `POST /api/v1/auth/dev` | signs in as a fixed dev user; only `APP_ENV` `local` and `test`, not in the API reference |
| `GET /api/v1/me` | the signed-in user |
| `GET /api/v1/docs` | API reference (Scalar); public on prod |
| `GET /api/v1/openapi.json` | OpenAPI schema; snapshot committed as [openapi.json](openapi.json) |

- Responses are JSON. Pydantic response models serialize themselves; the candles body, up to
  50000 candles, is written with orjson straight from the Polars columns (its model only
  documents it). Errors are RFC 9457 `application/problem+json` with
  `type` `https://candlestack.tech/problems/<slug>`, `title`, `status`, a `detail` that says
  which limit fired and what to do, and extension fields. Request validation errors use slug
  `validation` (422), the framework's own errors `not-found` (404) and `method-not-allowed`
  (405), and an unhandled exception `internal-error` (500), whose `detail` reveals nothing and
  asks to report the response's `X-Request-ID`. The slugs of the data module are listed in
  [data.md](data.md#errors). The accounts module adds `not-signed-in` (401: no session, or it
  ended) and `cross-origin-request` (403: a change that does not come from the app's own
  pages), and uses `not-found` (404) and `rate-limited` (429) too. Each `type` URI opens a page on the website that says what the
  problem means and what the client should do.
- Every response carries `X-Request-ID` and `Server-Timing: app;dur=<ms>` (the app's time
  until the response started), so response times can be measured from outside.
- Logs: one JSON object per line on stdout (`ts`, `level`, `logger`, `msg`); the access line
  adds `method`, `path`, `status`, `duration_ms`, `request_id` (the `CF-Ray` header, else a
  random hex).

## Modules

A module is a subpackage of `candlestack` under `backend/src/candlestack/`.

| Module | Status | Responsibility |
| --- | --- | --- |
| `core` | now | settings, logging, problem errors, Redis, Postgres and HTTP clients, CSRF protection, health endpoint |
| `data` | now | instrument catalog, candles, sessions, cache, source adapters, rate limits |
| `accounts` | now | users, GitHub and Google sign-in, sessions, the beta list; `CurrentUserDep` for the routes of the signed-in user |
| `preprocessing` | later | Renko, Kagi, time windows, normalization, segmentation |
| `ml` | later | upload `.keras` models, validate input/output shapes, run inference; worker only (below) |
| `signals` | started | turn predictions into signals: align them with the candles, thresholds, long only; later smoothing, holding period, sizing, risk limits |
| `engine` | started | the backtest loop: candles and signals in, trades and an equity series out; `ENGINE_VERSION` names its rules ([engine.md](engine.md)) |
| `metrics` | started | unified metrics and charts of one run |
| `cli` | started | the `candlestack-bt` command: backtests from files on the command line |
| `experiments` | later | assemble `preprocessing`, `ml`, `signals`, `engine` and `metrics` into runs, store and compare them |
| `admin` | later | team-only administration (roles, audit) under `/admin` |

Folders for later modules are created when their work starts, not before; `started` marks
the ones whose folder exists while their code is being written.

## Import rules

- Dependencies point one way: `experiments` -> `preprocessing` -> `data` -> `core`, and
  `accounts` -> `core`. `core` imports no other module.
- The backtest modules `signals`, `engine` and `metrics` stand alone: they import no other
  module of the project, not each other, and no server library (`fastapi`, `starlette`,
  `scalar_fastapi`, `granian`, `redis`, `httpx`, `sentry_sdk`, `pydantic_settings`,
  `sqlalchemy`, `asyncpg`, `alembic`, `authlib`). They are
  plain functions on Polars frames, put together only by the code that runs them: `cli` now,
  `experiments` later.
- No module imports `cli`: it is the entry point of the `candlestack-bt` command
  (`[project.scripts]` in `backend/pyproject.toml`).
- `ml` is worker-only, so the API process never loads TensorFlow: only the worker's
  composition root (a future `candlestack/worker.py`) imports it and wires it into the
  experiment runs, and the API enqueues worker tasks by name instead of importing them.
  TensorFlow and Keras go into a `worker` dependency group (or extra) that the API image does
  not install. An import-linter `forbidden` contract will enforce this when the worker lands:
  source `candlestack.main`, forbidden `tensorflow` and `keras`,
  `include_external_packages = true`. The name is `ml`, not `models`, which `data/models.py`
  and later ORM models use.
- Another module is imported only through its package root:
  `from candlestack.data import DataService`, never `from candlestack.data.sources import ...`.
  The package root's `__init__.py` is the module's public API.
- `candlestack.main` (builds the app) and `candlestack.openapi` (schema snapshot) wire the
  modules together and may import any module root except `ml` and `cli`.
- Checked by import-linter (`uv run lint-imports`, contracts in `backend/pyproject.toml`) in
  the CI `lint` job.

## Stack

| Concern | Choice | Why |
| --- | --- | --- |
| Language | Python 3.13 | the team's language and the ML ecosystem the later modules need |
| Packaging | uv, committed `uv.lock` | fast, reproducible installs (`uv sync --locked`) in dev, CI and images |
| Web | FastAPI, Pydantic v2, pydantic-settings | typed validation and an OpenAPI schema from the same code; typed env config |
| Server | granian | fast Rust ASGI server, one command for prod and `--reload` in dev |
| JSON | orjson | serializes large numeric arrays (up to 50000 candles) quickly |
| Data frames | Polars | fast columnar processing, Arrow-native; cache blobs are Arrow IPC + zstd |
| Cache | Redis with `redis[hiredis]` asyncio | one store for cache blobs, locks and rate-limit counters |
| Database | Postgres 18, SQLAlchemy 2 (asyncio) on asyncpg, Alembic migrations in `backend/migrations` | relational data with constraints; typed models; versioned schema changes that run before each deploy's backend starts |
| Sign-in | Authlib (OAuth 2.0 messages, PKCE) over the app's httpx client | a maintained implementation of the protocol; the requests stay on the client the tests mock with respx |
| HTTP client | httpx (async), timeouts always set | async calls to the sources; mocked in tests with respx |
| API docs | scalar-fastapi at `/api/v1/docs` | readable reference with request examples; Swagger and ReDoc disabled |
| Time zones | stdlib `zoneinfo` + `tzdata` | DST-correct New York sessions even in slim images without system tz data |
| Lint and format | ruff | one fast tool for linting, import sorting and formatting |
| Types | ty, exact version pinned | fast type checker; pinned so a new release cannot turn CI red by itself |
| Boundaries | import-linter | keeps the module rules above enforced, not just written down |
| Tests | pytest, pytest-xdist, anyio plugin, respx | parallel runs, async tests, no real network in unit and integration tests |
| Errors, traces, profiles, logs | Sentry (`sentry-sdk`), EU region | the team sees what fails or is slow with the code, commit and request behind it; free for a year with the GitHub Student Developer Pack |

## Configuration

Environment variables, read by pydantic-settings without a prefix. All are documented in
[`.env.example`](../.env.example).

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_ENV` | `local` | `local`, `test`, `stage`, `prod` |
| `APP_VERSION` | `dev` | deployed version (`main-<sha>`, `v0.2.0`) |
| `APP_COMMIT` | `unknown` | commit sha, baked into the image at build time |
| `LOG_LEVEL` | `INFO` | |
| `PUBLIC_URL` | prod `https://app.candlestack.tech`, stage `https://stage.candlestack.tech`, local `http://localhost:5173`, test `http://testserver` | where the app is reached: OAuth callbacks, cookies (`Secure` and `__Host-` over https), the same-origin check |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | |
| `DATABASE_URL` | `postgresql+asyncpg://candlestack:candlestack@127.0.0.1:5432/candlestack` | Postgres (whitespace stripped); the pool holds at most 10 connections |
| `OAUTH_GITHUB_CLIENT_ID`, `OAUTH_GITHUB_CLIENT_SECRET` | empty | GitHub OAuth app; without both, GitHub sign-in is off |
| `OAUTH_GOOGLE_CLIENT_ID`, `OAUTH_GOOGLE_CLIENT_SECRET` | empty | Google OAuth client; without both, Google sign-in is off |
| `BETA_ALLOWLIST` | empty | comma-separated emails that may sign in with GitHub or Google, any case; empty lets nobody in |
| `ALPACA_KEY_ID`, `ALPACA_SECRET_KEY` | empty | Alpaca paper account keys (whitespace stripped) |
| `ALPACA_API_URL` | `https://paper-api.alpaca.markets` | assets, calendar, clock |
| `ALPACA_DATA_URL` | `https://data.alpaca.markets` | bars |
| `BINANCE_API_URL` | `https://api.binance.com` | REST |
| `BINANCE_DATA_URL` | `https://data.binance.vision` | public archives |
| `LOGO_DEV_KEY` | empty | logo.dev publishable key for the instrument icons (whitespace stripped); empty: every icon is the fallback |
| `LOGO_DEV_URL` | `https://img.logo.dev` | logo images |
| `CANDLES_MAX` | `50000` | max candles in one candle response |
| `CLIENT_RATE_LIMIT` | `60` | candle and instrument-detail requests per minute per client IP (IPv6: per /64); `0` disables |
| `ALPACA_RATE_LIMIT` | prod `150`, stage `100`, `pr-*` `30`, else `60` | our Alpaca request budget per minute |
| `BINANCE_WEIGHT_LIMIT` | `1000` | our Binance REST weight budget per minute per environment |
| `LOGO_DEV_RATE_LIMIT` | prod `50`, stage `20`, `pr-*` `5`, else `20` | our logo.dev request budget per minute |
| `STATS_REFRESH` | prod and stage `true`, else `false` | refresh the instruments' 24 h stats and daily mini charts in the background ([data.md](data.md#stats)); without it the list has no stats or mini charts and sorts by symbol |
| `SENTRY_DSN` | empty | Sentry project for errors, traces, profiles and logs; empty sends nothing (set for prod and stage only) |
| `SENTRY_TRACES_SAMPLE_RATE` | prod `0.2`, else `1.0` | share of requests traced in Sentry |

## Observability

| Question | Where |
| --- | --- |
| Are prod and stage up? How loaded is the server? What was deployed or restarted? | https://ops.candlestack.tech, checks from outside every minute |
| What failed, where in the code, since which release? What is slow? | Sentry, organization `candlestack`, project `backend`: https://candlestack.sentry.io |
| Is prod down right now? | Sentry's uptime monitor calls `/api/health` of prod every minute and e-mails the tech lead after 3 failures |

What the backend sends to Sentry (only prod and stage have a DSN), set up in
`core/observability.py`:

- **Errors**: an unhandled exception (the client gets a 500 with `X-Request-ID`) and every
  record logged at ERROR or above. A problem response (4xx, or 502/503 when a source fails) and
  a warning are not errors: they are the service working as designed.
- **Traces**: 20% of prod requests and every stage request, never `/api/health`. Calls to
  Binance, Alpaca and Redis are spans of them.
- **Profiles**: while a traced request runs, the profiler samples the stacks about 100 times a
  second, so Sentry shows which functions take the CPU time (a trace's profile, or Explore >
  Profiles). The plan includes 750 profile hours a month, no pay-as-you-go.
- **Logs**: records from INFO up, the access line of each request included (except health
  checks), each with its `request_id`.
- Every event carries `environment` (`prod`, `stage`), `release` (`APP_VERSION`) and
  `request_id`: the `X-Request-ID` a user reports finds the error.
- Nothing personal or secret: no IP addresses, cookies, request bodies, Cloudflare Access
  logins or emails; the Alpaca keys, the DSN, the database URL and the OAuth client secrets,
  codes, verifiers, states and tokens are filtered, in the query of a request too; Redis keys
  hold the sign-in's state and the denial's id only as SHA-256; only our own frames keep their
  local variables, without the ASGI scope. The logs of a sign-in name the provider and why it
  failed, never the account.
- At most 100 error events an hour per process, so an error in a loop cannot use up the
  month's quota (50,000 errors, no pay-as-you-go).

Alerts are e-mails to the tech lead only: a new, regressed or reappearing issue on prod (at
most every 30 minutes), 50 events of one issue in an hour on prod, and prod down. Stage sends
none. Every deploy records its release in Sentry (`.github/scripts/sentry-release.sh`), which
links an issue to its suspect commit.

`GET /api/debug/sentry-error`, on stage only and not in the API reference, fails on purpose
to check that an error reaches Sentry. The Sentry settings are recorded in
[`infra/sentry/`](../infra/sentry/README.md).

## Not in this milestone

- Celery (job queue and worker)
- TensorFlow / Keras
- admin, roles, audit log
- user data upload (no CSV import)
- live data (streaming, websockets)
- Kubernetes, Terraform
- a coverage gate in CI

## Decisions

| Decision | Why |
| --- | --- |
| Modular monolith, one package, boundaries checked by import-linter | one image and one deploy for a small team; the boundaries still hold |
| Market data is not stored; Redis as a disposable cache (no persistence, `allkeys-lru`) | market data comes from the sources on demand; losing Redis costs only refetch time |
| Postgres for what users create, one database per environment, nightly dumps on prod and stage | accounts and later models and backtests must survive restarts and deploys; one small instance per environment keeps stage away from prod's data |
| Sign-in with GitHub or Google only, no passwords | no password storage, reset or verification flows to build and secure; both providers vouch for a verified email, which also links a user's two providers into one account |
| A beta list (`BETA_ALLOWLIST`) decides who signs in, closed when empty | the app is for the team and invited testers while it is built; a turned-away account is named on the sign-in page (from Redis, for 10 minutes, never in a URL) and gets no account |
| Server-side sessions: a random token in an HttpOnly, SameSite=Lax cookie (`__Host-` over https), only its SHA-256 in Postgres, 30 days sliding | a session can be ended at once (sign-out, later admin), a database leak does not leak sessions, and no script can read the cookie |
| Changes on behalf of the user require the app's own origin (`core.require_same_origin`), the OAuth round trip a state bound to the browser (Redis and a cookie) and PKCE | every host under candlestack.tech is the same site to the browser, so SameSite cookies alone do not stop a page on another of them; the state stops login CSRF; PKCE stops a stolen code |
| A dev sign-in for `APP_ENV` `local` and `test` only, fixed in code, not a setting | signed-in pages can be built and tested without OAuth keys; no setting can turn it on in stage or prod |
| One source per market, never mixed in one series: Binance spot for crypto, Alpaca SIP for US stocks (15 minutes delayed) | consistent data; both are free |
| Full history fetched lazily on request, catalog cached 24 h and refreshed in the background | no ingestion pipeline and no scheduler to run |
| The instruments' 24 h stats refreshed by one asyncio task in the API process (started in the app's lifespan, every 5-10 minutes, a Redis lock per market), only in prod and stage | a list sorted by volume needs every instrument's numbers before anyone asks; a task in the process needs no worker, queue or cron container, and the lock keeps a second process from fetching them again |
| Stocks use the regular session only (09:30-16:00 New York, calendar from Alpaca) | comparable candles; extended-hours data is thin |
| Same timeframes for both markets: `1m 5m 15m 30m 1h 4h 1d` | experiments can switch markets without changing the pipeline |
| UTC epoch seconds everywhere, candle label = open time, `start` inclusive, `end` exclusive | no time zone ambiguity at the API; New York time exists only in session math |
| Gaps are reported, never filled | filled candles would be invented prices |
| Explicit limits instead of silent truncation (50000 candles, per-IP and per-source rate limits) | the client always gets exactly what it asked for or an error saying what to change |
| A fingerprint over every candle set | later experiments can detect that a source changed its data |
| Prod API and docs public (per-IP rate limit); stage behind Cloudflare Access | anyone can try the released API without an account; unreleased builds stay team-only |
| granian instead of uvicorn, ty instead of mypy, Polars instead of pandas | faster tools with the same role |
| Coverage and TDD are team conventions, not CI gates | CI stays fast; test quality is checked in review |
| Security headers at the edge, the Content-Security-Policy in report-only mode first; Trivy on every image in CI and weekly on what runs | the headers protect every page without app code; the policy's reports show what it would break before it blocks anything; the scans catch known vulnerabilities before a merge and after a release |
| Sentry for errors, traces, profiles and logs of prod and stage; ops for uptime and the server | ops keeps working when the VM is down; Sentry shows failures with their code, commit and request, and local runs stay out of its quota |
