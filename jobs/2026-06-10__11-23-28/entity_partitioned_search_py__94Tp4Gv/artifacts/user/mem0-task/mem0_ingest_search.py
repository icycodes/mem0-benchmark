#!/usr/bin/env python3
"""
Mem0 Platform — Entity-Partitioned Memory Ingest and Filtered Search

Ingests multi-turn conversations for two travelers (Alice and Bob) under
entity-scoped identifiers, then performs v2 compound filter searches to
retrieve isolated memories for each traveler.
"""

import json
import os
import sys
import time
from mem0 import MemoryClient

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
MEM0_API_KEY = os.environ.get("MEM0_API_KEY")
ZEALT_RUN_ID = os.environ.get("ZEALT_RUN_ID")

if not MEM0_API_KEY:
    print("ERROR: MEM0_API_KEY environment variable is not set", file=sys.stderr)
    sys.exit(1)
if not ZEALT_RUN_ID:
    print("ERROR: ZEALT_RUN_ID environment variable is not set", file=sys.stderr)
    sys.exit(1)

RUN_ID_SUFFIX = ZEALT_RUN_ID  # e.g. "zr-94tp4gv"

# ---------------------------------------------------------------------------
# Derived identifiers (scoped to this run)
# ---------------------------------------------------------------------------
ALICE_USER_ID = f"alice-{RUN_ID_SUFFIX}"
BOB_USER_ID = f"bob-{RUN_ID_SUFFIX}"
AGENT_ID = f"travel-agent-{RUN_ID_SUFFIX}"
APP_ID = f"concierge-{RUN_ID_SUFFIX}"
RUN_ID = f"trip-{RUN_ID_SUFFIX}"

OUTPUT_DIR = "/home/user/mem0-task"

# ---------------------------------------------------------------------------
# Conversation data (verbatim per requirements)
# ---------------------------------------------------------------------------
ALICE_MESSAGES = [
    {"role": "user", "content": "I am vegetarian and I love boutique hotels in Lisbon."},
    {"role": "assistant", "content": "Noted. I'll save your dietary preference and Lisbon hotel taste."},
    {"role": "user", "content": "Also, I always book aisle seats on flights."},
]

BOB_MESSAGES = [
    {"role": "user", "content": "I'm allergic to shellfish and I prefer ski resorts in Hokkaido."},
    {"role": "assistant", "content": "Got it. Logged your shellfish allergy and Hokkaido ski preference."},
    {"role": "user", "content": "I always want a window seat on flights."},
]

# ---------------------------------------------------------------------------
# Shared entity kwargs for add calls
# ---------------------------------------------------------------------------
ENTITY_KWARGS = {
    "agent_id": AGENT_ID,
    "app_id": APP_ID,
    "run_id": RUN_ID,
}


def add_memories(client, user_id, messages):
    """Add a multi-turn conversation for a given user_id."""
    print(f"[ADD] Ingesting {len(messages)} messages for user_id={user_id}")
    result = client.add(messages, user_id=user_id, **ENTITY_KWARGS)
    print(f"[ADD] Response: {json.dumps(result, indent=2)}")
    return result


def build_filter(user_id):
    """Build a v2 compound AND filter for the given user_id across all entity scopes."""
    return {
        "AND": [
            {"user_id": user_id},
            {"agent_id": AGENT_ID},
            {"app_id": APP_ID},
            {"run_id": RUN_ID},
        ]
    }


def search_memories(client, user_id):
    """Search memories with v2 compound filter for a specific user."""
    filters = build_filter(user_id)
    query = "What are this traveler's flight, food, and lodging preferences?"
    print(f"[SEARCH] Querying for user_id={user_id}")
    print(f"[SEARCH] Filters: {json.dumps(filters, indent=2)}")
    result = client.search(query, filters=filters, top_k=20, threshold=0.0)
    print(f"[SEARCH] Raw result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
    return result


def normalize_results(search_result):
    """Normalize search result to a list of memory dicts."""
    if isinstance(search_result, list):
        return search_result
    if isinstance(search_result, dict):
        return search_result.get("results", [])
    return []


def write_artifact(user_id, agent_id, app_id, run_id, results, filepath):
    """Write the JSON artifact for a traveler."""
    artifact = {
        "user_id": user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": run_id,
        "results": results,
    }
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(artifact, f, indent=2)
    print(f"[ARTIFACT] Written {len(results)} results to {filepath}")


def wait_for_memories(client, user_id, expected_keywords, max_wait=60, poll_interval=3):
    """
    Poll search until we find at least one memory containing each expected keyword,
    or until max_wait seconds elapse.
    """
    filters = build_filter(user_id)
    query = "What are this traveler's flight, food, and lodging preferences?"
    start = time.time()
    while time.time() - start < max_wait:
        result = client.search(query, filters=filters, top_k=20, threshold=0.0)
        memories = normalize_results(result)
        found_all = True
        for kw in expected_keywords:
            if not any(kw.lower() in m.get("memory", "").lower() for m in memories):
                found_all = False
                break
        if found_all and len(memories) > 0:
            print(f"[WAIT] All expected keywords {expected_keywords} found after {time.time() - start:.1f}s")
            return memories
        print(f"[WAIT] Waiting for memories (found {len(memories)} so far)...")
        time.sleep(poll_interval)
    # Last attempt
    result = client.search(query, filters=filters, top_k=20, threshold=0.0)
    memories = normalize_results(result)
    print(f"[WAIT] Timeout reached. Returning {len(memories)} memories.")
    return memories


def main():
    client = MemoryClient(api_key=MEM0_API_KEY)

    # -----------------------------------------------------------------------
    # Step 1: Ingest conversations
    # -----------------------------------------------------------------------
    print("=" * 60)
    print("STEP 1: Ingesting memories for both travelers")
    print("=" * 60)

    add_memories(client, ALICE_USER_ID, ALICE_MESSAGES)
    add_memories(client, BOB_USER_ID, BOB_MESSAGES)

    # -----------------------------------------------------------------------
    # Step 2: Wait for async memory extraction and search
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 2: Waiting for memory extraction, then searching")
    print("=" * 60)

    alice_expected = ["vegetarian"]
    bob_expected = ["shellfish"]

    alice_memories = wait_for_memories(client, ALICE_USER_ID, alice_expected)
    bob_memories = wait_for_memories(client, BOB_USER_ID, bob_expected)

    # -----------------------------------------------------------------------
    # Step 3: Write artifacts
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 3: Writing artifacts")
    print("=" * 60)

    write_artifact(
        ALICE_USER_ID, AGENT_ID, APP_ID, RUN_ID,
        alice_memories,
        os.path.join(OUTPUT_DIR, "alice_memories.json"),
    )
    write_artifact(
        BOB_USER_ID, AGENT_ID, APP_ID, RUN_ID,
        bob_memories,
        os.path.join(OUTPUT_DIR, "bob_memories.json"),
    )

    # -----------------------------------------------------------------------
    # Step 4: Final log line
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 4: Final summary")
    print("=" * 60)

    alice_count = len(alice_memories)
    bob_count = len(bob_memories)

    log_line = (
        f"RUN_ID: {ZEALT_RUN_ID}  "
        f"TRAVELER_A_MEMORIES: {alice_count}  "
        f"TRAVELER_B_MEMORIES: {bob_count}"
    )
    print(log_line)

    # Also verify isolation
    alice_has_shellfish = any("shellfish" in m.get("memory", "").lower() for m in alice_memories)
    bob_has_vegetarian = any("vegetarian" in m.get("memory", "").lower() for m in bob_memories)
    print(f"[ISOLATION] Alice has shellfish: {alice_has_shellfish} (expected False)")
    print(f"[ISOLATION] Bob has vegetarian: {bob_has_vegetarian} (expected False)")

    if alice_count < 1 or bob_count < 1:
        print("ERROR: One or both travelers returned zero memories!", file=sys.stderr)
        sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
