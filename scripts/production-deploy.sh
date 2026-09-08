#!/usr/bin/env bash

# Deploy tested image digests to production and restore the previous digests
# when the post-deployment smoke test fails.
#
# Both container apps run in Single active revision mode, so traffic splitting
# is unavailable and a rollback re-pins the previous digest as a new revision.

set -euo pipefail

: "${RESOURCE_GROUP:?RESOURCE_GROUP is required}"
: "${API_APP_NAME:?API_APP_NAME is required}"
: "${API_FQDN:?API_FQDN is required}"
: "${API_IMAGE:?API_IMAGE is required}"
: "${WEB_APP_NAME:?WEB_APP_NAME is required}"
: "${WEB_IMAGE:?WEB_IMAGE is required}"
: "${PRODUCTION_URL:?PRODUCTION_URL is required}"

smoke_attempts="${SMOKE_ATTEMPTS:-30}"
smoke_delay_seconds="${SMOKE_DELAY_SECONDS:-10}"

summarize() {
  printf '%s\n' "$1"
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    printf '%s\n' "$1" >>"$GITHUB_STEP_SUMMARY"
  fi
}

live_image() {
  az containerapp show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$1" \
    --query 'properties.template.containers[0].image' \
    --output tsv
}

deploy_api() {
  az containerapp update \
    --resource-group "$RESOURCE_GROUP" \
    --name "$API_APP_NAME" \
    --image "$1" \
    --set-env-vars LIVE_CALL_ALLOWANCE=0
}

deploy_web() {
  az containerapp update \
    --resource-group "$RESOURCE_GROUP" \
    --name "$WEB_APP_NAME" \
    --image "$1" \
    --set-env-vars "FLASH_TRIPS_API_BASE_URL=https://$API_FQDN"
}

# Succeeds once production answers the status route through the web boundary,
# which exercises the web app, internal ingress, and the API together.
smoke_test() {
  local response attempt
  response="$(mktemp)"

  for ((attempt = 1; attempt <= smoke_attempts; attempt++)); do
    if curl --fail --silent --show-error \
      "$PRODUCTION_URL/api/status" >"$response" && [[ -s "$response" ]]; then
      return 0
    fi
    if ((attempt < smoke_attempts)); then
      sleep "$smoke_delay_seconds"
    fi
  done

  return 1
}

# A rollback target must be a real previously released image. The Bicep
# placeholder and a repeat of the failing digest are both unusable.
rollback_target() {
  local previous="$1" attempted="$2" repository="$3"

  if [[ -z "$previous" || "$previous" == "$attempted" ]]; then
    return 1
  fi
  if [[ "$previous" != *"$repository"* ]]; then
    return 1
  fi
  printf '%s\n' "$previous"
}

previous_api_image="$(live_image "$API_APP_NAME")"
previous_web_image="$(live_image "$WEB_APP_NAME")"

summarize "### Production deployment"
summarize ""
summarize "- Previous API image: \`${previous_api_image:-none}\`"
summarize "- Previous web image: \`${previous_web_image:-none}\`"
summarize "- Deploying API image: \`$API_IMAGE\`"
summarize "- Deploying web image: \`$WEB_IMAGE\`"

deploy_api "$API_IMAGE"
deploy_web "$WEB_IMAGE"

if smoke_test; then
  summarize "- Result: smoke test passed, release is live"
  exit 0
fi

summarize "- Result: smoke test failed after $smoke_attempts attempts"

rollback_api_image="$(rollback_target "$previous_api_image" "$API_IMAGE" flash-trips-api || true)"
rollback_web_image="$(rollback_target "$previous_web_image" "$WEB_IMAGE" flash-trips-web || true)"

if [[ -z "$rollback_api_image" || -z "$rollback_web_image" ]]; then
  summarize "- Rollback: skipped, no previously released digest to restore"
  summarize "- Action required: production is serving the failed release"
  exit 1
fi

summarize "- Rollback: restoring \`$rollback_api_image\` and \`$rollback_web_image\`"
deploy_api "$rollback_api_image"
deploy_web "$rollback_web_image"

if smoke_test; then
  summarize "- Rollback result: production restored to the previous release"
else
  summarize "- Rollback result: production still failing after rollback"
  summarize "- Action required: manual intervention"
fi

exit 1
