#!/usr/bin/env bash

set -euo pipefail

PROGRAM_NAME="$(basename "$0")"
GH_BIN="${PUBLISH_GH_BIN:-gh}"
GIT_BIN="${PUBLISH_GIT_BIN:-git}"

usage() {
  cat <<EOF
Usage: $PROGRAM_NAME (--draft-pr | --pr) [--allow-dirty]

Publish the committed HEAD tree through the GitHub Git Data API, then create
or reuse a pull request for the current branch.

  --draft-pr    Create a draft PR when none exists. Reuse an existing PR
                without changing a ready PR back to draft.
  --pr          Create a ready PR when none exists, or mark an existing draft
                PR ready for review.
  --allow-dirty Permit a dirty worktree. Only committed HEAD is published;
                working-tree and index changes are never included.
  -h, --help    Show this help.

The API-created commit SHA may differ from the local commit SHA. Success is
determined by an exact local-versus-remote Git tree hash comparison.
EOF
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

temp_dir=""

cleanup() {
  if [[ -n "$temp_dir" && -d "$temp_dir" ]]; then
    rm -rf -- "$temp_dir"
  fi
}

ensure_temp_dir() {
  if [[ -z "$temp_dir" ]]; then
    temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/flash-trips-publish.XXXXXX")"
    trap cleanup EXIT
  fi
}

urlencode() {
  jq -rn --arg value "$1" '$value | @uri'
}

pr_mode=""
allow_dirty=false

while (($#)); do
  case "$1" in
    --draft-pr)
      [[ -z "$pr_mode" ]] || fail "choose exactly one of --draft-pr or --pr"
      pr_mode="draft"
      ;;
    --pr)
      [[ -z "$pr_mode" ]] || fail "choose exactly one of --draft-pr or --pr"
      pr_mode="ready"
      ;;
    --allow-dirty)
      allow_dirty=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
  shift
done

[[ -n "$pr_mode" ]] || fail "choose exactly one of --draft-pr or --pr"

require_command "$GIT_BIN"
require_command "$GH_BIN"
require_command jq
require_command base64

repo_root="$($GIT_BIN rev-parse --show-toplevel 2>/dev/null)" || fail "not inside a Git repository"
cd "$repo_root"

branch="$($GIT_BIN symbolic-ref --quiet --short HEAD 2>/dev/null)" || fail "detached HEAD cannot be published"
[[ "$branch" != "main" ]] || fail "refusing to publish main"

local_head="$($GIT_BIN rev-parse --verify HEAD)"
local_tree="$($GIT_BIN rev-parse 'HEAD^{tree}')"

if [[ -n "$($GIT_BIN status --porcelain)" ]]; then
  if [[ "$allow_dirty" != true ]]; then
    fail "worktree is dirty; commit or clean it, or pass --allow-dirty to publish committed HEAD only"
  fi
  printf 'warning: dirty worktree allowed; publishing committed HEAD only\n' >&2
fi

"$GH_BIN" auth status >/dev/null
repo="$($GH_BIN repo view --json nameWithOwner --jq .nameWithOwner)"
default_branch="$($GH_BIN repo view "$repo" --json defaultBranchRef --jq .defaultBranchRef.name)"
[[ -n "$repo" && -n "$default_branch" ]] || fail "could not resolve repository and default branch"
[[ "$branch" != "$default_branch" ]] || fail "refusing to publish the default branch: $default_branch"

encoded_branch="$(urlencode "$branch")"
remote_ref="refs/heads/$branch"

refs_json="$($GH_BIN api "repos/$repo/git/matching-refs/heads/$encoded_branch")"
remote_sha="$(printf '%s' "$refs_json" | jq -r --arg ref "$remote_ref" '[.[] | select(.ref == $ref)][0].object.sha // empty')"

branch_exists=false
if [[ -n "$remote_sha" ]]; then
  branch_exists=true
  parent_sha="$remote_sha"
  remote_tree="$($GH_BIN api "repos/$repo/git/commits/$remote_sha" --jq .tree.sha)"
else
  if "$GIT_BIN" show-ref --verify --quiet "refs/remotes/origin/$default_branch"; then
    local_base_ref="refs/remotes/origin/$default_branch"
  elif "$GIT_BIN" show-ref --verify --quiet "refs/heads/$default_branch"; then
    local_base_ref="refs/heads/$default_branch"
  else
    fail "cannot find a local $default_branch or origin/$default_branch ref for the first publication"
  fi
  local_base_sha="$($GIT_BIN merge-base HEAD "$local_base_ref")"
  [[ -n "$local_base_sha" ]] || fail "current branch has no merge base with $local_base_ref"
  parent_sha="$($GH_BIN api "repos/$repo/git/commits/$local_base_sha" --jq .sha)"
  [[ "$parent_sha" == "$local_base_sha" ]] || fail "GitHub does not contain the local merge-base commit $local_base_sha"
  remote_tree=""
fi

published_sha="$remote_sha"

if [[ "$remote_tree" == "$local_tree" ]]; then
  printf 'Remote branch already has committed tree %s; skipping Git object publication.\n' "$local_tree"
else
  ensure_temp_dir
  entries_file="$temp_dir/tree-entries.jsonl"
  : >"$entries_file"

  while IFS= read -r -d '' entry; do
    metadata="${entry%%$'\t'*}"
    path="${entry#*$'\t'}"
    IFS=' ' read -r mode object_type object_sha <<<"$metadata"

    [[ "$object_type" == "blob" ]] || fail "unsupported tracked object at $path: $object_type (submodules are not supported)"

    blob_size="$($GIT_BIN cat-file -s "$object_sha")"
    ((blob_size <= 100000000)) || fail "GitHub blob limit exceeded by $path ($blob_size bytes)"

    blob_base64_file="$temp_dir/blob.b64"
    "$GIT_BIN" cat-file blob "$object_sha" | base64 | tr -d '\n' >"$blob_base64_file"
    blob_payload="$temp_dir/blob-payload.json"
    jq -n --rawfile content "$blob_base64_file" '{content: $content, encoding: "base64"}' >"$blob_payload"
    uploaded_sha="$($GH_BIN api --method POST "repos/$repo/git/blobs" --input "$blob_payload" --jq .sha)"
    [[ "$uploaded_sha" == "$object_sha" ]] || fail "uploaded blob hash mismatch for $path"

    jq -nc \
      --arg path "$path" \
      --arg mode "$mode" \
      --arg sha "$uploaded_sha" \
      '{path: $path, mode: $mode, type: "blob", sha: $sha}' >>"$entries_file"
  done < <("$GIT_BIN" ls-tree -rz --full-tree HEAD)

  tree_payload="$temp_dir/tree-payload.json"
  jq -s '{tree: .}' "$entries_file" >"$tree_payload"
  published_tree="$($GH_BIN api --method POST "repos/$repo/git/trees" --input "$tree_payload" --jq .sha)"
  [[ "$published_tree" == "$local_tree" ]] || fail "API tree hash $published_tree does not match local tree $local_tree"

  commit_message="$($GIT_BIN log -1 --format=%B HEAD)"
  author_name="$($GIT_BIN log -1 --format=%an HEAD)"
  author_email="$($GIT_BIN log -1 --format=%ae HEAD)"
  author_date="$($GIT_BIN log -1 --format=%aI HEAD)"
  committer_name="$($GIT_BIN log -1 --format=%cn HEAD)"
  committer_email="$($GIT_BIN log -1 --format=%ce HEAD)"
  committer_date="$($GIT_BIN log -1 --format=%cI HEAD)"

  commit_payload="$temp_dir/commit-payload.json"
  jq -n \
    --arg message "$commit_message" \
    --arg tree "$published_tree" \
    --arg parent "$parent_sha" \
    --arg author_name "$author_name" \
    --arg author_email "$author_email" \
    --arg author_date "$author_date" \
    --arg committer_name "$committer_name" \
    --arg committer_email "$committer_email" \
    --arg committer_date "$committer_date" \
    '{
      message: $message,
      tree: $tree,
      parents: [$parent],
      author: {name: $author_name, email: $author_email, date: $author_date},
      committer: {name: $committer_name, email: $committer_email, date: $committer_date}
    }' >"$commit_payload"

  published_sha="$($GH_BIN api --method POST "repos/$repo/git/commits" --input "$commit_payload" --jq .sha)"

  ref_payload="$temp_dir/ref-payload.json"
  if [[ "$branch_exists" == true ]]; then
    jq -n --arg sha "$published_sha" '{sha: $sha, force: false}' >"$ref_payload"
    "$GH_BIN" api --method PATCH "repos/$repo/git/refs/heads/$encoded_branch" --input "$ref_payload" --silent
  else
    jq -n --arg ref "$remote_ref" --arg sha "$published_sha" '{ref: $ref, sha: $sha}' >"$ref_payload"
    "$GH_BIN" api --method POST "repos/$repo/git/refs" --input "$ref_payload" --silent
  fi
fi

verified_refs_json="$($GH_BIN api "repos/$repo/git/matching-refs/heads/$encoded_branch")"
verified_sha="$(printf '%s' "$verified_refs_json" | jq -r --arg ref "$remote_ref" '[.[] | select(.ref == $ref)][0].object.sha // empty')"
[[ -n "$verified_sha" ]] || fail "remote branch was not found after publication"
verified_tree="$($GH_BIN api "repos/$repo/git/commits/$verified_sha" --jq .tree.sha)"
[[ "$verified_tree" == "$local_tree" ]] || fail "remote tree $verified_tree does not match local tree $local_tree"

owner="${repo%%/*}"
pulls_json="$($GH_BIN api --method GET "repos/$repo/pulls" -f state=open -f "head=$owner:$branch")"
pr_number="$(printf '%s' "$pulls_json" | jq -r '.[0].number // empty')"
pr_is_draft="$(printf '%s' "$pulls_json" | jq -r '.[0].draft // empty')"
pr_url="$(printf '%s' "$pulls_json" | jq -r '.[0].html_url // empty')"

if [[ -n "$pr_number" ]]; then
  if [[ "$pr_mode" == "ready" && "$pr_is_draft" == "true" ]]; then
    "$GH_BIN" pr ready "$pr_number" --repo "$repo" >/dev/null
    printf 'Marked existing PR #%s ready for review: %s\n' "$pr_number" "$pr_url"
  else
    printf 'Reusing existing PR #%s: %s\n' "$pr_number" "$pr_url"
  fi
else
  pr_title="$($GIT_BIN log -1 --format=%s HEAD)"
  pr_body="Published from committed local HEAD $local_head with scripts/$PROGRAM_NAME. Local and remote tree: $local_tree."
  ensure_temp_dir
  pr_payload="$temp_dir/pr-payload.json"
  if [[ "$pr_mode" == "draft" ]]; then
    draft_json=true
  else
    draft_json=false
  fi
  jq -n \
    --arg title "$pr_title" \
    --arg head "$branch" \
    --arg base "$default_branch" \
    --arg body "$pr_body" \
    --argjson draft "$draft_json" \
    '{title: $title, head: $head, base: $base, body: $body, draft: $draft}' >"$pr_payload"
  pr_url="$($GH_BIN api --method POST "repos/$repo/pulls" --input "$pr_payload" --jq .html_url)"
  printf 'Created %s PR: %s\n' "$pr_mode" "$pr_url"
fi

printf 'Published branch: %s\n' "$branch"
printf 'Local commit:    %s\n' "$local_head"
printf 'Remote commit:   %s\n' "$verified_sha"
printf 'Verified tree:   %s\n' "$verified_tree"
