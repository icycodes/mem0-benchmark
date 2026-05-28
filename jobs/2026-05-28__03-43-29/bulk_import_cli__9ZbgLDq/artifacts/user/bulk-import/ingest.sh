#!/usr/bin/env bash
# ingest.sh — Bulk-ingest user preferences into Mem0 and log the results.
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
RUN_ID="${ZEALT_RUN_ID}"
USER_ID="harbor-bulk-import-${RUN_ID}"
LOG_FILE="/home/user/bulk-import/output.log"

# ── Preferences to ingest (in order) ──────────────────────────────────────────
PREFS=(
  "I prefer dark mode in every application and avoid bright UI themes."
  "I work in the America/Los_Angeles timezone and prefer afternoon meetings."
  "I am vegetarian and have a severe peanut allergy."
  "My primary programming language is Python and my editor is Neovim."
)

# ── Helper: wait for an ADD event to be resolved, then return the memory id ───
# Usage: resolve_event_id <event_id>
resolve_event_id() {
  local event_id="$1"
  local mem_id=""
  local attempts=0
  local max_attempts=20

  while [[ -z "${mem_id}" || "${mem_id}" == "null" ]]; do
    if (( attempts >= max_attempts )); then
      echo "ERROR: event ${event_id} did not resolve after ${max_attempts} attempts." >&2
      exit 1
    fi
    sleep 1
    local status_json
    status_json="$(mem0 event status "${event_id}" \
      --output json \
      --api-key "${MEM0_API_KEY}" 2>/dev/null)"
    # data.results[0].id holds the real memory uuid once SUCCEEDED
    mem_id="$(printf '%s' "${status_json}" | jq -r '.data.results[0].id // empty' 2>/dev/null || true)"
    (( attempts++ ))
  done

  printf '%s' "${mem_id}"
}

# ── Idempotency: remove any pre-existing memories for this user ───────────────
echo "Cleaning up any pre-existing memories for user '${USER_ID}'…"
EXISTING="$(mem0 list --user-id "${USER_ID}" --output json --api-key "${MEM0_API_KEY}" 2>/dev/null)"
EXISTING_IDS="$(printf '%s' "${EXISTING}" | jq -r '.data[].id // empty' 2>/dev/null || true)"
if [[ -n "${EXISTING_IDS}" ]]; then
  while IFS= read -r mid; do
    echo "  Deleting pre-existing memory: ${mid}"
    mem0 delete "${mid}" --api-key "${MEM0_API_KEY}" >/dev/null 2>&1 || true
  done <<< "${EXISTING_IDS}"
fi

# ── (Re)create the log file with a header ─────────────────────────────────────
printf 'User ID: %s\n' "${USER_ID}" > "${LOG_FILE}"

# ── Ingest each preference as a separate memory ───────────────────────────────
for pref in "${PREFS[@]}"; do
  echo "Adding: ${pref}"

  ADD_RESPONSE="$(mem0 add "${pref}" \
    --user-id "${USER_ID}" \
    --output json \
    --api-key "${MEM0_API_KEY}" 2>/dev/null)"

  # The platform returns an event_id; poll until the ADD event is SUCCEEDED.
  EVENT_ID="$(printf '%s' "${ADD_RESPONSE}" | jq -r '.event_id // .results[0].event_id // empty')"

  if [[ -z "${EVENT_ID}" || "${EVENT_ID}" == "null" ]]; then
    echo "ERROR: no event_id in add response: ${ADD_RESPONSE}" >&2
    exit 1
  fi

  MEM_ID="$(resolve_event_id "${EVENT_ID}")"
  printf 'Added memory: %s\n' "${MEM_ID}" | tee -a "${LOG_FILE}"
done

# ── Search for dietary restrictions ───────────────────────────────────────────
echo "Searching for 'dietary restrictions'…"
SEARCH_RESPONSE="$(mem0 search "dietary restrictions" \
  --user-id "${USER_ID}" \
  --top-k 5 \
  --output json \
  --api-key "${MEM0_API_KEY}" 2>/dev/null)"

# The search response is a plain JSON array of result objects.
HIT_COUNT="$(printf '%s' "${SEARCH_RESPONSE}" | jq -r '
  if type == "array" then length
  elif .results and (.results | type) == "array" then (.results | length)
  elif .data and (.data | type) == "array" then (.data | length)
  else 0
  end
')"

printf 'Search hits: %s\n' "${HIT_COUNT}" | tee -a "${LOG_FILE}"

echo ""
echo "=== Log file contents ==="
cat "${LOG_FILE}"
echo "==========================="
echo "Done. Log written to ${LOG_FILE}"
