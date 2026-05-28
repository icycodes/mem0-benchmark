"""
Mem0 Platform — Async Client, Batch Update & History Audit
Fitness coaching: bulk-correct athlete memories, then audit the change log.
"""

import asyncio
import json
import os
import re
import sys

from mem0 import AsyncMemoryClient

# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------

MEM0_API_KEY = os.environ.get("MEM0_API_KEY")
ZEALT_RUN_ID = os.environ.get("ZEALT_RUN_ID")

if not MEM0_API_KEY:
    sys.exit("ERROR: MEM0_API_KEY environment variable is not set.")
if not ZEALT_RUN_ID:
    sys.exit("ERROR: ZEALT_RUN_ID environment variable is not set.")

# ---------------------------------------------------------------------------
# Per-run scoped entity identifiers (prevent collision across concurrent runs)
# ---------------------------------------------------------------------------

RUN_ID     = ZEALT_RUN_ID
USER_ID    = f"athlete-{RUN_ID}"
AGENT_ID   = f"coach-{RUN_ID}"
APP_ID     = f"fitness-app-{RUN_ID}"
SESSION_ID = f"session-{RUN_ID}"

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

BASE_DIR             = "/home/user/mem0-async-task"
ALL_MEMORIES_PATH    = f"{BASE_DIR}/all_memories.json"
BATCH_UPDATE_PATH    = f"{BASE_DIR}/batch_update_response.json"
BARBELL_HISTORY_PATH = f"{BASE_DIR}/barbell_history.json"
BATCH_DELETE_PATH    = f"{BASE_DIR}/batch_delete_response.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_memories(raw) -> list:
    """Return a plain list regardless of whether the SDK returned a list or
    an object with a 'results' key."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "results" in raw:
        return raw["results"]
    if isinstance(raw, dict):
        return [raw]
    return list(raw)


def _find_memory(memories: list, keyword: str) -> dict:
    """Return the first memory whose 'memory' field contains *keyword* (case-insensitive)."""
    kw = keyword.lower()
    for m in memories:
        text = m.get("memory", "")
        if kw in text.lower():
            return m
    raise ValueError(
        f"No memory containing '{keyword}' found. "
        f"Available memories: {[m.get('memory', '') for m in memories]}"
    )


def _parse_count_from_message(message: str, fallback: int) -> int:
    """Extract first integer from a message like 'Successfully updated 2 memories'."""
    match = re.search(r"\d+", str(message))
    return int(match.group()) if match else fallback


def _write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=str)


# ---------------------------------------------------------------------------
# Core async workflow
# ---------------------------------------------------------------------------

async def main() -> None:
    client = AsyncMemoryClient()  # reads MEM0_API_KEY from env

    # Shared entity kwargs used for every add() call
    entity_kwargs = dict(
        user_id=USER_ID,
        agent_id=AGENT_ID,
        app_id=APP_ID,
        run_id=SESSION_ID,
    )

    print(f"RUN_ID: {ZEALT_RUN_ID}")

    # -----------------------------------------------------------------------
    # STEP 1 — Ingest four memories concurrently
    # -----------------------------------------------------------------------
    print("Ingesting four memories concurrently …")

    add_tasks = [
        client.add(
            [{"role": "user", "content": "I run 5 kilometers every Tuesday morning."}],
            **entity_kwargs,
        ),
        client.add(
            [{"role": "user", "content": "I do strength training with kettlebells on Thursdays."}],
            **entity_kwargs,
        ),
        client.add(
            [{"role": "user", "content": "I prefer plant-based protein shakes after workouts."}],
            **entity_kwargs,
        ),
        client.add(
            [{"role": "user", "content": "My resting heart rate is around 58 bpm."}],
            **entity_kwargs,
        ),
    ]
    await asyncio.gather(*add_tasks)
    print("All four add() calls completed.")

    # -----------------------------------------------------------------------
    # STEP 2 — Wait for server-side extraction; poll until ≥ 4 memories appear
    #
    # NOTE: Per Mem0 docs, memories are stored per-entity scope. Combining
    # user_id + agent_id + app_id + run_id in AND returns no results because
    # no single record holds all four simultaneously. Use user_id alone to
    # retrieve the records written under this run's user scope.
    # -----------------------------------------------------------------------
    v2_filters = {
        "AND": [
            {"user_id": USER_ID},
        ]
    }

    memories: list = []
    max_attempts = 20
    wait_seconds = 5
    for attempt in range(1, max_attempts + 1):
        raw = await client.get_all(filters=v2_filters)
        memories = _normalize_memories(raw)
        print(f"  [poll {attempt}/{max_attempts}] Retrieved {len(memories)} memories …")
        if len(memories) >= 4:
            break
        if attempt < max_attempts:
            await asyncio.sleep(wait_seconds)
    else:
        print(
            f"WARNING: Only {len(memories)} memories retrieved after {max_attempts} polls. "
            "Continuing with what is available."
        )

    print(f"TOTAL_MEMORIES: {len(memories)}")

    # Persist all_memories.json
    _write_json(
        ALL_MEMORIES_PATH,
        {
            "user_id":  USER_ID,
            "agent_id": AGENT_ID,
            "app_id":   APP_ID,
            "run_id":   SESSION_ID,
            "memories": memories,
        },
    )
    print(f"Wrote {ALL_MEMORIES_PATH}")

    # -----------------------------------------------------------------------
    # STEP 3 — Identify the three memories of interest
    # -----------------------------------------------------------------------
    # Try multiple keyword variants to handle platform deduplication / merging
    def find_kettlebells(mems):
        for kw in ("kettlebells", "kettlebell", "strength training"):
            try:
                return _find_memory(mems, kw)
            except ValueError:
                pass
        raise ValueError("Cannot locate kettlebells/strength-training memory")

    def find_plant_based(mems):
        for kw in ("plant-based", "plant based", "protein shakes"):
            try:
                return _find_memory(mems, kw)
            except ValueError:
                pass
        raise ValueError("Cannot locate plant-based/protein-shakes memory")

    def find_heart_rate(mems):
        for kw in ("heart rate", "resting heart", "58 bpm", "bpm"):
            try:
                return _find_memory(mems, kw)
            except ValueError:
                pass
        raise ValueError("Cannot locate heart-rate memory")

    barbell_mem   = find_kettlebells(memories)
    nutrition_mem = find_plant_based(memories)
    heart_mem     = find_heart_rate(memories)

    BARBELL_ID   = barbell_mem["id"]
    NUTRITION_ID = nutrition_mem["id"]
    HEART_ID     = heart_mem["id"]

    print(f"BARBELL_ID: {BARBELL_ID}")
    print(f"NUTRITION_ID: {NUTRITION_ID}")
    print(f"HEART_ID: {HEART_ID}")

    # -----------------------------------------------------------------------
    # STEP 4 — Batch-update BARBELL and NUTRITION in one SDK call
    # -----------------------------------------------------------------------
    print("Submitting batch_update for BARBELL and NUTRITION …")
    batch_update_payload = [
        {"memory_id": BARBELL_ID,   "text": "Strength training with dumbbells on Thursdays"},
        {"memory_id": NUTRITION_ID, "text": "Prefers whey protein shakes after workouts"},
    ]
    update_response = await client.batch_update(memories=batch_update_payload)
    _write_json(BATCH_UPDATE_PATH, update_response)
    print(f"Wrote {BATCH_UPDATE_PATH}")

    # Determine BATCH_UPDATE_COUNT from response or payload length
    if isinstance(update_response, dict) and "message" in update_response:
        batch_update_count = _parse_count_from_message(
            update_response["message"], len(batch_update_payload)
        )
    else:
        batch_update_count = len(batch_update_payload)
    print(f"BATCH_UPDATE_COUNT: {batch_update_count}")

    # -----------------------------------------------------------------------
    # STEP 5 — History audit for BARBELL_ID
    #          Give the platform time to index the UPDATE event, then poll.
    # -----------------------------------------------------------------------
    print("Waiting 20 s for batch_update to be indexed before polling history …")
    await asyncio.sleep(20)

    print(f"Fetching history for BARBELL_ID={BARBELL_ID} …")
    history_events: list = []
    max_hist_attempts = 20
    hist_wait = 8
    for attempt in range(1, max_hist_attempts + 1):
        raw_history = await client.history(memory_id=BARBELL_ID)
        history_events = (
            raw_history if isinstance(raw_history, list) else list(raw_history)
        )
        print(
            f"  [history poll {attempt}/{max_hist_attempts}] "
            f"{len(history_events)} event(s) found …"
        )
        if len(history_events) >= 2:
            break
        if attempt < max_hist_attempts:
            await asyncio.sleep(hist_wait)

    _write_json(
        BARBELL_HISTORY_PATH,
        {
            "memory_id":    BARBELL_ID,
            "updated_text": "Strength training with dumbbells on Thursdays",
            "history":      history_events,
        },
    )
    print(f"Wrote {BARBELL_HISTORY_PATH}")
    print(f"HISTORY_EVENTS: {len(history_events)}")

    # -----------------------------------------------------------------------
    # STEP 6 — Batch-delete HEART_ID
    # -----------------------------------------------------------------------
    print(f"Submitting batch_delete for HEART_ID={HEART_ID} …")
    batch_delete_payload = [{"memory_id": HEART_ID}]
    delete_response = await client.batch_delete(memories=batch_delete_payload)
    _write_json(BATCH_DELETE_PATH, delete_response)
    print(f"Wrote {BATCH_DELETE_PATH}")

    if isinstance(delete_response, dict) and "message" in delete_response:
        batch_delete_count = _parse_count_from_message(
            delete_response["message"], len(batch_delete_payload)
        )
    else:
        batch_delete_count = len(batch_delete_payload)
    print(f"BATCH_DELETE_COUNT: {batch_delete_count}")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
