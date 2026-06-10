#!/usr/bin/env bash
set -euo pipefail

# Ensure ZEALT_RUN_ID is set
if [ -z "${ZEALT_RUN_ID:-}" ]; then
  echo "Error: ZEALT_RUN_ID is not set." >&2
  exit 1
fi

USER_ID="harbor-bulk-import-${ZEALT_RUN_ID}"
LOG_FILE="/home/user/bulk-import/output.log"

# Recreate the log file
echo "User ID: ${USER_ID}" > "$LOG_FILE"

# Array of preference statements
PREFERENCES=(
  "I prefer dark mode in every application and avoid bright UI themes."
  "I work in the America/Los_Angeles timezone and prefer afternoon meetings."
  "I am vegetarian and have a severe peanut allergy."
  "My primary programming language is Python and my editor is Neovim."
)

echo "Starting ingestion for user: ${USER_ID}"

for pref in "${PREFERENCES[@]}"; do
  echo "Adding preference: $pref"
  # Run mem0 add and extract event_id
  add_response=$(mem0 add "$pref" --user-id "$USER_ID" -o json 2>/dev/null)
  event_id=$(echo "$add_response" | jq -r '.event_id')
  
  if [ -z "$event_id" ] || [ "$event_id" = "null" ]; then
    echo "Error: Failed to get event_id for preference: $pref" >&2
    echo "Response was: $add_response" >&2
    exit 1
  fi
  
  echo "Event ID: $event_id. Polling for completion..."
  
  # Poll event status
  while true; do
    status_response=$(mem0 event status "$event_id" -o json 2>/dev/null)
    status=$(echo "$status_response" | jq -r '.data.status')
    
    if [ "$status" = "SUCCEEDED" ]; then
      # Extract memory ID
      memory_id=$(echo "$status_response" | jq -r '.data.results[0].id')
      if [ -z "$memory_id" ] || [ "$memory_id" = "null" ]; then
        echo "Error: Memory ID was empty in succeeded event results." >&2
        echo "Response was: $status_response" >&2
        exit 1
      fi
      echo "Added memory: $memory_id"
      echo "Added memory: $memory_id" >> "$LOG_FILE"
      break
    elif [ "$status" = "FAILED" ]; then
      echo "Error: Event $event_id failed to process." >&2
      echo "Response was: $status_response" >&2
      exit 1
    fi
    sleep 2
  done
done

echo "Ingestion completed. Performing search..."

# Run mem0 search
search_response=$(mem0 search "dietary restrictions" --user-id "$USER_ID" --top-k 5 -o json 2>/dev/null)
search_hits=$(echo "$search_response" | jq '. | length')

echo "Search hits: $search_hits"
echo "Search hits: $search_hits" >> "$LOG_FILE"

echo "Workflow finished successfully. Log file written to $LOG_FILE"
