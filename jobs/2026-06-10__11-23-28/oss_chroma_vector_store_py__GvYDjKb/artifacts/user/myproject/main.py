#!/usr/bin/env python3
"""Mem0 OSS with Chroma Vector Store — full memory lifecycle demo.

Reads the run-id from ZEALT_RUN_ID, wires Mem0 to a persistent Chroma backend,
ingests a conversation about Alex, then exercises add/search/update/delete/get_all.
Writes a structured JSON report and a human-readable log.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from mem0 import Memory

# ── Configuration ────────────────────────────────────────────────────────────

RUN_ID = os.environ["ZEALT_RUN_ID"]
COLLECTION_NAME = f"mem0_demo_{RUN_ID}"
CHROMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.log")
RESULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "result.json")
USER_ID = "alex"

# ── Logging setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, mode="w"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("mem0_demo")

log.info("=== Mem0 + Chroma Demo ===")
log.info("Run ID: %s", RUN_ID)
log.info("Collection name: %s", COLLECTION_NAME)
log.info("Chroma persistence path: %s", CHROMA_PATH)

# ── Build Memory instance ────────────────────────────────────────────────────

config = {
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": COLLECTION_NAME,
            "path": CHROMA_PATH,
        },
    },
}

log.info("Creating Memory instance with Chroma vector store...")
m = Memory.from_config(config_dict=config)
log.info("Memory instance created successfully.")

# ── Ingest conversation ──────────────────────────────────────────────────────

conversation = [
    {"role": "user", "content": "Hi, my name is Alex and I'm a vegan."},
    {"role": "assistant", "content": "Nice to meet you, Alex! I'll remember that you're vegan."},
    {"role": "user", "content": "I also really enjoy hiking on weekends. It's my favorite outdoor activity."},
    {"role": "assistant", "content": "That sounds great, Alex! Hiking on weekends is a wonderful way to stay active."},
]

log.info("Adding conversation to Mem0 (user_id=%s)...", USER_ID)
add_response = m.add(
    conversation,
    user_id=USER_ID,
    metadata={"category": "preferences"},
)

results = add_response.get("results", [])
added_memory_ids = [item["id"] for item in results]

log.info("Added %d memories: %s", len(added_memory_ids), added_memory_ids)
for item in results:
    log.info("  [%s] %s → %s", item["event"], item["id"], item["memory"])

# ── Semantic search ──────────────────────────────────────────────────────────

search_query = "What does Alex like to eat?"
log.info("Searching for: '%s'", search_query)
search_response = m.search(search_query, user_id=USER_ID, top_k=10)
search_results = search_response.get("results", [])
search_result_count = len(search_results)
log.info("Search returned %d results.", search_result_count)
for sr in search_results:
    log.info("  score=%.4f id=%s memory=%s", sr["score"], sr["id"], sr["memory"])

# ── Update one memory ────────────────────────────────────────────────────────

update_memory_id = added_memory_ids[0]
update_memory_text = "Alex now prefers vegetarian food and tracks calories."

log.info("Updating memory %s → '%s'", update_memory_id, update_memory_text)
update_response = m.update(memory_id=update_memory_id, data=update_memory_text)
log.info("Update response: %s", update_response)

# ── Delete a different memory ────────────────────────────────────────────────

delete_memory_id = added_memory_ids[1]
log.info("Deleting memory %s", delete_memory_id)
delete_response = m.delete(memory_id=delete_memory_id)
log.info("Delete response: %s", delete_response)

# ── Final inventory ──────────────────────────────────────────────────────────

log.info("Fetching final memory inventory for user_id=%s...", USER_ID)
get_all_response = m.get_all(user_id=USER_ID, top_k=100)
final_memories = get_all_response.get("results", [])
final_memory_count = len(final_memories)
log.info("Final memory count: %d", final_memory_count)
for mem in final_memories:
    log.info("  [%s] %s", mem["id"], mem["memory"])

# ── Verify update persisted ──────────────────────────────────────────────────

log.info("Verifying updated memory via get()...")
verified = m.get(memory_id=update_memory_id)
log.info("  Retrieved: %s", verified.get("memory"))

# ── Write structured JSON report ─────────────────────────────────────────────

report = {
    "run_id": RUN_ID,
    "collection_name": COLLECTION_NAME,
    "user_id": USER_ID,
    "added_memory_ids": added_memory_ids,
    "updated_memory_id": update_memory_id,
    "updated_memory_text": update_memory_text,
    "deleted_memory_id": delete_memory_id,
    "search_query": search_query,
    "search_result_count": search_result_count,
    "final_memory_count": final_memory_count,
    "timestamp": datetime.now(timezone.utc).isoformat(),
}

with open(RESULT_PATH, "w") as f:
    json.dump(report, f, indent=2)

log.info("Report written to %s", RESULT_PATH)
log.info("=== Done ===")
