# Contributing

## Branches and pull requests

- `main` is protected. Every change goes through a pull request and is squash-merged once it
  is reviewed and its checks are green.
- Branch from `main` and name the branch `<area>/<topic>`, e.g. `backend/candles`.
  Keep pull requests small and about one thing.
- The pull request title becomes the commit on `main`: imperative, sentence case, no trailing
  period, e.g. "Add the candles endpoint".
- No AI attribution in commits or pull requests: no co-author trailers of AI tools,
  "Generated with ..." lines or session links. The `no-ai-signs` check fails on them.

## Merging

What the ruleset of `main` enforces:

- one approving review; a new push dismisses earlier approvals;
- every review thread resolved;
- the required checks `no-ai-signs / No AI signs` and `ci` (below) green;
- no force pushes to `main` and no deleting it.

A pull request that changes a path listed in `.github/CODEOWNERS` (infrastructure, CI, the
toolchain, the dependency set) requests a review from @ArsenLabovich; the ruleset does not
require that review beyond the one approval. Squash merging is the team's convention, not a
rule of the repository.

## Checks

Both are required to merge:

| Check | What it runs |
| --- | --- |
| `no-ai-signs / No AI signs` | commit messages, authors and the pull request text |
| `ci` | the backend jobs `lint` (ruff, ty, import-linter), `unit`, `integration` (Redis) and `e2e` (the built image); `infra` (actionlint with shellcheck on the workflows, shellcheck on the deploy and smoke scripts, the edge Caddyfile and the tunnel ingress rules validated, the frontend and server agent images built) |

The backend jobs run only when `backend/`, `docs/openapi.json`, a `compose*.yaml` file in the
repository root (`compose.yaml`) or `.github/workflows/ci.yml` changed, and `infra` only when
`infra/`, `frontend/` or `.github/` changed; `ci` passes when they are skipped.

## Preview environment

Add the `preview` label to a pull request to deploy it to
`https://pr-<N>-preview.candlestack.tech` (team only). Every push redeploys it; removing the
label or closing the pull request removes it.

## Backend

Needs [uv](https://docs.astral.sh/uv/) and Docker. The uv release line is `required-version`
in `backend/pyproject.toml` (CI and the image use the same line), and uv refuses to run outside
it. Get a matching release with `uv self update <version>`, e.g. the lower bound of that range
(uv from the standalone installer; otherwise through the tool that installed it).

The commands are POSIX shell (macOS Terminal, Linux, Git Bash on Windows). In Windows
PowerShell 5.1, chain commands with `;` instead of `&&` and set a variable before the command:
`$env:E2E_PORT='18001'; uv run pytest -m e2e` (it stays set in that window). From `backend/`:

```sh
uv sync                                               # virtualenv with the dev tools
uv run ruff check . && uv run ruff format --check .   # lint and format
uv run ty check                                       # types
uv run lint-imports                                   # module boundaries
uv run pytest                                         # unit tests (-n auto: in parallel)
docker compose up -d redis                            # Redis of ../compose.yaml on 127.0.0.1:6379 ...
uv run pytest -m integration                          # ... Redis DB 15, which the tests flush; runs serially
uv run pytest -m e2e                                  # builds and runs the image with compose on 127.0.0.1:18000 (E2E_PORT to change)
```

- `REDIS_URL` points the integration tests at another Redis; they flush the database they
  get, so never give them one whose data you need.
- Coverage of the unit and integration tests (with Redis running):
  `uv run pytest --cov=candlestack --cov-branch -m "not e2e"`. The team's convention is at
  least 85% (branch coverage included); CI does not enforce it.
- The market data endpoints (instruments, candles, `/api/health/sources`) are specified in
  [docs/data.md](docs/data.md). With `compose.yaml` running (`docker compose up --build` in the
  repository root), try them in the API reference at http://localhost:8000/api/v1/docs (test
  request panel of each endpoint); crypto needs no keys, US stocks need `ALPACA_KEY_ID` and
  `ALPACA_SECRET_KEY` in `.env` (see the [README](README.md#alpaca-keys-for-us-stocks)).
- Tests mirror the modules: `tests/unit/<module>/` and `tests/integration/<module>/`; tests
  of the whole app (lifespan, API reference, OpenAPI snapshot) sit in `tests/unit/`.
- Unit tests fake the `DataService`; integration tests mock the sources with respx. The e2e
  stack replaces Binance and Alpaca with `tests/e2e/mock_sources.py`, which serves the
  recorded responses listed in `tests/fixtures/README.md` under the sources' paths, so no test
  needs the network or keys.
- The API contract is committed in `docs/openapi.json` and a unit test fails when it is stale.
  After changing the API, regenerate it (in a POSIX shell such as Git Bash) and commit it with
  the change: `uv run python -m candlestack.openapi > ../docs/openapi.json`.
- Modules import each other only through their package root
  (`from candlestack.core import ProblemError`), and `candlestack.core` imports no other module.
  `lint-imports` checks both.
- Add dependencies with `uv add <package>` (`--dev` for tools) and commit `uv.lock`.
- Settings are environment variables, documented in `.env.example`.
