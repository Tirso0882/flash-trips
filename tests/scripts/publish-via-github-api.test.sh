#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
publisher="$project_root/scripts/publish-via-github-api.sh"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/flash-trips-publisher-test.XXXXXX")"
trap 'rm -rf "$test_root"' EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local file="$1"
  local expected="$2"
  rg -F --quiet "$expected" "$file" || fail "expected '$expected' in $file"
}

new_repo() {
  local name="$1"
  local branch="$2"
  local repo="$test_root/$name"
  mkdir -p "$repo"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.name "Publisher Test"
  git -C "$repo" config user.email "publisher@example.com"
  printf 'base\n' >"$repo/tracked.txt"
  git -C "$repo" add tracked.txt
  git -C "$repo" commit -qm "Base"
  if [[ "$branch" != "main" ]]; then
    git -C "$repo" switch -q -c "$branch"
    printf 'tracked\n' >"$repo/tracked.txt"
    git -C "$repo" add tracked.txt
    git -C "$repo" commit -qm "Test publication"
  fi
  printf '%s\n' "$repo"
}

make_fake_gh() {
  local fake="$test_root/fake-gh"
  cat >"$fake" <<'FAKE_GH'
#!/usr/bin/env bash
set -euo pipefail

printf '%q ' "$@" >>"$FAKE_GH_STATE_DIR/calls.log"
printf '\n' >>"$FAKE_GH_STATE_DIR/calls.log"

if [[ "$1" == "auth" && "$2" == "status" ]]; then
  exit 0
fi

if [[ "$1" == "repo" && "$2" == "view" ]]; then
  if [[ " $* " == *" --repo "* ]]; then
    printf 'unknown flag: --repo\n' >&2
    exit 1
  fi
  if printf '%s\n' "$@" | rg -q 'defaultBranchRef'; then
    printf 'main\n'
  else
    printf 'Tirso0882/flash-trips\n'
  fi
  exit 0
fi

if [[ "$1" == "pr" && "$2" == "ready" ]]; then
  touch "$FAKE_GH_STATE_DIR/pr-ready"
  exit 0
fi

[[ "$1" == "api" ]] || exit 2
shift

method=GET
input=""
endpoint=""
while (($#)); do
  case "$1" in
    --method)
      method="$2"
      shift 2
      ;;
    --input)
      input="$2"
      shift 2
      ;;
    --jq)
      shift 2
      ;;
    --silent|-f)
      if [[ "$1" == "-f" ]]; then shift 2; else shift; fi
      ;;
    *)
      if [[ -z "$endpoint" ]]; then endpoint="$1"; fi
      shift
      ;;
  esac
done

case "$endpoint" in
  */git/matching-refs/heads/*)
    if [[ -f "$FAKE_GH_STATE_DIR/ref" ]]; then
      printf '[{"ref":"refs/heads/feature/publisher","object":{"sha":"api-commit"}}]\n'
    else
      printf '[]\n'
    fi
    ;;
  */git/commits/api-commit)
    printf '%s\n' "$FAKE_LOCAL_TREE"
    ;;
  */git/commits/*)
    printf '%s\n' "${endpoint##*/}"
    ;;
  */git/blobs)
    content="$(jq -r .content "$input")"
    sha="$(printf '%s' "$content" | base64 -d | git hash-object --stdin)"
    printf '%s\n' "$sha"
    ;;
  */git/trees)
    printf '%s\n' "$FAKE_LOCAL_TREE"
    ;;
  */git/commits)
    printf 'api-commit\n'
    ;;
  */git/refs|*/git/refs/heads/*)
    touch "$FAKE_GH_STATE_DIR/ref"
    ;;
  */pulls)
    if [[ "$method" == "POST" ]]; then
      touch "$FAKE_GH_STATE_DIR/pr"
      if jq -e '.draft == true' "$input" >/dev/null; then
        touch "$FAKE_GH_STATE_DIR/pr-draft"
      fi
      printf 'https://github.com/Tirso0882/flash-trips/pull/99\n'
    elif [[ -f "$FAKE_GH_STATE_DIR/pr" ]]; then
      draft=false
      [[ ! -f "$FAKE_GH_STATE_DIR/pr-draft" ]] || draft=true
      printf '[{"number":99,"draft":%s,"html_url":"https://github.com/Tirso0882/flash-trips/pull/99"}]\n' "$draft"
    else
      printf '[]\n'
    fi
    ;;
  *)
    printf 'unexpected fake gh endpoint: %s\n' "$endpoint" >&2
    exit 2
    ;;
esac
FAKE_GH
  chmod +x "$fake"
  printf '%s\n' "$fake"
}

bash -n "$publisher"
"$publisher" --help >/dev/null

main_repo="$(new_repo main-refusal main)"
if (cd "$main_repo" && "$publisher" --draft-pr >"$test_root/main.out" 2>&1); then
  fail "publisher accepted main"
fi
assert_contains "$test_root/main.out" "refusing to publish main"

dirty_repo="$(new_repo dirty-refusal feature/dirty)"
printf 'dirty\n' >>"$dirty_repo/tracked.txt"
if (cd "$dirty_repo" && "$publisher" --draft-pr >"$test_root/dirty.out" 2>&1); then
  fail "publisher accepted a dirty worktree without --allow-dirty"
fi
assert_contains "$test_root/dirty.out" "worktree is dirty"

publish_repo="$(new_repo publish feature/publisher)"
printf 'uncommitted\n' >"$publish_repo/untracked.txt"
fake_gh="$(make_fake_gh)"
mkdir -p "$test_root/fake-state"
export FAKE_GH_STATE_DIR="$test_root/fake-state"
export FAKE_LOCAL_TREE="$(git -C "$publish_repo" rev-parse 'HEAD^{tree}')"

if ! (cd "$publish_repo" && PUBLISH_GH_BIN="$fake_gh" "$publisher" --draft-pr --allow-dirty >"$test_root/first.out" 2>&1); then
  sed -n '1,80p' "$test_root/first.out" >&2
  fail "initial draft publication failed"
fi
assert_contains "$test_root/first.out" "Created draft PR"
assert_contains "$test_root/first.out" "Verified tree:"
[[ -f "$FAKE_GH_STATE_DIR/ref" ]] || fail "remote ref was not created"
[[ -f "$FAKE_GH_STATE_DIR/pr-draft" ]] || fail "draft PR was not requested"

blob_calls_before="$(rg -c 'git/blobs' "$FAKE_GH_STATE_DIR/calls.log")"
(cd "$publish_repo" && PUBLISH_GH_BIN="$fake_gh" "$publisher" --draft-pr --allow-dirty >"$test_root/second.out" 2>&1)
blob_calls_after="$(rg -c 'git/blobs' "$FAKE_GH_STATE_DIR/calls.log")"
[[ "$blob_calls_before" == "$blob_calls_after" ]] || fail "idempotent rerun uploaded blobs"
assert_contains "$test_root/second.out" "skipping Git object publication"
assert_contains "$test_root/second.out" "Reusing existing PR #99"

(cd "$publish_repo" && PUBLISH_GH_BIN="$fake_gh" "$publisher" --pr --allow-dirty >"$test_root/ready.out" 2>&1)
[[ -f "$FAKE_GH_STATE_DIR/pr-ready" ]] || fail "--pr did not mark the draft ready"
assert_contains "$test_root/ready.out" "Marked existing PR #99 ready"

printf 'PASS: publish-via-github-api\n'
