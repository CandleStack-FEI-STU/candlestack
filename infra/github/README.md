# GitHub settings

A snapshot of how the organization CandleStack-FEI-STU and its five repositories are configured,
exported from the GitHub API on 2026-09-26. GitHub stays the source of truth: these files record
what was set up by hand, so it can be reviewed, compared after a change and set up again.

| File | What it holds |
| --- | --- |
| `organization.json` | Organization settings and member privileges, the Actions policy (allowed actions, token permissions, fork approval), the interaction limit, the `developers` team and its repository access |
| `project.json` | Project #1 "CandleStack": linked repositories, fields with their options, the board view, the built-in workflows (names and whether they are on) |
| `repositories/<repo>.json` | Per repository: merge and feature settings, security features, Actions settings, secret and variable names, environments (reviewers, branch and tag policies, secret names), labels, Pages |
| `rulesets/<repo>--<name>.json` | Each ruleset as GitHub returns it, ready for **Settings > Rules > Rulesets > Import a ruleset** or `POST /repos/{owner}/{repo}/rulesets` |

## Not in the snapshot

- **Secret values.** GitHub never returns them; only their names are listed.
- **Member and invitation lists.** They are personal data and change with the team.
- **Set up by hand only**, with no API to read or write them:
  - creating the organization and its plan, and the two-factor requirement;
  - the OAuth app "CandleStack team login" that Cloudflare Access uses for GitHub sign-in: its callback is `https://candlestack.cloudflareaccess.com/cdn-cgi/access/callback`, and its client secret lives only in Cloudflare;
  - the Pages domain verification click (the TXT record is in `../cloudflare/`);
  - the grouping and sorting of the project board view and the project workflows;
  - visibility and Actions access of the GHCR packages.

## Refresh

Export again after changing a setting and commit the difference. Each file is the matching `GET`
of the REST API (`/orgs/{org}`, `/orgs/{org}/actions/permissions/*`, `/repos/{owner}/{repo}`,
`/repos/{owner}/{repo}/rulesets/{id}`, `/repos/{owner}/{repo}/environments`, ...) or of the GraphQL
`projectV2` field, reduced to the settings and sorted by key. Timestamps, IDs of volatile objects
and URLs are left out, so a new export only differs where a setting changed.
