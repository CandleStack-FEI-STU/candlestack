#!/usr/bin/env bash
# Records in Sentry that an environment now runs a release of the backend, built from
# $GITHUB_SHA. Run by the deploy workflows after the smoke test:
#   .github/scripts/sentry-release.sh main-<sha> stage
#   .github/scripts/sentry-release.sh v0.3.0 prod
# The release name is the backend's APP_VERSION, the one its events carry. Through the GitHub
# integration Sentry reads the commits since the previous release: issues show their suspect
# commit, and "Fixes BACKEND-12" in a commit resolves that issue once its release is out.
# Needs SENTRY_AUTH_TOKEN, an organization token (scope org:ci).
set -euo pipefail

version=${1:?version} environment=${2:?environment}
: "${SENTRY_AUTH_TOKEN:?}" "${GITHUB_SHA:?}"
api=https://de.sentry.io/api/0/organizations/candlestack

# post <path> <json>: fails on an HTTP error, prints nothing on success.
post() {
  curl -fsS --max-time 30 -o /dev/null -X POST \
    -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" -H 'Content-Type: application/json' \
    --data "$2" "$api/$1"
}

post releases/ "$(jq -n --arg version "$version" --arg commit "$GITHUB_SHA" '{
  version: $version,
  projects: ["backend"],
  refs: [{repository: "CandleStack-FEI-STU/candlestack", commit: $commit}]
}')"
post "releases/$(jq -rn --arg version "$version" '$version | @uri')/deploys/" \
  "$(jq -n --arg environment "$environment" '{environment: $environment}')"
echo "Sentry: release $version runs on $environment"
