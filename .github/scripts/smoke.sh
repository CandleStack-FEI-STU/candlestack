#!/usr/bin/env bash
# Smoke test of a deployed environment, run by the deploy workflows after the health check:
#   .github/scripts/smoke.sh https://stage.candlestack.tech
# stage and previews are behind Cloudflare Access: set CF_ACCESS_CLIENT_ID and
# CF_ACCESS_CLIENT_SECRET to send the service token. prod is checked without it.
#
# Every check is a function check_<name> listed in CHECKS. It calls get, then fails with a
# message that says what was expected. All checks run; the script fails if any failed.
# To add one, write the function and append its name to CHECKS.
# shellcheck disable=SC2329 # the checks are called by name from the loop at the end
set -euo pipefail

CHECKS=(health openapi docs frontend)

base=${1:?usage: smoke.sh <base-url>}
base=${base%/}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

curl_opts=(--silent --show-error --max-time 20 --retry 2)
if [[ -n ${CF_ACCESS_CLIENT_ID:-} ]]; then
  curl_opts+=(-H "CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID" -H "CF-Access-Client-Secret: ${CF_ACCESS_CLIENT_SECRET:?}")
fi

fail() {
  echo "$*" >&2
  exit 1
}

# get <path>: GET base-url + path. Sets $status, $type (the media type) and $body.
get() {
  local meta
  meta=$(curl "${curl_opts[@]}" --output "$work/body" --write-out '%{http_code} %{content_type}' "$base$1") ||
    fail "GET $1: request failed"
  status=${meta%% *}
  type=${meta#* }
  type=${type%%;*}
  body=$(<"$work/body")
}

# expect <status> <media type>
expect() {
  [[ $status == "$1" ]] || fail "expected HTTP $1, got $status: ${body:0:300}"
  [[ $type == "$2" ]] || fail "expected $2, got '$type'"
}

check_health() {
  get /api/health
  expect 200 application/json
  jq -e '.status == "ok"' <<<"$body" >/dev/null || fail "status is not ok: $body"
}

check_openapi() {
  get /api/v1/openapi.json
  expect 200 application/json
  jq -e '.openapi | strings' <<<"$body" >/dev/null || fail "not an OpenAPI document"
}

check_docs() {
  get /api/v1/docs
  expect 200 text/html
  grep -qi scalar "$work/body" || fail "the page does not load Scalar"
}

check_frontend() {
  get /
  expect 200 text/html
}

failed=0
for check in "${CHECKS[@]}"; do
  # Each check runs in a subshell, so fail ends only that check.
  if message=$("check_$check" 2>&1); then
    echo "ok    $check"
  else
    message=${message//$'\n'/ }
    echo "FAIL  $check: $message"
    [[ -z ${GITHUB_ACTIONS:-} ]] || echo "::error title=Smoke test $check::$message"
    failed=1
  fi
done
exit "$failed"
