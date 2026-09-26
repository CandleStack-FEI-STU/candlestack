# infra

Everything needed to run CandleStack on a single VM: one edge proxy in front of the
prod, stage and pull-request preview environments.

```
Internet -> Cloudflare (TLS) -> Tunnel -> cloudflared on the VM -> edge Caddy -> environment
```

The VM has no open inbound ports. `app`, `stage`, `ssh` and `*` under `candlestack.tech`
are proxied CNAMEs to the tunnel, so moving to another server does not touch DNS; see
[Replace the VM](#replace-the-vm) for the swap itself.

## Environments

| Environment | URL | Deployed when | Approval |
| --- | --- | --- | --- |
| prod | https://app.candlestack.tech | a `v*` tag is pushed on a commit of `main` | tech lead (GitHub environment `production`) |
| stage | https://stage.candlestack.tech | every push to `main` | none |
| preview | `https://pr-<N>-preview.candlestack.tech` | a pull request has the `preview` label | none |

Every environment is one compose project (`env/compose.yaml`) with three containers. The edge
Caddy sends `/api/*` of the environment's hostname to its backend and everything else to its
frontend, and compresses the responses (zstd or gzip) on the way to Cloudflare.

| Container | Image | Reached as | Memory limit |
| --- | --- | --- | --- |
| `backend` | `ghcr.io/candlestack-fei-stu/candlestack/backend` (built from `backend/`) | `<env>-backend:8000` on the `edge` network | `320m` |
| `frontend` | `ghcr.io/candlestack-fei-stu/candlestack/frontend` (built from `frontend/`, the placeholder page) | `<env>-frontend:8080` on the `edge` network | `32m` |
| `redis` | `redis:8-alpine`, pinned by digest | `redis:6379` on the environment's own network only | see below |

Redis is a cache for the backend: no persistence, least recently used keys are evicted at
`maxmemory`, and losing it only costs refetch time.

| Environment | Redis `maxmemory` | Container limit |
| --- | --- | --- |
| prod | `256mb` | `288m` |
| stage | `128mb` | `160m` |
| `pr-<N>` | `64mb` | `96m` |

All containers of an environment run with a read-only root filesystem, no Linux capabilities
and `no-new-privileges`.

Every push to `main` builds the backend, frontend and agent images once, a preview deployment
builds the backend and frontend images, and a release builds nothing. The images that keep
running on the VM (Redis, the edge Caddy, the agent's Docker socket proxy) are pinned in the
compose files, and Dependabot proposes their updates; `edge` recreates the edge Caddy when its
version changes.

stage, previews and https://ops.candlestack.tech (the team status page) are behind Cloudflare
Access: members of the `CandleStack-FEI-STU` GitHub organization sign in with GitHub. prod is
public. Any new subdomain is team-only by default (Access application `*.candlestack.tech`).

## Monitoring

https://ops.candlestack.tech is a Cloudflare Worker in its own repository,
[CandleStack-FEI-STU/ops](https://github.com/CandleStack-FEI-STU/ops), so it keeps working and
records the outage when this VM is down. Every minute it checks prod and stage from outside and
reads `https://vm.candlestack.tech/api/snapshot`, served by the server agent (`agent/`): host
CPU, memory and disk, containers and the health of every preview. The agent keeps no history
and holds no secrets; its JSON is a contract with the ops repository (schema 1).

Each commit of `main` is built once. A release does not rebuild: it deploys the exact images
(same digests) that stage already runs for the tagged commit, started with that commit's own
`infra/env/compose.yaml` rather than whatever main's checkout has by then (`edge` keeps
resetting it to origin/main on every stage deploy). Removing the `preview` label or closing the
pull request removes its environment. Pull requests from forks never deploy.

To release: `git tag v0.2.0 <commit on main> && git push origin v0.2.0`, then approve the
deployment in the Actions tab. After every deployment the workflow waits for `/api/health` to
report the new commit or version, then runs `.github/scripts/smoke.sh` against the environment:

| Check | What it expects |
| --- | --- |
| `health` | `/api/health` answers 200 with `status` `ok` |
| `openapi`, `docs` | the OpenAPI schema, and the API reference page that loads Scalar |
| `frontend` | the page at `/` |
| `access` | stage and previews only: `/api/health` without the Access token gets Access (a redirect to its login, or 401/403), not the app |
| `sources` | `/api/health/sources`: Binance and Alpaca reachable |
| `search` | `btc` finds `crypto:BTCUSDT` and `apple` finds `stock:AAPL` first, with both markets loaded |
| `instruments` | the detail of both, with `available_from` |
| `crypto_candles`, `stock_candles` | the 24 BTCUSDT and the 7 AAPL 1h candles of 2024-06-03 |
| `timings` | a year of BTCUSDT 1h candles twice; prints both times and warns (without failing) when the app takes over 3 s the first time or over 300 ms from the cache |

The stage deployment also reloads the edge Caddy, which serves prod too, so right after that it
checks that https://app.candlestack.tech/api/health reports `ok` and the page at `/` answers
200 (without the Access token: prod is public).

## How a deployment reaches the VM

GitHub Actions connects over SSH to `ssh.candlestack.tech` through the tunnel. That hostname
is a Cloudflare Access application that only lets in the `github-actions-deploy` service token.
Behind it, the `deploy` user has one key per environment, and each key is forced to run
`vm/candlestack-deploy` for its own scope only (for example, the preview key cannot touch prod).

```
up <env> <version> <backend image@digest> <frontend image@digest>
```

`up` reads its stdin: the first line is a GHCR token used once for the pull, then `KEY=VALUE`
lines with the backend's secrets. Only `ALPACA_KEY_ID` and `ALPACA_SECRET_KEY` are accepted
(at most 256 printable characters, no spaces or quotes). The script hands them to
`docker compose` in its environment only: it writes no file and prints nothing (Docker itself
keeps them in the container's configuration, as with any container environment variable). The
workflows send them with the `env-secrets` input of `.github/actions/deploy`. After `up` and
`down` the script removes the images no container uses any more (every backend build adds a
source layer of about 150 KB, and a dependency layer of about 250 MB when `uv.lock` changes).
The other commands are `down pr-<N>` (preview key), `edge` and `agent <image@digest>` (stage
key); the header of `vm/candlestack-deploy` lists which key may run what.

| Secret or variable | Where | What |
| --- | --- | --- |
| `DEPLOY_SSH_KEY` | environments `production`, `staging`, `preview` | private deploy key of that scope |
| `ALPACA_KEY_ID`, `ALPACA_SECRET_KEY` | environments `production`, `staging`, `preview` | Alpaca paper account keys for the backend (US stocks); `staging` and `preview` share the stage account, `production` has its own |
| `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET` | repository secrets | Access service token |
| `DEPLOY_KNOWN_HOSTS` | repository variable | SSH host key of the VM |

## Files

| Path | What it is |
| --- | --- |
| `vm/cloud-init.yaml` | Provider-neutral bootstrap: Docker, swap, cloudflared, edge, deploy user |
| `vm/aws-create.sh` | Creates the VM on AWS EC2 (t3.small, no inbound, SSM shell access) |
| `vm/candlestack-deploy` | The only command the deploy keys can run |
| `vm/test-candlestack-deploy.sh` | Tests of `candlestack-deploy` (see [Tests](#tests)) |
| `vm/deploy_authorized_keys` | Public deploy keys with their scopes |
| `cloudflared/config.yml` | Tunnel ingress: SSH for deployments, everything else to the edge |
| `edge/` | Caddy that routes each hostname to its environment |
| `env/compose.yaml` | One environment (prod, stage or `pr-<N>`): backend, frontend and Redis |
| `agent/` | Server agent for ops: host metrics, containers and preview health as JSON, read-only Docker proxy |
| `github/` | Snapshot of the organization's GitHub settings: rulesets, environments, Actions policy, security, project |
| `cloudflare/` | Snapshot of the Cloudflare settings: zone, DNS, Access, tunnel, Workers |

The images of an environment are built from `backend/` and `frontend/` at the repository root.

## Tests

The CI `infra` job runs these, besides actionlint, shellcheck and validating the compose files,
the Caddyfiles and the tunnel ingress rules. Locally, from the repository root:

```sh
infra/vm/test-candlestack-deploy.sh    # bash with GNU tools (Linux, WSL), or in a container:
docker run --rm -v "$PWD:/repo:ro" -w /repo ubuntu:24.04 infra/vm/test-candlestack-deploy.sh
docker run --rm -v "$PWD/infra/agent:/agent:ro" -w /agent python:3.13-alpine python -m unittest -v
cd backend && uv run ruff check ../infra/agent && uv run ruff format --check ../infra/agent
```

- `vm/test-candlestack-deploy.sh` runs the real `vm/candlestack-deploy` as sshd runs it for each
  key (the scope from `vm/deploy_authorized_keys`, the command in `SSH_ORIGINAL_COMMAND`, the
  token and secrets on stdin) with fake `docker` and `git` that record their calls. It checks
  which key may run what, that malformed images, versions, preview numbers and secrets are
  refused before anything runs, that prod takes only a release tag on main's history and
  starts with that tag's compose file, that no token or secret is printed, and the Docker
  commands of every allowed command. It touches nothing outside a temporary directory.
- `agent/test_agent.py` (standard library `unittest`, like the agent) pins the schema-1
  snapshot that ops reads, the order of its containers and the HTTP answers (`starting`, the
  snapshot, `stale`), with a stub Docker API and fixture files for `/proc`. The agent is linted
  with the backend's ruff release and `agent/ruff.toml`.

## Create the VM on AWS

Requires the AWS CLI logged in (`aws login --profile candlestack`) and the tunnel
credentials file from `cloudflared tunnel create` (never commit it).

```sh
infra/vm/aws-create.sh ~/.cloudflared/<tunnel-id>.json main
```

Shell on the VM: `aws ssm start-session --profile candlestack --region eu-north-1 --target <instance-id>`
(needs the AWS Session Manager plugin), or EC2 console > the instance > Connect > Session Manager.

## Replace the VM

Both VMs would run cloudflared on the same tunnel, so until the old one stops, Cloudflare
balances `ssh.candlestack.tech` and all web traffic between them: deploys can reach the wrong
machine or fail the host-key check. cloud-init only starts the edge Caddy, so every environment
needs a fresh deploy afterwards.

1. Boot the new VM (above), with the same tunnel credentials file as the old one.
2. Before deploying anything to the new VM, stop the old VM's tunnel (SSM shell:
   `sudo systemctl stop cloudflared`) or shut the old VM down.
3. Read the new VM's SSH host key (SSM shell: `cat /etc/ssh/ssh_host_ed25519_key.pub`) and
   replace the `DEPLOY_KNOWN_HOSTS` repository variable (Settings > Secrets and variables >
   Actions > Variables) with `ssh.candlestack.tech` followed by the key's type and base64
   fields, in the format the variable already holds.
4. Redeploy every environment, since nothing but the edge Caddy is running yet:
   - stage: `stage.yml` has no manual trigger, so re-run its latest workflow run, or push to
     `main`; this also deploys the server agent.
   - prod: re-run the latest release workflow run and approve the deployment again.
   - previews: push to the pull request, or remove and re-add the `preview` label.
5. Two things no deploy repeats, on this VM or the next one, because cloud-init only did them
   once at boot: after a change to `infra/cloudflared/config.yml`, restart cloudflared on the
   VM (SSM: `sudo systemctl restart cloudflared`); after a change to
   `infra/vm/deploy_authorized_keys`, reinstall it for the deploy user by hand (SSM:
   `sudo install -o deploy -g deploy -m 600 /opt/candlestack/infra/vm/deploy_authorized_keys
   /home/deploy/.ssh/authorized_keys`). cloudflared itself is also never upgraded after boot.
6. Once the new VM is confirmed healthy, terminate the old one.
