# infra

Everything needed to run CandleStack on a single VM: one edge proxy in front of the
prod, stage and pull-request preview environments.

```
Internet -> Cloudflare (TLS) -> Tunnel -> cloudflared on the VM -> edge Caddy -> environment
```

The VM has no open inbound ports. `app`, `stage`, `ops` and `*` under `candlestack.tech`
are proxied CNAMEs to the tunnel, so moving to another server does not touch DNS: boot a
new VM with the same tunnel credentials and turn the old one off.

## Environments

| Environment | URL | Deployed when | Approval |
| --- | --- | --- | --- |
| prod | https://app.candlestack.tech | a `v*` tag is pushed on a commit of `main` | tech lead (GitHub environment `production`) |
| stage | https://stage.candlestack.tech | every push to `main` | none |
| preview | `https://pr-<N>-preview.candlestack.tech` | a pull request has the `preview` label | none |

stage, previews and https://ops.candlestack.tech (the team status page) are behind Cloudflare
Access: members of the `CandleStack-FEI-STU` GitHub organization sign in with GitHub. prod is
public. Any new subdomain is team-only by default (Access application `*.candlestack.tech`).

Each commit of `main` is built once. A release does not rebuild: it deploys the exact image
(same digest) that stage already runs for the tagged commit. Removing the `preview` label or
closing the pull request removes its environment. Pull requests from forks never deploy.

To release: `git tag v0.1.0 <commit on main> && git push origin v0.1.0`, then approve the
deployment in the Actions tab.

## How a deployment reaches the VM

GitHub Actions connects over SSH to `ssh.candlestack.tech` through the tunnel. That hostname
is a Cloudflare Access application that only lets in the `github-actions-deploy` service token.
Behind it, the `deploy` user has one key per environment, and each key is forced to run
`vm/candlestack-deploy` for its own scope only (for example, the preview key cannot touch prod).

| Secret or variable | Where | What |
| --- | --- | --- |
| `DEPLOY_SSH_KEY` | environments `production`, `staging`, `preview` | private deploy key of that scope |
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
| `env/compose.yaml` | One environment (prod, stage or `pr-<N>`) |
| `ops/` | Status page: collector and page in one Python process, SQLite history, read-only Docker proxy |
| `placeholder/` | Placeholder app shown until the real application exists |

## Create the VM on AWS

Requires the AWS CLI logged in (`aws login --profile candlestack`) and the tunnel
credentials file from `cloudflared tunnel create` (never commit it).

```sh
infra/vm/aws-create.sh ~/.cloudflared/<tunnel-id>.json main
```

Shell on the VM: `aws ssm start-session --profile candlestack --region eu-north-1 --target <instance-id>`
(needs the AWS Session Manager plugin), or EC2 console > the instance > Connect > Session Manager.
After a new VM, update the `DEPLOY_KNOWN_HOSTS` variable with its SSH host key.
