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
- Using Claude Code is fine: `CLAUDE.md` gives it the project's rules and
  `.claude/settings.json` turns its commit and pull request attribution off. Keep personal
  settings in `.claude/settings.local.json` (ignored).
- Once per clone, install the git hooks: `uvx pre-commit install`. On every commit they fix
  ruff findings and formatting, trailing whitespace and missing final newlines, and stop
  merge conflict markers, files over 1 MB, private keys and AI attribution in the commit
  message (`.pre-commit-config.yaml`). A hook that fixed files stops the commit: review the
  changes, `git add` them and commit again. They take a second or two; CI still runs every
  check.

## Merging

What the ruleset of `main` enforces:

- one approving review; a new push dismisses earlier approvals;
- an approval from @ArsenLabovich when the pull request changes a path listed in
  `.github/CODEOWNERS` (infrastructure, CI, the toolchain, the dependency set, the shared
  editor and Claude Code settings);
- every review thread resolved;
- the required checks `no-ai-signs / No AI signs` and `ci` (below) green;
- no force pushes to `main` and no deleting it.

Squash merging is the team's convention, not a rule of the repository.

## Checks

Both are required to merge:

| Check | What it runs |
| --- | --- |
| `no-ai-signs / No AI signs` | commit messages, authors and the pull request text |
| `ci` | the backend jobs `lint` (ruff, ty, import-linter, the root `compose.yaml` validated and its dev image built), `unit`, `integration` (Redis) and `e2e` (the built image, then scanned by Trivy); `api` (breaking changes to the API, see below); `infra` (actionlint with shellcheck on the workflows, shellcheck on the deploy and smoke scripts, the deploy script's tests, the compose files of `infra/` validated, the server agent's ruff and tests, the edge Caddyfile and the tunnel ingress rules validated, the frontend and server agent images built and scanned by Trivy; see [infra/README.md](infra/README.md#tests)) |

The backend jobs run only when `backend/`, `docs/openapi.json`, a `compose*.yaml` file in the
repository root (`compose.yaml`) or `.github/workflows/ci.yml` changed, and `infra` only when
`infra/`, `frontend/`, `.github/` or `backend/uv.lock` (the agent is linted with the backend's
ruff) changed; `api` runs on pull requests that change `docs/openapi.json`. `ci` passes when
they are skipped.

The Trivy scans fail on a HIGH or CRITICAL vulnerability in an image that has a fix: usually
a newer base image or dependency fixes it. One that cannot be fixed yet goes to
`.trivyignore.yaml` with a date to look again, and only with the tech lead's approval.

## Preview environment

Add the `preview` label to a pull request to deploy its current commit to
`https://pr-<N>-preview.candlestack.tech` (team only). The server has room for one preview at a
time: when another pull request holds it, the label comes off again and a comment says until
when. A preview lives at most 6 hours (then the label comes off with a comment); a new commit,
removing the label or closing the pull request removes it sooner. A new commit removes the
label too: add it again to deploy that commit.

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
- The CI job `api` compares that file with the one on `main` (oasdiff) and lists every change
  in its summary. It fails on a change that breaks existing clients: a removed or renamed
  field, parameter or endpoint, a new required parameter, a narrower type, a new value in a
  response enum. Prefer a change that keeps them working (a new optional field or parameter, a
  new endpoint). A break meant on purpose is agreed on in the pull request: the job prints one
  line per change, and those lines go to `docs/api-breaking-changes.txt`.
- Modules import each other only through their package root
  (`from candlestack.core import ProblemError`), and `candlestack.core` imports no other module.
  `lint-imports` checks both.
- Add dependencies with `uv add <package>` (`--dev` for tools) and commit `uv.lock`.
- Settings are environment variables, documented in `.env.example`.

## Errors and logs

The errors, traces, profiles and logs of prod and stage go to Sentry (https://candlestack.sentry.io;
the tech lead grants access). What it records is in
[docs/architecture.md](docs/architecture.md#observability). In code:

- What the client should see is a `ProblemError` (4xx, or 502/503 when a source fails); what
  the service works around is `logger.warning`. Neither becomes a Sentry issue.
- What needs a developer is `logger.exception(...)` in the `except` block (or `logger.error`):
  it becomes a Sentry issue, as does any exception nobody catches.
- Never swallow an exception (`except Exception: pass`), and never put keys, tokens or personal
  data in a log message or its `extra`.
- Only `candlestack.core` imports `sentry_sdk`; `lint-imports` checks it.
- Without `SENTRY_DSN` (local runs, tests, previews) nothing is sent. To check that errors
  reach Sentry, open https://stage.candlestack.tech/api/debug/sentry-error (stage only): it
  fails on purpose, and the error shows up in Sentry under the environment `stage`.
