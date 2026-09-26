#!/usr/bin/env bash
# Smoke test of a deployed environment, run by the deploy workflows after the health check:
#   .github/scripts/smoke.sh https://stage.candlestack.tech
# stage and previews are behind Cloudflare Access: set CF_ACCESS_CLIENT_ID and
# CF_ACCESS_CLIENT_SECRET to send the service token. prod is checked without it.
#
# Every check is a function check_<name> listed in CHECKS. It calls get, then fails with a
# message that says what was expected; what it prints on success is shown after "ok". All
# checks run; the script fails if any failed. To add one, write the function and append its
# name to CHECKS. The data checks go through the deployed API to the real sources: keep them
# few, candle and instrument requests count against CLIENT_RATE_LIMIT and every Alpaca call
# against the environment's Alpaca budget.
# shellcheck disable=SC2329 # the checks are called by name from the loop at the end
set -euo pipefail

CHECKS=(health openapi docs frontend sources search instruments crypto_candles stock_candles timings)

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

# get <path>: GET base-url + path. Sets $status, $type (the media type), $body, $seconds (the
# total time curl measured) and $app_ms (the app's own time from its Server-Timing header).
get() {
  local meta
  meta=$(curl "${curl_opts[@]}" --output "$work/body" --dump-header "$work/headers" \
    --write-out '%{http_code} %{time_total} %{content_type}' "$base$1") ||
    fail "GET $1: request failed"
  status=${meta%% *}
  meta=${meta#* }
  seconds=${meta%% *}
  type=${meta#* }
  type=${type%%;*}
  body=$(<"$work/body")
  app_ms=$(sed -n 's/^server-timing: *app;dur=\([0-9.]*\).*/\1/Ip' "$work/headers")
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

check_sources() {
  get /api/health/sources
  expect 200 application/json
  jq -e '.sources.binance.status == "ok" and .sources.alpaca.status == "ok"' <<<"$body" >/dev/null ||
    fail "a source is not reachable: $body"
}

# The first search of a new environment loads both catalogs from the sources.
check_search() {
  local pair q id
  for pair in btc=crypto:BTCUSDT apple=stock:AAPL; do
    q=${pair%%=*}
    id=${pair#*=}
    get "/api/v1/data/instruments?q=$q"
    expect 200 application/json
    jq -e --arg id "$id" 'any(.items[]; .id == $id)' <<<"$body" >/dev/null ||
      fail "q=$q does not find $id: ${body:0:300}"
  done
}

check_instruments() {
  local pair id source
  for pair in crypto:BTCUSDT=binance stock:AAPL=alpaca; do
    id=${pair%%=*}
    source=${pair#*=}
    get "/api/v1/data/instruments/$id"
    expect 200 application/json
    jq -e --arg id "$id" --arg source "$source" \
      '.id == $id and .source == $source and (.available_from | numbers) and (.timeframes | length) == 6' \
      <<<"$body" >/dev/null || fail "unexpected detail of $id: ${body:0:300}"
  done
}

# candles <instrument> <timeframe> <start> <end> <count>: expects exactly count candles.
candles() {
  get "/api/v1/data/candles?instrument=$1&timeframe=$2&start=$3&end=$4"
  expect 200 application/json
  jq -e --argjson n "$5" '.meta.count == $n and (.t | length) == $n' <<<"$body" >/dev/null ||
    fail "expected $5 candles of $1 $2 from $3 to $4: ${body:0:300}"
}

check_crypto_candles() {
  candles crypto:BTCUSDT 1h 2024-06-03 2024-06-04 24
}

# One regular session: 09:30, 10:30, ..., 15:30 New York, the last candle is 30 minutes.
check_stock_candles() {
  candles stock:AAPL 1h 2024-06-03 2024-06-04 7
}

# One year of 1h candles of a random year, so most likely not cached yet, then the same request
# again from the cache. Prints both times; the targets are 3 s cold and 300 ms cached.
check_timings() {
  local year=$((2018 + RANDOM % 8)) path first
  path="/api/v1/data/candles?instrument=crypto:BTCUSDT&timeframe=1h&start=$year-01-01&end=$((year + 1))-01-01"
  get "$path"
  expect 200 application/json
  first="$seconds s (app ${app_ms:-?} ms)"
  get "$path"
  expect 200 application/json
  echo "BTCUSDT 1h of $year, $(jq .meta.count <<<"$body") candles: first $first," \
    "repeated $seconds s (app ${app_ms:-?} ms)"
}

failed=0
for check in "${CHECKS[@]}"; do
  # Each check runs in a subshell, so fail ends only that check.
  if message=$("check_$check" 2>&1); then
    echo "ok    $check${message:+: $message}"
  else
    message=${message//$'\n'/ }
    echo "FAIL  $check: $message"
    [[ -z ${GITHUB_ACTIONS:-} ]] || echo "::error title=Smoke test $check::$message"
    failed=1
  fi
done
exit "$failed"
