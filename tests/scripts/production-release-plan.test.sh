#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
planner="$project_root/scripts/production-release-plan.sh"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/flash-trips-release-plan-test.XXXXXX")"
trap 'rm -rf "$test_root"' EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_plan() {
  local event_name="$1"
  local expected="$2"
  local output

  output="$(cd "$test_root/repo" && "$planner" "$event_name" HEAD)"
  grep -qxF "deploy=$expected" <<<"$output" ||
    fail "expected deploy=$expected for $event_name, got: $output"
}

commit_file() {
  local path="$1"

  mkdir -p "$test_root/repo/$(dirname "$path")"
  printf 'changed\n' >>"$test_root/repo/$path"
  git -C "$test_root/repo" add "$path"
  git -C "$test_root/repo" commit -qm "Change $path"
}

bash -n "$planner"

mkdir -p "$test_root/repo"
git -C "$test_root/repo" init -q -b main
git -C "$test_root/repo" config user.name "Release Plan Test"
git -C "$test_root/repo" config user.email "release-plan@example.com"

commit_file "README.md"
assert_plan workflow_run true

commit_file "docs/operations.md"
assert_plan workflow_run false
assert_plan workflow_dispatch true

for deployable_path in \
  ".dockerignore" \
  "apps/api/Dockerfile" \
  "apps/web/app/page.tsx" \
  "contracts/ts/src/client.ts" \
  "package.json" \
  "pnpm-lock.yaml" \
  "pnpm-workspace.yaml" \
  "pyproject.toml" \
  "src/flash_trips/composition.py" \
  "uv.lock"; do
  commit_file "$deployable_path"
  assert_plan workflow_run true
done

commit_file ".github/workflows/quality.yml"
assert_plan workflow_run false

if (cd "$test_root/repo" && "$planner" pull_request HEAD >/dev/null 2>&1); then
  fail "planner accepted an unsupported event"
fi

printf 'production release plan tests passed\n'
