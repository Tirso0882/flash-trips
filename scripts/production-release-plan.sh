#!/usr/bin/env bash

set -euo pipefail

event_name="${1:-}"
release_sha="${2:-}"

if [[ -z "$event_name" || -z "$release_sha" ]]; then
  printf 'usage: %s EVENT_NAME RELEASE_SHA\n' "$(basename "$0")" >&2
  exit 2
fi

git cat-file -e "${release_sha}^{commit}"

if [[ "$event_name" == "workflow_dispatch" ]]; then
  printf 'deploy=true\n'
  printf 'reason=manual production release requested\n'
  exit 0
fi

if [[ "$event_name" != "workflow_run" ]]; then
  printf 'unsupported GitHub event: %s\n' "$event_name" >&2
  exit 2
fi

read -r -a commit_and_parents <<<"$(git rev-list --parents -n 1 "$release_sha")"
if ((${#commit_and_parents[@]} == 1)); then
  printf 'deploy=true\n'
  printf 'reason=initial production commit has no parent\n'
  exit 0
fi
parent_sha="${commit_and_parents[1]}"

while IFS= read -r path; do
  case "$path" in
    .dockerignore | \
      package.json | \
      pnpm-lock.yaml | \
      pnpm-workspace.yaml | \
      pyproject.toml | \
      uv.lock | \
      apps/api/* | \
      apps/web/* | \
      contracts/ts/* | \
      src/*)
      printf 'deploy=true\n'
      printf 'reason=deployable production inputs changed\n'
      exit 0
      ;;
  esac
done < <(git diff --name-only "$parent_sha" "$release_sha")

printf 'deploy=false\n'
printf 'reason=no deployable production inputs changed\n'
