# Sentry settings

A snapshot of how the Sentry organization `candlestack` (https://candlestack.sentry.io, EU data
region) is configured, exported from the Sentry API on 2026-09-26. Sentry stays the source of
truth: these files record what was set up by hand, so it can be reviewed, compared after a change
and set up again. What the backend sends and why: [docs/architecture.md](../../docs/architecture.md#observability).

| File | What it holds |
| --- | --- |
| `organization.json` | Data region, privacy (IP addresses not stored, data scrubbing required, extra sensitive fields, no public issue links), what members may do (no inviting, no new projects, no deleting events, no editing alerts), Seer (AI) automation: it proposes fixes in Sentry and never opens pull requests |
| `teams.json` | The one team, `candlestack` |
| `projects/backend.json` | Project `backend` (Python, FastAPI): privacy, inbound filters, Seer settings |
| `projects/backend--keys.json` | Its client key: name and state. The DSN is not recorded; it is the GitHub environment secret `SENTRY_DSN` of `production` and `staging` |
| `alerts.json` | Alerts: e-mail to the tech lead for a new, regressed or reappearing issue on prod (at most every 30 minutes) and for 50 events of one issue in an hour on prod; Sentry's default notice when Seer has a pull request ready |
| `monitors.json` | Monitors: the uptime check of `https://app.candlestack.tech/api/health` every minute (down after 3 failures, up after 1 success) and the default error and issue monitors the alerts hang on |
| `integrations.json` | GitHub: installed on the `candlestack` repository only, every sync and pull request comment off, and the code mapping that turns stack trace paths into links to the code |

## Not in the snapshot

- **The DSN and tokens.** The organization token of the deploy workflows (`org:ci`) is the
  GitHub environment secret `SENTRY_AUTH_TOKEN`.
- **Members and invitations.** They are personal data and change with the team. Alerts name the
  tech lead as "tech lead" instead of a user ID.
- **Personal notification settings**, which belong to each account (Settings > Account >
  Notifications). The tech lead's deploy e-mails are off, so a stage deploy sends none.
- **Set up by hand only**:
  - the organization, its plan (Sponsored Team through the GitHub Student Developer Pack until
    2027-09-26, then the free Developer plan unless renewed) and the EU region, which cannot
    change later;
  - approving the Sentry GitHub App on the organization CandleStack-FEI-STU (read and write
    access to `candlestack` only);
  - spike protection, on for `backend` (Settings > Spike Protection);
  - per-key rate limits, which need the Business plan: the backend limits itself to 100 error
    events an hour per process instead.

## Refresh

Export again after changing a setting and commit the difference. Each file is the matching `GET`
of the REST API, reduced to the settings and sorted by key, with IDs, timestamps, URLs and e-mail
addresses left out, so a new export only differs where a setting changed:

| File | Endpoint |
| --- | --- |
| `organization.json` | `https://de.sentry.io/api/0/organizations/candlestack/` |
| `teams.json` | `.../organizations/candlestack/teams/` |
| `projects/backend.json` | `.../projects/candlestack/backend/` and `.../projects/candlestack/backend/filters/` |
| `projects/backend--keys.json` | `.../projects/candlestack/backend/keys/` |
| `alerts.json` | `.../organizations/candlestack/workflows/` |
| `monitors.json` | `.../organizations/candlestack/detectors/` |
| `integrations.json` | `https://sentry.io/api/0/organizations/candlestack/integrations/?provider_key=github`, `.../repos/`, `.../code-mappings/` |

Organization data lives in the EU region (`de.sentry.io`); integrations are global
(`sentry.io`). A personal token with read access to projects, teams, releases, events,
organization, members and alerts reads all of them.
