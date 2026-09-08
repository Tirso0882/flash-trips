#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
deployer="$project_root/scripts/production-deploy.sh"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/flash-trips-production-deploy-test.XXXXXX")"
trap 'rm -rf "$test_root"' EXIT

registry="flashtripsprodx7trifyn.azurecr.io"
released_api="$registry/flash-trips-api@sha256:released"
released_web="$registry/flash-trips-web@sha256:released"
candidate_api="$registry/flash-trips-api@sha256:candidate"
candidate_web="$registry/flash-trips-web@sha256:candidate"
placeholder="mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

# Fakes record every az invocation and let each case script curl's outcome.
install_fakes() {
  local bin="$test_root/bin"

  rm -rf "$bin" "$test_root/az.log" "$test_root/curl.log"
  mkdir -p "$bin"

  cat >"$bin/az" <<'FAKE_AZ'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$AZ_LOG"
if [[ "$*" == *"containerapp show"* ]]; then
  if [[ "$*" == *"$FAKE_API_APP"* ]]; then
    printf '%s\n' "$FAKE_LIVE_API_IMAGE"
  else
    printf '%s\n' "$FAKE_LIVE_WEB_IMAGE"
  fi
fi
FAKE_AZ

  # Fails for the first FAKE_CURL_FAILURES calls, then serves a status body.
  cat >"$bin/curl" <<'FAKE_CURL'
#!/usr/bin/env bash
set -euo pipefail
printf 'call\n' >>"$CURL_LOG"
calls="$(wc -l <"$CURL_LOG" | tr -d ' ')"
if ((calls <= FAKE_CURL_FAILURES)); then
  exit 22
fi
printf '{"status":"ok"}\n'
FAKE_CURL

  chmod +x "$bin/az" "$bin/curl"
}

run_deploy() {
  install_fakes
  set +e
  env \
    PATH="$test_root/bin:$PATH" \
    AZ_LOG="$test_root/az.log" \
    CURL_LOG="$test_root/curl.log" \
    FAKE_API_APP="flash-trips-prod-api" \
    FAKE_LIVE_API_IMAGE="$1" \
    FAKE_LIVE_WEB_IMAGE="$2" \
    FAKE_CURL_FAILURES="$3" \
    RESOURCE_GROUP="flash-trips-prod-rg" \
    API_APP_NAME="flash-trips-prod-api" \
    API_FQDN="api.internal.example.invalid" \
    API_IMAGE="$candidate_api" \
    WEB_APP_NAME="flash-trips-prod-web" \
    WEB_IMAGE="$candidate_web" \
    PRODUCTION_URL="https://web.example.invalid" \
    SMOKE_ATTEMPTS=2 \
    SMOKE_DELAY_SECONDS=0 \
    GITHUB_STEP_SUMMARY="$test_root/summary.md" \
    bash "$deployer" >"$test_root/stdout.txt" 2>"$test_root/stderr.txt"
  deploy_status=$?
  set -e
}

assert_output_contains() {
  grep -qF "$1" "$test_root/stdout.txt" ||
    fail "expected output to contain '$1', got: $(cat "$test_root/stdout.txt")"
}

assert_deployed_images() {
  local expected="$1"
  local actual
  actual="$(grep -c -- "--image $expected" "$test_root/az.log" || true)"
  test "$actual" -ge 1 || fail "expected an update to $expected, az log: $(cat "$test_root/az.log")"
}

assert_no_deploy_of() {
  if grep -qF -- "--image $1" "$test_root/az.log"; then
    fail "expected no update to $1, az log: $(cat "$test_root/az.log")"
  fi
}

bash -n "$deployer"

# A healthy release deploys the candidate and never touches the previous digest.
run_deploy "$released_api" "$released_web" 0
test "$deploy_status" -eq 0 || fail "expected success for a passing smoke test"
assert_deployed_images "$candidate_api"
assert_deployed_images "$candidate_web"
assert_no_deploy_of "$released_api"
assert_output_contains "smoke test passed"

# A failing release rolls back to the previously released digests and still fails.
run_deploy "$released_api" "$released_web" 2
test "$deploy_status" -eq 1 || fail "expected failure for a failing smoke test"
assert_deployed_images "$candidate_api"
assert_deployed_images "$released_api"
assert_deployed_images "$released_web"
assert_output_contains "restoring"
assert_output_contains "production restored to the previous release"

# The Bicep placeholder is not a usable rollback target.
run_deploy "$placeholder" "$placeholder" 4
test "$deploy_status" -eq 1 || fail "expected failure when rollback is impossible"
assert_no_deploy_of "$placeholder"
assert_output_contains "no previously released digest to restore"
assert_output_contains "production is serving the failed release"

# Re-deploying the digest that is already live has nothing to roll back to.
run_deploy "$candidate_api" "$candidate_web" 4
test "$deploy_status" -eq 1 || fail "expected failure when the live digest is the candidate"
assert_output_contains "no previously released digest to restore"

# Missing configuration fails before any Azure call.
install_fakes
if env PATH="$test_root/bin:$PATH" AZ_LOG="$test_root/az.log" \
  RESOURCE_GROUP="flash-trips-prod-rg" bash "$deployer" >/dev/null 2>&1; then
  fail "deployer accepted incomplete configuration"
fi
test ! -s "$test_root/az.log" || fail "deployer called az with incomplete configuration"

printf 'production deploy tests passed\n'
