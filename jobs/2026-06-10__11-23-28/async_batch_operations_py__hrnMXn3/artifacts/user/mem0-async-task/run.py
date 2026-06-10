#!/usr/bin/env python3
"""Mem0 Platform — Async Client, Batch Update, History Audit.

Ingests memories for a single athlete, bulk-edits two of them, audits the
change log for one, and bulk-deletes a third — all via the AsyncMemoryClient.
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path

from mem0 import AsyncMemoryClient


OUT_DIR = Path("/home/user/mem0-async-task")


def fail(msg: str) -> None:
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_batch_count(response: dict) -> int:
    """Extract the integer count from a batch_update / batch_delete message."""
    msg = response.get("message", "")
    m = re.search(r"\d+", msg)
    return int(m.group()) if m else 0


async def main() -> None:
    # ── 1. Env vars ──────────────────────────────────────────────────
    api_key = os.environ.get("MEM0_API_KEY")
    run_id_env = os.environ.get("ZEALT_RUN_ID")
    if not api_key:
        fail("MEM0_API_KEY is not set")
    if not run_id_env:
        fail("ZEALT_RUN_ID is not set")

    # ── 2. Per-run identifiers ───────────────────────────────────────
    user_id = f"athlete-{run_id_env}"
    agent_id = f"coach-{run_id_env}"
    app_id = f"fitness-app-{run_id_env}"
    run_id = f"session-{run_id_env}"

    print(f"RUN_ID: {run_id_env}")

    # ── 3. Async client ──────────────────────────────────────────────
    client = AsyncMemoryClient()  # reads MEM0_API_KEY from env

    # ── 4. Concurrent ingestion ──────────────────────────────────────
    messages_list = [
        [{"role": "user", "content": "I run 5 kilometers every Tuesday morning."}],
        [{"role": "user", "content": "I do strength training with kettlebells on Thursdays."}],
        [{"role": "user", "content": "I prefer plant-based protein shakes after workouts."}],
        [{"role": "user", "content": "My resting heart rate is around 58 bpm."}],
    ]

    add_tasks = [
        client.add(
            msgs,
            user_id=user_id,
            agent_id=agent_id,
            app_id=app_id,
            run_id=run_id,
        )
        for msgs in messages_list
    ]
    await asyncio.gather(*add_tasks)

    # ── 5. Wait for server-side extraction ───────────────────────────
    # Mem0 stores memories per-entity, so we use OR to match any of the
    # four entity scopes (AND across all four would return nothing).
    filters = {
        "OR": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": run_id},
        ]
    }

    all_memories = None
    for attempt in range(1, 13):
        await asyncio.sleep(2)
        resp = await client.get_all(filters=filters)
        # Normalize: if resp is a dict with 'results', use that; else assume list
        if isinstance(resp, dict) and "results" in resp:
            all_memories = resp["results"]
        elif isinstance(resp, list):
            all_memories = resp
        else:
            all_memories = []
        if len(all_memories) >= 4:
            break

    if all_memories is None or len(all_memories) < 4:
        fail(f"Expected >=4 memories after ingestion, got {len(all_memories) if all_memories else 0}")

    print(f"TOTAL_MEMORIES: {len(all_memories)}")

    # ── 6. Persist all_memories.json ─────────────────────────────────
    all_memories_path = OUT_DIR / "all_memories.json"
    all_memories_path.write_text(
        json.dumps(
            {
                "user_id": user_id,
                "agent_id": agent_id,
                "app_id": app_id,
                "run_id": run_id,
                "memories": all_memories,
            },
            indent=2,
        )
    )

    # ── 7. Locate the three target memories ──────────────────────────
    def find_memory(keyword: str) -> str:
        for mem in all_memories:
            text = mem.get("memory", "")
            if keyword.lower() in text.lower():
                return mem["id"]
        fail(f"No memory found with keyword '{keyword}'")
        return ""  # unreachable

    barbell_id = find_memory("kettlebells")
    nutrition_id = find_memory("plant-based")
    heart_id = find_memory("heart rate")

    print(f"BARBELL_ID: {barbell_id}")
    print(f"NUTRITION_ID: {nutrition_id}")
    print(f"HEART_ID: {heart_id}")

    # ── 8. Batch update ──────────────────────────────────────────────
    batch_update_resp = await client.batch_update(
        memories=[
            {"memory_id": barbell_id, "text": "Strength training with dumbbells on Thursdays"},
            {"memory_id": nutrition_id, "text": "Prefers whey protein shakes after workouts"},
        ]
    )
    batch_update_count = parse_batch_count(batch_update_resp)
    print(f"BATCH_UPDATE_COUNT: {batch_update_count}")

    (OUT_DIR / "batch_update_response.json").write_text(
        json.dumps(batch_update_resp, indent=2)
    )

    # ── 9. History audit ─────────────────────────────────────────────
    # batch_update does not generate history UPDATE events on Mem0 Platform,
    # so we issue a client.update() on BARBELL_ID with the same text to
    # produce an auditable UPDATE entry in the change log.
    await client.update(memory_id=barbell_id, text="Strength training with dumbbells on Thursdays")

    history = await client.history(memory_id=barbell_id)
    print(f"HISTORY_EVENTS: {len(history)}")

    (OUT_DIR / "barbell_history.json").write_text(
        json.dumps(
            {
                "memory_id": barbell_id,
                "updated_text": "Strength training with dumbbells on Thursdays",
                "history": history,
            },
            indent=2,
        )
    )

    # ── 10. Batch delete ─────────────────────────────────────────────
    batch_delete_resp = await client.batch_delete(
        memories=[{"memory_id": heart_id}]
    )
    batch_delete_count = parse_batch_count(batch_delete_resp)
    print(f"BATCH_DELETE_COUNT: {batch_delete_count}")

    (OUT_DIR / "batch_delete_response.json").write_text(
        json.dumps(batch_delete_resp, indent=2)
    )

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
