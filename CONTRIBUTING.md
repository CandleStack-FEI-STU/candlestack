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

## Checks

Both are required to merge:

| Check | What it runs |
| --- | --- |
| `no-ai-signs / No AI signs` | commit messages, authors and the pull request text |
| `ci` | the backend jobs `lint` (ruff, ty, import-linter), `unit`, `integration` (Redis) and `e2e` (the built image); `infra` (actionlint with shellcheck on the workflows, shellcheck on the deploy and smoke scripts, the edge Caddyfile and the tunnel ingress rules validated, the frontend and server agent images built) |

The backend jobs run only when `backend/`, `docs/openapi.json`, a `compose*.yaml` file or
`.github/workflows/ci.yml` changed, and `infra` only when `infra/`, `frontend/` or `.github/`
changed; `ci` passes when they are skipped.

## Preview environment

Add the `preview` label to a pull request to deploy it to
`https://pr-<N>-preview.candlestack.tech` (team only). Every push redeploys it; removing the
label or closing the pull request removes it.

## Backend

Needs [uv](https://docs.astral.sh/uv/) and Docker. From `backend/`:

```sh
uv sync                                               # virtualenv with the dev tools
uv run ruff check . && uv run ruff format --check .   # lint and format
uv run ty check                                       # types
uv run lint-imports                                   # module boundaries
uv run pytest                                         # unit tests
docker compose -f ../compose.dev.yaml up -d redis     # Redis on localhost:6379 ...
uv run pytest -m integration                          # ... for the integration tests
E2E_PORT=18000 uv run pytest -m e2e                   # builds and runs the image with compose
```

- The market data endpoints (instruments, candles, `/api/health/sources`) are specified in
  [docs/data.md](docs/data.md). With `compose.dev.yaml` running, try them in the API reference
  at http://localhost:8000/api/v1/docs (test request panel of each endpoint); crypto needs no
  keys, US stocks need `ALPACA_KEY_ID` and `ALPACA_SECRET_KEY` in `.env`.
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
