#!/usr/bin/env bash
# Whether a pull request wants a preview of a commit now, by its current state on GitHub (not
# by what an event or a run of the pull request's workflow said):
#   .github/scripts/preview-wanted.sh <pull request number> <commit>
# Prints nothing when it does: the pull request is open, into main, from a branch of this
# repository (not a fork), has the "preview" label and <commit> is still its head. Otherwise
# prints why not. Needs GH_TOKEN (pull-requests: read) and GH_REPO.
set -euo pipefail

pr=${1:?usage: preview-wanted.sh <pull request number> <commit>}
commit=${2:?usage: preview-wanted.sh <pull request number> <commit>}
[[ $pr =~ ^[0-9]{1,6}$ ]] || {
  echo "::error::bad pull request number: '$pr'" >&2
  exit 1
}
[[ $commit =~ ^[0-9a-f]{40}$ ]] || {
  echo "::error::bad commit: '$commit'" >&2
  exit 1
}

gh api "repos/$GH_REPO/pulls/$pr" | jq -r --arg repo "$GH_REPO" --arg commit "$commit" '
  if .state != "open" then "#\(.number) is closed"
  elif .head.repo.full_name != $repo then "#\(.number) comes from a fork"
  elif .base.ref != "main" then "#\(.number) is not into main"
  elif ([.labels[].name] | index("preview")) == null then "#\(.number) has no preview label"
  elif .head.sha != $commit then "the head of #\(.number) is no longer \($commit)"
  else empty end'
