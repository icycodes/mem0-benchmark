import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from mem0 import AsyncMemoryClient


OUTPUT_DIR = Path("/home/user/mem0-async-task")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def extract_text(memory: Dict[str, Any]) -> str:
    for key in ("memory", "text", "content"):
        value = memory.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def normalize_memories(response: Any) -> List[Dict[str, Any]]:
    if isinstance(response, dict) and "results" in response:
        results = response.get("results")
        if isinstance(results, list):
            return results
    if isinstance(response, list):
        return response
    return []


def find_memory_id(memories: List[Dict[str, Any]], keyword: str) -> str:
    keyword_lower = keyword.lower()
    for memory in memories:
        text = extract_text(memory).lower()
        if keyword_lower in text:
            memory_id = memory.get("id") or memory.get("memory_id")
            if memory_id:
                return str(memory_id)
    return ""


async def wait_for_memories(
    client: AsyncMemoryClient,
    filters: Dict[str, Any],
    expected_min: int,
    attempts: int = 20,
    delay: float = 2.5,
) -> List[Dict[str, Any]]:
    memories: List[Dict[str, Any]] = []
    for attempt in range(attempts):
        response = await client.get_all(filters=filters)
        memories = normalize_memories(response)
        if len(memories) >= expected_min:
            return memories
        if attempt < attempts - 1:
            await asyncio.sleep(delay)
    return memories


async def wait_for_history(
    client: AsyncMemoryClient,
    memory_id: str,
    expected_min: int = 2,
    attempts: int = 25,
    delay: float = 3.0,
) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    for attempt in range(attempts):
        response = await client.history(memory_id=memory_id)
        if isinstance(response, list):
            history = response
        else:
            history = []
        has_update = any(
            isinstance(event, dict)
            and "UPDATE" in str(event.get("event", "")).upper()
            for event in history
        )
        if len(history) >= expected_min and has_update:
            return history
        if attempt < attempts - 1:
            await asyncio.sleep(delay)
    return history


async def main() -> None:
    api_key = require_env("MEM0_API_KEY")
    run_id = require_env("ZEALT_RUN_ID")

    suffix = run_id
    user_id = f"athlete-{suffix}"
    agent_id = f"coach-{suffix}"
    app_id = f"fitness-app-{suffix}"
    run_scope = f"session-{suffix}"

    client = AsyncMemoryClient(api_key=api_key)

    messages = [
        [{"role": "user", "content": "I run 5 kilometers every Tuesday morning."}],
        [
            {
                "role": "user",
                "content": "I do strength training with kettlebells on Thursdays.",
            }
        ],
        [
            {
                "role": "user",
                "content": "I prefer plant-based protein shakes after workouts.",
            }
        ],
        [{"role": "user", "content": "My resting heart rate is around 58 bpm."}],
    ]

    entity_filters = {
        "user_id": user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": run_scope,
    }

    add_tasks = [
        client.add(
            messages=message,
            filters=entity_filters,
        )
        for message in messages
    ]
    await asyncio.gather(*add_tasks)

    filters = {
        "AND": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": run_scope},
        ]
    }

    memories = await wait_for_memories(client, filters, expected_min=4)
    if len(memories) < 4:
        raise RuntimeError(
            f"Expected at least 4 memories but found {len(memories)} after retrying."
        )

    all_memories_payload = {
        "user_id": user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": run_scope,
        "memories": memories,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "all_memories.json").write_text(
        json.dumps(all_memories_payload, indent=2), encoding="utf-8"
    )

    barbell_id = find_memory_id(memories, "kettlebells")
    nutrition_id = find_memory_id(memories, "plant-based")
    heart_id = find_memory_id(memories, "heart rate")

    if not barbell_id or not nutrition_id or not heart_id:
        raise RuntimeError(
            "Failed to locate all required memory IDs from retrieved memories."
        )

    batch_update_payload = [
        {"memory_id": barbell_id, "text": "Strength training with dumbbells on Thursdays"},
        {"memory_id": nutrition_id, "text": "Prefers whey protein shakes after workouts"},
    ]
    batch_update_response = await client.batch_update(memories=batch_update_payload)
    (OUTPUT_DIR / "batch_update_response.json").write_text(
        json.dumps(batch_update_response, indent=2), encoding="utf-8"
    )

    await asyncio.sleep(3)
    history_response = await wait_for_history(client, barbell_id)
    if len(history_response) < 2:
        raise RuntimeError(
            f"Expected at least 2 history events for {barbell_id} but got {len(history_response)}."
        )

    history_payload = {
        "memory_id": barbell_id,
        "updated_text": "Strength training with dumbbells on Thursdays",
        "history": history_response,
    }
    (OUTPUT_DIR / "barbell_history.json").write_text(
        json.dumps(history_payload, indent=2), encoding="utf-8"
    )

    batch_delete_payload = [{"memory_id": heart_id}]
    batch_delete_response = await client.batch_delete(memories=batch_delete_payload)
    (OUTPUT_DIR / "batch_delete_response.json").write_text(
        json.dumps(batch_delete_response, indent=2), encoding="utf-8"
    )

    total_memories = len(memories)
    batch_update_count = len(batch_update_payload)
    batch_delete_count = len(batch_delete_payload)
    history_count = len(history_response) if isinstance(history_response, list) else 0

    print(f"RUN_ID: {run_id}")
    print(f"TOTAL_MEMORIES: {total_memories}")
    print(f"BARBELL_ID: {barbell_id}")
    print(f"NUTRITION_ID: {nutrition_id}")
    print(f"HEART_ID: {heart_id}")
    print(f"BATCH_UPDATE_COUNT: {batch_update_count}")
    print(f"BATCH_DELETE_COUNT: {batch_delete_count}")
    print(f"HISTORY_EVENTS: {history_count}")


if __name__ == "__main__":
    asyncio.run(main())
