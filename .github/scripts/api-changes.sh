#!/usr/bin/env bash
# Compares the API contract of a pull request with its base branch's: every change goes to the
# job summary, and a change that breaks clients fails unless docs/api-breaking-changes.txt
# accepts it. Needs oasdiff and jq; run from the repository root.
#   api-changes.sh <base openapi.json> <revision openapi.json>
set -euo pipefail

base=$1
revision=$2
accepted=docs/api-breaking-changes.txt
# The snapshots have no external references, so never fetch one.
flags=(--allow-external-refs=false)

if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then
  oasdiff changelog "$base" "$revision" "${flags[@]}" --format markdown >>"$GITHUB_STEP_SUMMARY"
fi

# One line per breaking change (level 3 is an error), as the accepted list takes it:
# "<METHOD> <path> <change>".
breaking=$(
  oasdiff breaking "$base" "$revision" "${flags[@]}" --err-ignore "$accepted" --format json |
    jq -r '.[]? | select(.level == 3) | "\(.operation) \(.path) \(.text)"'
)
if [[ -z $breaking ]]; then
  echo "No breaking API changes."
  exit 0
fi

while IFS= read -r change; do
  echo "::error title=Breaking API change::$change"
done <<<"$breaking"
cat <<MESSAGE

These changes break clients written against the current API (the frontend, anyone using the
public API). Prefer a change that does not: a new optional field or parameter, a new endpoint.
If the break is intended, add these lines to $accepted and say why in the pull request:

$breaking
MESSAGE
exit 1
