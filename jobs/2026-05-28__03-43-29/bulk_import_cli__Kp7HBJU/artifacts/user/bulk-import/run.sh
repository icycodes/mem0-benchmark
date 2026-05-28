#!/bin/bash
set -e

# Ensure dependencies
if ! command -v jq &> /dev/null; then
    apt-get update && apt-get install -y jq
fi

USER_ID="harbor-bulk-import-${ZEALT_RUN_ID}"
LOG_FILE="/home/user/bulk-import/output.log"

mkdir -p /home/user/bulk-import

# Initialize log file from scratch (idempotent)
echo "User ID: ${USER_ID}" > "$LOG_FILE"

# Clean up any existing memories for this user to ensure idempotency
mem0 delete --all -u "$USER_ID" --force >/dev/null 2>&1 || true

# Preferences to ingest
PREFS=(
  "I prefer dark mode in every application and avoid bright UI themes."
  "I work in the America/Los_Angeles timezone and prefer afternoon meetings."
  "I am vegetarian and have a severe peanut allergy."
  "My primary programming language is Python and my editor is Neovim."
)

for pref in "${PREFS[@]}"; do
  # Add memory with --no-infer to guarantee exactly 1 memory per statement
  ADD_OUTPUT=$(mem0 add "$pref" --user-id "$USER_ID" --no-infer -o json)
  
  # Parse memory ID using jq
  MEMORY_ID=$(echo "$ADD_OUTPUT" | jq -r '.results[0].id')
  
  if [ "$MEMORY_ID" = "null" ] || [ -z "$MEMORY_ID" ]; then
    echo "Failed to get memory ID for pref: $pref"
    echo "Output was: $ADD_OUTPUT"
    exit 1
  fi
  
  echo "Added memory: $MEMORY_ID" >> "$LOG_FILE"
done

# Search for dietary restrictions
SEARCH_OUTPUT=$(mem0 search "dietary restrictions" --user-id "$USER_ID" --top-k 5 -o json)
# Count results using jq
HIT_COUNT=$(echo "$SEARCH_OUTPUT" | jq '. | length')

echo "Search hits: $HIT_COUNT" >> "$LOG_FILE"
