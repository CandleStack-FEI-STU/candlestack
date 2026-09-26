# infra

Everything needed to run CandleStack on a single VM: one edge proxy in front of the
prod, stage and pull-request preview environments.

```
Internet -> Cloudflare (TLS) -> Tunnel -> cloudflared on the VM -> edge Caddy -> environment
```

The VM has no open inbound ports. `app`, `stage` and `*` under `candlestack.tech`
are proxied CNAMEs to the tunnel, so moving to another server does not touch DNS: boot a
new VM with the same tunnel credentials and turn the old one off.

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

All containers run with a read-only root filesystem, no Linux capabilities and
`no-new-privileges`.

The backend, frontend and agent images are built for every deployment. The images that keep
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
(same digests) that stage already runs for the tagged commit. Removing the `preview` label or
closing the pull request removes its environment. Pull requests from forks never deploy.

To release: `git tag v0.2.0 <commit on main> && git push origin v0.2.0`, then approve the
deployment in the Actions tab. After every deployment the workflow waits for `/api/health` to
report the new commit or version, then runs `.github/scripts/smoke.sh` against the environment
(health, the OpenAPI schema, the API reference and the frontend page).

### Transition to the backend + frontend layout

Until the first release with this layout, prod still runs the old single `app` container
(`prod-app:8080`, the placeholder that also answered `/api/health`), while the edge Caddyfile
is deployed from `main` with every stage deployment. So for `app.candlestack.tech` the edge
lists `prod-backend`/`prod-frontend` first and `prod-app` as a fallback that is used only while
the new containers do not exist. The release replaces `app` with the three containers
(`--remove-orphans`). After that first release, remove the fallback from
`edge/caddy/Caddyfile` (`import env prod` like stage).

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
| `vm/deploy_authorized_keys` | Public deploy keys with their scopes |
| `cloudflared/config.yml` | Tunnel ingress: SSH for deployments, everything else to the edge |
| `edge/` | Caddy that routes each hostname to its environment |
| `env/compose.yaml` | One environment (prod, stage or `pr-<N>`): backend, frontend and Redis |
| `agent/` | Server agent for ops: host metrics, containers and preview health as JSON, read-only Docker proxy |

The images of an environment are built from `backend/` and `frontend/` at the repository root.

## Create the VM on AWS

Requires the AWS CLI logged in (`aws login --profile candlestack`) and the tunnel
credentials file from `cloudflared tunnel create` (never commit it).

```sh
infra/vm/aws-create.sh ~/.cloudflared/<tunnel-id>.json main
```

Shell on the VM: `aws ssm start-session --profile candlestack --region eu-north-1 --target <instance-id>`
(needs the AWS Session Manager plugin), or EC2 console > the instance > Connect > Session Manager.
After a new VM, update the `DEPLOY_KNOWN_HOSTS` variable with its SSH host key.
