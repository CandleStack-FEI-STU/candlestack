# infra

Everything needed to run CandleStack on a single VM: one edge proxy in front of the
prod, stage and pull-request preview environments.

```
Internet -> Cloudflare (TLS) -> Tunnel -> cloudflared on the VM -> edge Caddy -> environment
```

The VM has no open inbound ports. `app`, `stage`, `ops` and `*` (for `pr-<N>`) under
`candlestack.tech` are proxied CNAMEs to the tunnel, so moving to another server does not
touch DNS: boot a new VM with the same tunnel credentials and turn the old one off.

| Path | What it is |
| --- | --- |
| `vm/cloud-init.yaml` | Provider-neutral bootstrap: Docker, swap, cloudflared, edge |
| `vm/aws-create.sh` | Creates the VM on AWS EC2 (t3.small, no inbound, SSM shell access) |
| `cloudflared/config.yml` | Tunnel ingress: every hostname goes to the edge Caddy |
| `edge/` | Caddy that routes requests by hostname |

## Create the VM on AWS

Requires the AWS CLI logged in (`aws login --profile candlestack`) and the tunnel
credentials file from `cloudflared tunnel create` (never commit it).

```sh
infra/vm/aws-create.sh ~/.cloudflared/<tunnel-id>.json main
```

Shell on the VM: `aws ssm start-session --profile candlestack --region eu-north-1 --target <instance-id>`
(needs the AWS Session Manager plugin).
