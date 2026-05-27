#!/bin/bash

# Configuration
USER_ID="harbor-bulk-import-${ZEALT_RUN_ID}"
LOG_FILE="/home/user/bulk-import/output.log"

# Clear/Initialize log file
echo "User ID: $USER_ID" > "$LOG_FILE"

# Preferences to ingest
PREFERENCES=(
    "I prefer dark mode in every application and avoid bright UI themes."
    "I work in the America/Los_Angeles timezone and prefer afternoon meetings."
    "I am vegetarian and have a severe peanut allergy."
    "My primary programming language is Python and my editor is Neovim."
)

# Ingest memories
# We'll use a temporary file to keep track of seen IDs to ensure we get the NEW one
SEEN_IDS=()

for pref in "${PREFERENCES[@]}"; do
    mem0 --agent add "$pref" --user-id "$USER_ID" > /dev/null
    
    # Wait for processing (Mem0 platform is usually fast but async)
    sleep 3
    
    # Get all memories for this user
    LIST_RESPONSE=$(mem0 --agent list --user-id "$USER_ID")
    
    # Find the memory ID that is NOT in our SEEN_IDS list
    # Since we add them one by one, the newest one is likely at the top, 
    # but let's be safe and pick the one that isn't seen yet.
    CURRENT_IDS=$(echo "$LIST_RESPONSE" | jq -r '.data[].id')
    
    NEW_ID=""
    for id in $CURRENT_IDS; do
        is_seen=false
        for seen in "${SEEN_IDS[@]}"; do
            if [ "$id" == "$seen" ]; then
                is_seen=true
                break
            fi
        done
        if [ "$is_seen" == false ]; then
            NEW_ID=$id
            break
        fi
    done

    if [ -n "$NEW_ID" ]; then
        echo "Added memory: $NEW_ID" >> "$LOG_FILE"
        SEEN_IDS+=("$NEW_ID")
    else
        echo "Failed to extract ID for preference: $pref" >> "$LOG_FILE"
    fi
done

# Search memories
SEARCH_QUERY="dietary restrictions"
SEARCH_RESPONSE=$(mem0 --agent search "$SEARCH_QUERY" --user-id "$USER_ID" --top-k 5)

# Count hits
HITS_COUNT=$(echo "$SEARCH_RESPONSE" | jq '.data | length')

echo "Search hits: $HITS_COUNT" >> "$LOG_FILE"
