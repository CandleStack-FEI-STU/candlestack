#!/usr/bin/env bash
# Tests of candlestack-deploy, the forced command of the deploy keys. Runs the real script as
# sshd does (the key's scope from deploy_authorized_keys as its argument, the client's command
# in SSH_ORIGINAL_COMMAND, the GHCR token and the secrets on stdin) with fake docker and git
# on PATH that record their calls, and checks what each key may run and what reaches Docker.
# Needs bash and coreutils; touches nothing outside a temporary directory:
#   infra/vm/test-candlestack-deploy.sh
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Fake docker and git: every call is a line "<tool> <args>". docker also records the token
# of the login (its stdin) and where the login is kept, and for compose the first line of a
# compose file outside the checkout and the variables the deploy script gives it.
mkdir "$work/bin"
cat >"$work/bin/docker" <<'EOF'
#!/usr/bin/env bash
echo "docker $*" >>"$CALLS"
case $1 in
  login)
    echo "  stdin $(cat)" >>"$CALLS"
    echo "  config $DOCKER_CONFIG" >>"$CALLS"
    ;;
  compose)
    file=$(sed -n 's/.* -f \([^ ]*\) .*/\1/p' <<<"$*")
    if [[ $file != /opt/candlestack/* ]]; then
      echo "  file $(head -n 1 "$file")" >>"$CALLS"
    fi
    env | grep -E '^(ENV_NAME|APP_VERSION|BACKEND_IMAGE|FRONTEND_IMAGE|IMAGE|REDIS_[A-Z_]+|ALPACA_[A-Z_]+)=' |
      sort | sed 's/^/  env /' >>"$CALLS"
    ;;
esac
EOF
# The VM's checkout, where the release tag of "up prod" is fine unless FAKE_GIT names what is
# wrong: no-tag (not on origin), no-commit, not-on-main, no-compose (no infra/env/compose.yaml).
# not-shallow: the checkout is a full clone.
cat >"$work/bin/git" <<'EOF'
#!/usr/bin/env bash
echo "git $*" >>"$CALLS"
case "$*" in
  *" fetch --quiet --no-tags origin tag "*) [[ $FAKE_GIT != *no-tag* ]] ;;
  *" rev-parse --verify --quiet refs/tags/"*)
    [[ $FAKE_GIT != *no-commit* ]] && echo 5eed5eed5eed5eed5eed5eed5eed5eed5eed5eed
    ;;
  *" rev-parse --is-shallow-repository")
    if [[ $FAKE_GIT == *not-shallow* ]]; then echo false; else echo true; fi
    ;;
  *" merge-base --is-ancestor "*) [[ $FAKE_GIT != *not-on-main* ]] ;;
  *" show "*":infra/env/compose.yaml")
    [[ $FAKE_GIT != *no-compose* ]] && echo "# infra/env/compose.yaml of the release"
    ;;
esac
EOF
chmod +x "$work/bin/docker" "$work/bin/git"
CALLS=$work/calls
COMMIT=5eed5eed5eed5eed5eed5eed5eed5eed5eed5eed

# image <name>: a GHCR digest reference, as the workflows pass them.
image() {
  printf 'ghcr.io/candlestack-fei-stu/candlestack/%s@sha256:%s' "$1" \
    "$(sha256sum <<<"$1" | cut -c1-64)"
}
BACKEND=$(image backend)
FRONTEND=$(image frontend)
AGENT=$(image agent)
IMAGES="$BACKEND $FRONTEND"
TOKEN=ghs_TestToken0123456789
KEY_ID=PKTEST0123456789
SECRET='t3st/Secret+0123=~!'
SECRETS="ALPACA_KEY_ID=$KEY_ID
ALPACA_SECRET_KEY=$SECRET"

tests=0
failures=0

# run <scope> <command> [stdin]: runs the script with only the variables sshd sets (and
# FAKE_GIT); sets $status, $output, $temporary (the temporary directories the calls name: the
# Docker config of a login, the directory of a release's compose file) and $calls, with those
# directories as TMP. An empty stdin sends nothing at all.
run() {
  local dir
  : >"$CALLS"
  status=0
  output=$(if [[ -n ${3-} ]]; then printf '%s\n' "$3"; fi |
    env -i HOME="$work" PATH="$work/bin:$PATH" CALLS="$CALLS" FAKE_GIT="${FAKE_GIT-}" \
      SSH_ORIGINAL_COMMAND="$2" "$here/candlestack-deploy" "$1" 2>&1) || status=$?
  temporary=$(sed -n -e 's/^  config //p' -e 's|^docker compose .* -f \(/[^ ]*\)/compose\.yaml .*|\1|p' \
    "$CALLS" | grep -v '^/opt/candlestack' || true)
  calls=$(<"$CALLS")
  for dir in $temporary; do
    calls=${calls//"$dir"/TMP}
  done
}

failed() {
  failures=$((failures + 1))
  echo "FAIL  $1"
  shift
  printf '      %s\n' "$@"
}

# The script's output never shows the token or a secret value, whatever happened.
quiet() {
  local value
  for value in "$TOKEN" "$KEY_ID" "$SECRET" "${@:2}"; do
    if [[ $output == *"$value"* ]]; then
      failed "$1" "the output shows '$value': $output"
      return 1
    fi
  done
}

# allowed <name> <scope> <command> <stdin> <expected calls>
allowed() {
  tests=$((tests + 1))
  run "$2" "$3" "$4"
  quiet "$1" || return 0
  if [[ $status != 0 ]]; then
    failed "$1" "exit $status: $output"
  elif [[ $calls != "$5" ]]; then
    failed "$1" "calls differ (< expected, > actual):" "$(diff <(echo "$5") <(echo "$calls"))"
  else
    left_behind "$1" || echo "ok    $1"
  fi
}

# left_behind <name>: fails the test when a temporary directory of the script is still there.
left_behind() {
  local dir
  for dir in $temporary; do
    if [[ -e $dir ]]; then
      failed "$1" "the temporary directory $dir is left behind"
      return 0
    fi
  done
  return 1
}

# refused <name> <scope> <command> <stdin> <message> [value never shown]: fails with the
# message before any docker call, and before any git call unless $after_git lists the calls.
refused() {
  tests=$((tests + 1))
  run "$2" "$3" "$4"
  quiet "$1" "${@:6}" || return 0
  if [[ $status == 0 ]]; then
    failed "$1" "allowed, calls: $calls"
  elif [[ $calls != "${after_git-}" ]]; then
    failed "$1" "refused after other calls (< expected, > actual):" \
      "$(diff <(echo "${after_git-}") <(echo "$calls"))"
  elif [[ $output != "candlestack-deploy: $5" ]]; then
    failed "$1" "expected 'candlestack-deploy: $5', got: $output"
  else
    echo "ok    $1"
  fi
}

# release_git <tag> <count>: the first <count> git calls with which "up prod" checks its
# release tag and reads the tag's compose file.
release_git() {
  printf '%s\n' \
    "git -C /opt/candlestack fetch --quiet --no-tags origin tag $1" \
    "git -C /opt/candlestack rev-parse --verify --quiet refs/tags/$1^{commit}" \
    "git -C /opt/candlestack rev-parse --is-shallow-repository" \
    "git -C /opt/candlestack fetch --quiet --unshallow origin main" \
    "git -C /opt/candlestack merge-base --is-ancestor $COMMIT origin/main" \
    "git -C /opt/candlestack show $COMMIT:infra/env/compose.yaml" | head -n "$2"
}

# up_calls <env> <version> <maxmemory> <container limit> [with-secrets]: what "up" asks of
# Docker; prod with the compose file of its release tag.
up_calls() {
  echo "docker login ghcr.io --username deploy --password-stdin"
  echo "  stdin $TOKEN"
  echo "  config TMP"
  echo "docker pull --quiet $BACKEND"
  echo "docker pull --quiet $FRONTEND"
  if [[ $1 == prod ]]; then
    echo "docker compose -p prod -f TMP/compose.yaml up --detach --remove-orphans"
    echo "  file # infra/env/compose.yaml of the release"
  else
    echo "docker compose -p $1 -f /opt/candlestack/infra/env/compose.yaml up --detach --remove-orphans"
  fi
  if [[ -n ${5:-} ]]; then
    echo "  env ALPACA_KEY_ID=$KEY_ID"
    echo "  env ALPACA_SECRET_KEY=$SECRET"
  fi
  echo "  env APP_VERSION=$2"
  echo "  env BACKEND_IMAGE=$BACKEND"
  echo "  env ENV_NAME=$1"
  echo "  env FRONTEND_IMAGE=$FRONTEND"
  echo "  env REDIS_MAXMEMORY=$3"
  echo "  env REDIS_MEM_LIMIT=$4"
  echo "docker image prune --all --force"
}

echo "# The keys: every one is restricted to candlestack-deploy with one of the scopes"
tests=$((tests + 1))
forced='^restrict,command="/opt/candlestack/infra/vm/candlestack-deploy \([a-z]*\)" ssh-ed25519 .*'
scopes=$(sed -n "s|$forced|\1|p" "$here/deploy_authorized_keys" | sort | tr '\n' ' ')
keys=$(grep -c '^[^#]' "$here/deploy_authorized_keys")
if [[ $scopes == "preview prod stage " && $keys == 3 ]]; then
  echo "ok    deploy_authorized_keys: prod, stage and preview, each forced"
else
  failed "deploy_authorized_keys" "expected 3 forced keys prod, stage, preview; got $keys: $scopes"
fi

echo "# What each key may run"
allowed "prod: up prod, with the compose file of the release" prod "up prod v0.2.0 $IMAGES" \
  "$TOKEN
$SECRETS" "$(release_git v0.2.0 6)
$(up_calls prod v0.2.0 256mb 288m with-secrets)"
FAKE_GIT=not-shallow allowed "prod: up prod, a release candidate in a full clone" prod \
  "up prod v0.3.0-rc.1 $IMAGES" "$TOKEN
$SECRETS" "$(release_git v0.3.0-rc.1 6 | sed 's/ --unshallow//')
$(up_calls prod v0.3.0-rc.1 256mb 288m with-secrets)"
allowed "stage: up stage" stage "up stage main-0123abc $IMAGES" "$TOKEN
$SECRETS" "$(up_calls stage main-0123abc 128mb 160m with-secrets)"
allowed "stage: up stage without secrets" stage "up stage main-0123abc $IMAGES" "$TOKEN" \
  "$(up_calls stage main-0123abc 128mb 160m)"
allowed "preview: up pr-42" preview "up pr-42 pr-42-0123abc $IMAGES" "$TOKEN
$SECRETS" "$(up_calls pr-42 pr-42-0123abc 64mb 96m with-secrets)"
allowed "preview: down pr-42" preview "down pr-42" "" \
  "docker compose -p pr-42 -f /opt/candlestack/infra/env/compose.yaml down --remove-orphans
  env APP_VERSION=none
  env BACKEND_IMAGE=none
  env ENV_NAME=pr-42
  env FRONTEND_IMAGE=none
  env REDIS_MAXMEMORY=64mb
  env REDIS_MEM_LIMIT=96m
docker image prune --all --force"
allowed "stage: edge" stage "edge" "" \
  "git -C /opt/candlestack fetch --quiet --depth 1 origin main
git -C /opt/candlestack reset --quiet --hard FETCH_HEAD
docker compose -f /opt/candlestack/infra/edge/compose.yaml up --detach
docker compose -f /opt/candlestack/infra/edge/compose.yaml exec -T caddy caddy reload --config /etc/caddy/Caddyfile"
allowed "stage: agent" stage "agent $AGENT" "$TOKEN" \
  "docker login ghcr.io --username deploy --password-stdin
  stdin $TOKEN
  config TMP
docker pull --quiet $AGENT
docker compose -p agent -f /opt/candlestack/infra/agent/compose.yaml up --detach --remove-orphans
  env IMAGE=$AGENT"

echo "# What each key may not run"
refused "preview: up prod" preview "up prod v0.2.0 $IMAGES" "$TOKEN" \
  "the preview key may not deploy 'prod'"
refused "preview: up stage" preview "up stage main-0123abc $IMAGES" "$TOKEN" \
  "the preview key may not deploy 'stage'"
refused "preview: edge" preview "edge" "" "only the stage key updates the edge"
refused "preview: agent" preview "agent $AGENT" "$TOKEN" \
  "only the stage key deploys the server agent"
refused "preview: down stage" preview "down stage" "" "the preview key may not remove 'stage'"
refused "preview: down prod" preview "down prod" "" "the preview key may not remove 'prod'"
refused "stage: up prod" stage "up prod v0.2.0 $IMAGES" "$TOKEN" \
  "the stage key may not deploy 'prod'"
refused "stage: up pr-42" stage "up pr-42 pr-42-0123abc $IMAGES" "$TOKEN" \
  "the stage key may not deploy 'pr-42'"
refused "stage: down stage" stage "down stage" "" "only the preview key removes environments"
refused "prod: up stage" prod "up stage main-0123abc $IMAGES" "$TOKEN" \
  "the prod key may not deploy 'stage'"
refused "prod: up pr-42" prod "up pr-42 pr-42-0123abc $IMAGES" "$TOKEN" \
  "the prod key may not deploy 'pr-42'"
refused "prod: edge" prod "edge" "" "only the stage key updates the edge"
refused "prod: agent" prod "agent $AGENT" "$TOKEN" "only the stage key deploys the server agent"
refused "prod: down prod" prod "down prod" "" "only the preview key removes environments"
refused "unknown scope" admin "up prod v0.2.0 $IMAGES" "$TOKEN" \
  "the admin key may not deploy 'prod'"
refused "unknown command" stage "sh -c id" "" "unknown command: 'sh -c id'"
refused "no command (a shell)" stage "" "" "unknown command: ''"

echo "# prod: only a release tag on main's history, with the tag's own compose file"
for version in main-0123abc v0.2 0.2.0 v0.2.0.1 v0.2.0-; do
  refused "prod: version $version" prod "up prod $version $IMAGES" "$TOKEN" \
    "prod version must be a release tag (vX.Y.Z): '$version'"
done
FAKE_GIT=no-tag after_git=$(release_git v0.2.0 1) refused "prod: a tag not on origin" prod \
  "up prod v0.2.0 $IMAGES" "$TOKEN" "release tag 'v0.2.0' not found on origin"
FAKE_GIT=no-commit after_git=$(release_git v0.2.0 2) refused "prod: a tag of no commit" prod \
  "up prod v0.2.0 $IMAGES" "$TOKEN" "release tag 'v0.2.0' does not point to a commit"
FAKE_GIT=not-on-main after_git=$(release_git v0.2.0 5) refused "prod: a tag off main" prod \
  "up prod v0.2.0 $IMAGES" "$TOKEN" "release tag 'v0.2.0' is not on main's history"
FAKE_GIT=no-compose after_git=$(release_git v0.2.0 6) refused "prod: a tag without the file" \
  prod "up prod v0.2.0 $IMAGES" "$TOKEN" "release tag 'v0.2.0' has no infra/env/compose.yaml"

echo "# Malformed arguments"
for env in pr- pr-1234567 pr-4x2 PR-42 pr-42/ ../prod; do
  refused "preview: up $env" preview "up $env v1 $IMAGES" "$TOKEN" \
    "the preview key may not deploy '$env'"
done
long=$(printf 'v%.0s' {1..65})
# shellcheck disable=SC2016 # a command substitution the script must not run
for version in "$long" 'v1;id' 'v1$(id)' "v1'" 'main/0123' 'v1*'; do
  refused "version '${version:0:12}'" stage "up stage $version $IMAGES" "$TOKEN" \
    "bad version: '$version'"
done
refused "no images" stage "up stage v1" "$TOKEN" \
  "image must be a GHCR digest reference: ''"
for bad in \
  "ghcr.io/candlestack-fei-stu/candlestack/backend:latest" \
  "ghcr.io/candlestack-fei-stu/candlestack/backend@sha256:0123abcd" \
  "${BACKEND^^}" \
  "docker.io/library/redis@${BACKEND#*@}" \
  "ghcr.io/other-org/candlestack/backend@${BACKEND#*@}" \
  "ghcr.io/candlestack-fei-stu/candlestack/../backend@${BACKEND#*@}" \
  "registry.example/$BACKEND" \
  "$BACKEND;id"; do
  refused "image ${bad:0:60}" stage "up stage v1 $bad $FRONTEND" "$TOKEN" \
    "image must be a GHCR digest reference: '$bad'"
  refused "frontend ${bad:0:57}" stage "up stage v1 $BACKEND $bad" "$TOKEN" \
    "image must be a GHCR digest reference: '$bad'"
done
refused "agent image" stage "agent ${AGENT%@*}:latest" "$TOKEN" \
  "image must be a GHCR digest reference: '${AGENT%@*}:latest'"

echo "# stdin: the token, then only the Alpaca keys with safe values"
refused "up without a token" stage "up stage v1 $IMAGES" "" "expected a GHCR token on stdin"
refused "agent without a token" stage "agent $AGENT" "" "expected a GHCR token on stdin"
refused "another variable" stage "up stage v1 $IMAGES" "$TOKEN
LD_PRELOAD=/tmp/x.so" "only ALPACA_KEY_ID and ALPACA_SECRET_KEY may follow the token on stdin" \
  /tmp/x.so
refused "PATH" stage "up stage v1 $IMAGES" "$TOKEN
PATH=/tmp" "only ALPACA_KEY_ID and ALPACA_SECRET_KEY may follow the token on stdin"
refused "a line without =" stage "up stage v1 $IMAGES" "$TOKEN
$KEY_ID" "expected KEY=VALUE lines after the token on stdin"
for value in 'with space' 'quote"d' "quote'd" 'back`tick' 'back\slash' $'tab\there' \
  "$(printf 'x%.0s' {1..257})" $'caf\xc3\xa9'; do
  refused "secret value ${value:0:12}" stage "up stage v1 $IMAGES" "$TOKEN
ALPACA_SECRET_KEY=$value" \
    "ALPACA_SECRET_KEY must be at most 256 printable characters without spaces or quotes" \
    "$value"
done
secret=$SECRET
SECRET=$(printf '~%.0s' {1..256})
allowed "secret value of 256 characters, blank lines" stage "up stage v1 $IMAGES" "$TOKEN

ALPACA_KEY_ID=$KEY_ID
ALPACA_SECRET_KEY=$SECRET
" "$(up_calls stage v1 128mb 160m with-secrets)"
SECRET=$secret

echo
if ((failures)); then
  echo "$failures of $tests tests failed"
  exit 1
fi
echo "all $tests tests passed"
