# Cloudflare settings

A snapshot of how `candlestack.tech` is configured in Cloudflare, exported from the Cloudflare API
on 2026-09-26. Cloudflare stays the source of truth: these files record what was set up in the
dashboard, so it can be reviewed, compared after a change and set up again.

| File | What it holds |
| --- | --- |
| `zone.json` | The zone (Free plan, nameservers), every zone setting (SSL Full (strict), minimum TLS 1.2, Always Use HTTPS, ...), DNSSEC with its DS record, Universal SSL, Worker routes |
| `dns-records.json` | Every DNS record: the GitHub Pages records (DNS only, which Pages needs to issue its certificate) and the proxied CNAMEs to the tunnel |
| `candlestack.tech.zone` | The same records as a BIND zone file |
| `access.json` | Zero Trust: the organization (`candlestack.cloudflareaccess.com`), the login methods, the reusable policies, the Access applications and the service tokens (names and expiry only) |
| `tunnel.json` | The tunnel `candlestack-vm`; its ingress rules are in `../cloudflared/config.yml` |
| `workers.json` | The ops Worker (cron, `workers.dev` off, custom domain) and its D1 database; the Worker itself is configured in the ops repository's `wrangler.jsonc` |

How the pieces fit: the tunnel CNAMEs send `app`, `stage`, `ssh` and every other name (`*`) to the
VM. Access decides who gets through: `app` is public (application `prod-public`), `ssh` accepts
only the deploy service token (`ssh-deploy`), and everything else (stage, previews, `vm`, `ops`)
needs a GitHub login from the organization or a service token (`team-only`). `ops` is served by
the Worker, not the tunnel.

## Not in the snapshot

- **Secrets.** Service token secrets, the GitHub login's client secret, the tunnel credentials
  and API tokens are shown once when created and never returned.
- **Set up by hand only:**
  - the Cloudflare account and the Zero Trust plan (needs a payment card, stays free);
  - the nameservers and the DNSSEC DS record at the registrar (get.tech);
  - the first API token;
  - Certificate Transparency monitoring (a dashboard toggle).
- **Not exported:** API tokens (the export token could not read them).

The `ops` record (`AAAA 100::`) belongs to the Worker's custom domain: Cloudflare creates and
removes it with the Worker, so it is never edited by hand.

## Refresh

Export again after changing a setting and commit the difference, with a short-lived read-only API
token (Zone, Zone Settings, DNS, SSL and Certificates, Workers Routes; Access apps, policies,
organizations and service tokens, Cloudflare Tunnel, Workers Scripts, D1, Account Settings).
Each file is the matching `GET` of the API v4 (`/zones/{zone}/settings`, `/zones/{zone}/dns_records`,
`/accounts/{account}/access/apps`, ...), reduced to the settings and sorted by key. Timestamps are
left out, so a new export only differs where a setting changed.
