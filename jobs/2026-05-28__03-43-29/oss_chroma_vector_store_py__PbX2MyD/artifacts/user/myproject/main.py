"""
Mem0 OSS + Chroma Vector Store demo.

Lifecycle:
  1. Configure Memory with Chroma backend (persisted to disk).
  2. Add conversation messages that establish Alex's preferences.
  3. Semantic search on food preference.
  4. Update one memory to an explicit text.
  5. Delete a different memory.
  6. Collect final inventory with get_all().
  7. Write result.json + output.log.

Compatible with mem0ai >= 2.0.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from mem0 import Memory

# ---------------------------------------------------------------------------
# Logging setup — writes to both stdout and output.log
# ---------------------------------------------------------------------------
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(PROJECT_DIR, "output.log")
RESULT_PATH = os.path.join(PROJECT_DIR, "result.json")
CHROMA_PATH = os.path.join(PROJECT_DIR, "chroma_db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Runtime configuration
# ---------------------------------------------------------------------------
RUN_ID = os.environ.get("ZEALT_RUN_ID", "default")
COLLECTION_NAME = f"mem0_demo_{RUN_ID}"
USER_ID = "alex"
UPDATED_TEXT = "Alex now prefers vegetarian food and tracks calories."

log.info("=" * 60)
log.info("Mem0 + Chroma demo starting")
log.info("Run-ID          : %s", RUN_ID)
log.info("Collection name : %s", COLLECTION_NAME)
log.info("Chroma path     : %s", CHROMA_PATH)
log.info("User-ID         : %s", USER_ID)
log.info("=" * 60)

# ---------------------------------------------------------------------------
# Build Mem0 Memory instance backed by Chroma
# ---------------------------------------------------------------------------
config = {
    "llm": {
        "provider": "openai",
        "config": {
            # gpt-4o-mini correctly honours max_tokens (unlike gpt-5-mini which
            # requires max_completion_tokens). Using the full model name avoids
            # the "unsupported parameter" 400 error from the OpenAI API.
            "model": "gpt-4o-mini",
            "temperature": 0.1,
            "max_tokens": 2000,
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small",
        },
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": COLLECTION_NAME,
            "path": CHROMA_PATH,
        },
    },
}

log.info("Initialising Memory from config …")
m = Memory.from_config(config)
log.info("Memory instance ready.")

# ---------------------------------------------------------------------------
# 1. Add conversation
# ---------------------------------------------------------------------------
conversation = [
    {
        "role": "user",
        "content": (
            "Hi, I'm Alex. I've been vegan for three years now and I love it. "
            "Every weekend I go hiking in the hills near my house — it really "
            "clears my head. I also meditate every morning."
        ),
    },
    {
        "role": "assistant",
        "content": (
            "That sounds wonderful, Alex! A vegan lifestyle combined with regular "
            "hiking and meditation is a great combination for wellbeing. "
            "Do you have a favourite trail?"
        ),
    },
    {
        "role": "user",
        "content": (
            "Yes — the Ridgeline Trail. I usually pack a vegan lunch and spend "
            "the whole morning out there. Hiking really is my favourite weekend activity."
        ),
    },
]

log.info("Adding conversation for user_id=%s …", USER_ID)
add_response = m.add(
    conversation,
    user_id=USER_ID,
    metadata={"category": "preferences"},
)
log.info("add() raw response: %s", json.dumps(add_response, default=str))

# mem0ai 2.x always returns {"results": [...]}
results = add_response.get("results", [])
added_memory_ids: list[str] = [r["id"] for r in results]

log.info("Memories added (%d): %s", len(added_memory_ids), added_memory_ids)

if len(added_memory_ids) < 2:
    log.error(
        "Expected at least 2 memories to be created, got %d. "
        "Cannot proceed with update + delete on distinct IDs.",
        len(added_memory_ids),
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Semantic search (food preference)  — v2 API uses filters=
# ---------------------------------------------------------------------------
SEARCH_QUERY = "What does Alex eat? Is Alex vegan or vegetarian?"
log.info("Searching with query: %r", SEARCH_QUERY)
search_response = m.search(
    SEARCH_QUERY,
    filters={"user_id": USER_ID},
)
log.info("search() raw response: %s", json.dumps(search_response, default=str))

if isinstance(search_response, dict):
    search_results = search_response.get("results", [])
else:
    search_results = list(search_response)

search_result_count = len(search_results)
log.info("Search returned %d result(s).", search_result_count)

# ---------------------------------------------------------------------------
# 3. Update first memory
# ---------------------------------------------------------------------------
update_id = added_memory_ids[0]
log.info("Updating memory %s to: %r", update_id, UPDATED_TEXT)
update_response = m.update(memory_id=update_id, data=UPDATED_TEXT)
log.info("update() response: %s", json.dumps(update_response, default=str))

# ---------------------------------------------------------------------------
# 4. Delete a different memory
# ---------------------------------------------------------------------------
delete_id = added_memory_ids[1]
log.info("Deleting memory %s …", delete_id)
delete_response = m.delete(memory_id=delete_id)
log.info("delete() response: %s", json.dumps(delete_response, default=str))

# ---------------------------------------------------------------------------
# 5. Final inventory — v2 API uses filters=
# ---------------------------------------------------------------------------
log.info("Fetching final inventory with get_all(filters={user_id: %r}) …", USER_ID)
all_response = m.get_all(filters={"user_id": USER_ID})
log.info("get_all() raw response: %s", json.dumps(all_response, default=str))

if isinstance(all_response, dict):
    final_memories = all_response.get("results", [])
else:
    final_memories = list(all_response)

final_memory_count = len(final_memories)
log.info("Final memory count: %d", final_memory_count)

# ---------------------------------------------------------------------------
# 6. Verify update persistence
# ---------------------------------------------------------------------------
log.info("Verifying updated memory via get(memory_id=%r) …", update_id)
got = m.get(memory_id=update_id)
log.info("get() response for updated memory: %s", json.dumps(got, default=str))

# ---------------------------------------------------------------------------
# 7. Write result.json
# ---------------------------------------------------------------------------
result = {
    "run_id": RUN_ID,
    "collection_name": COLLECTION_NAME,
    "user_id": USER_ID,
    "added_memory_ids": added_memory_ids,
    "updated_memory_id": update_id,
    "updated_memory_text": UPDATED_TEXT,
    "deleted_memory_id": delete_id,
    "search_query": SEARCH_QUERY,
    "search_result_count": search_result_count,
    "final_memory_count": final_memory_count,
    "timestamp": datetime.now(timezone.utc).isoformat(),
}

with open(RESULT_PATH, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2)

log.info("result.json written to %s", RESULT_PATH)
log.info("=" * 60)
log.info("Demo completed successfully.")
log.info("=" * 60)

print("\n--- result.json ---")
print(json.dumps(result, indent=2))
