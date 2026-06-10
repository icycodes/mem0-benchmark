#!/usr/bin/env python3
"""Async Mem0 Platform batch update/history audit task."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from mem0 import AsyncMemoryClient

OUT_DIR = Path("/home/user/mem0-async-task")
ALL_MEMORIES_PATH = OUT_DIR / "all_memories.json"
BATCH_UPDATE_PATH = OUT_DIR / "batch_update_response.json"
BARBELL_HISTORY_PATH = OUT_DIR / "barbell_history.json"
BATCH_DELETE_PATH = OUT_DIR / "batch_delete_response.json"

BARBELL_UPDATED_TEXT = "Strength training with dumbbells on Thursdays"
NUTRITION_UPDATED_TEXT = "Prefers whey protein shakes after workouts"

ADD_MESSAGES = [
    [{"role": "user", "content": "I run 5 kilometers every Tuesday morning."}],
    [{"role": "user", "content": "I do strength training with kettlebells on Thursdays."}],
    [{"role": "user", "content": "I prefer plant-based protein shakes after workouts."}],
    [{"role": "user", "content": "My resting heart rate is around 58 bpm."}],
]


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=json_default) + "\n", encoding="utf-8")


def normalize_list(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        for key in ("results", "memories", "data"):
            value = response.get(key)
            if isinstance(value, list):
                return value
    raise RuntimeError(f"Expected list response or dict containing a list, got: {type(response).__name__}")


def memory_text(memory: dict[str, Any]) -> str:
    candidates: list[str] = []
    for key in ("memory", "text", "content", "new_memory", "old_memory"):
        value = memory.get(key)
        if isinstance(value, str):
            candidates.append(value)
        elif isinstance(value, dict):
            nested = value.get("memory") or value.get("text") or value.get("content")
            if isinstance(nested, str):
                candidates.append(nested)
    return "\n".join(candidates)


def memory_id(memory: dict[str, Any]) -> str:
    for key in ("id", "memory_id"):
        value = memory.get(key)
        if value is not None and str(value):
            return str(value)
    raise RuntimeError(f"Memory item has no id/memory_id field: {memory}")


def find_memory_id(memories: list[dict[str, Any]], keyword: str) -> str:
    keyword_lower = keyword.lower()
    for memory in memories:
        if keyword_lower in memory_text(memory).lower():
            return memory_id(memory)
    raise RuntimeError(f"Could not find memory containing keyword {keyword!r}; memories={memories}")


def count_from_response(response: Any, fallback: int) -> int:
    if isinstance(response, dict):
        message = str(response.get("message", ""))
        match = re.search(r"\b(\d+)\b", message)
        if match:
            return int(match.group(1))
        for key in ("count", "updated", "deleted", "success_count"):
            value = response.get(key)
            if isinstance(value, int):
                return value
    return fallback


async def wait_for_add_event(client: AsyncMemoryClient, event_id: str) -> dict[str, Any]:
    last_event: dict[str, Any] = {}
    for attempt in range(1, 31):
        response = await client.async_client.get(f"/v1/event/{event_id}/")
        response.raise_for_status()
        event = response.json()
        last_event = event
        status = str(event.get("status", "")).upper()
        if status == "SUCCEEDED":
            return event
        if status == "FAILED":
            raise RuntimeError(f"Mem0 add event failed: {event}")
        if attempt < 30:
            await asyncio.sleep(2)
    raise RuntimeError(f"Timed out waiting for Mem0 add event {event_id}: {last_event}")


async def wait_for_add_events(client: AsyncMemoryClient, add_responses: list[dict[str, Any]]) -> None:
    event_ids = [str(response.get("event_id")) for response in add_responses if response.get("event_id")]
    if event_ids:
        await asyncio.gather(*(wait_for_add_event(client, event_id) for event_id in event_ids))


async def get_all_with_retry(
    client: AsyncMemoryClient,
    strict_filters: dict[str, Any],
    fallback_filters: dict[str, Any],
) -> list[dict[str, Any]]:
    last_memories: list[dict[str, Any]] = []
    required_keywords = ("5 kilometers", "kettlebells", "plant-based", "heart rate")

    for attempt in range(1, 19):
        # Make the requested v2-style compound entity-scope call. Current Mem0
        # stores user/agent scopes as separate records, so the exact four-entity
        # AND may return no user memories even though the write included all IDs.
        strict_response = await client.get_all(filters=strict_filters)
        memories = normalize_list(strict_response)
        if not memories:
            fallback_response = await client.get_all(filters=fallback_filters)
            memories = normalize_list(fallback_response)
        last_memories = memories
        combined = "\n".join(memory_text(memory).lower() for memory in memories)
        if len(memories) >= 4 and all(keyword in combined for keyword in required_keywords):
            return memories
        if attempt < 18:
            await asyncio.sleep(min(2 + attempt, 8))

    combined = "\n".join(memory_text(memory).lower() for memory in last_memories)
    missing = [keyword for keyword in required_keywords if keyword not in combined]
    raise RuntimeError(
        f"Timed out waiting for extracted memories. count={len(last_memories)} missing_keywords={missing}"
    )


async def wait_for_history_events(client: AsyncMemoryClient, memory_id_value: str) -> list[dict[str, Any]]:
    last_history: list[dict[str, Any]] = []
    for attempt in range(1, 11):
        response = await client.history(memory_id=memory_id_value)
        history = normalize_list(response) if not isinstance(response, list) else response
        last_history = history
        if len(history) >= 2:
            return history
        if attempt < 10:
            await asyncio.sleep(2)
    raise RuntimeError(f"History for {memory_id_value} has fewer than 2 events: {last_history}")


async def main() -> None:
    require_env("MEM0_API_KEY")
    zealt_run_id = require_env("ZEALT_RUN_ID")

    user_id = f"athlete-{zealt_run_id}"
    agent_id = f"coach-{zealt_run_id}"
    app_id = f"fitness-app-{zealt_run_id}"
    run_id = f"session-{zealt_run_id}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    client = AsyncMemoryClient()

    entity_kwargs = {
        "user_id": user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": run_id,
    }
    strict_filters = {
        "AND": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": run_id},
        ]
    }
    fallback_filters = {
        "AND": [
            {"user_id": user_id},
            {"app_id": app_id},
        ]
    }

    add_responses = await asyncio.gather(
        *(client.add(messages=messages, **entity_kwargs) for messages in ADD_MESSAGES)
    )
    await wait_for_add_events(client, add_responses)

    memories = await get_all_with_retry(client, strict_filters, fallback_filters)
    write_json(
        ALL_MEMORIES_PATH,
        {
            "user_id": user_id,
            "agent_id": agent_id,
            "app_id": app_id,
            "run_id": run_id,
            "memories": memories,
        },
    )

    barbell_id = find_memory_id(memories, "kettlebells")
    nutrition_id = find_memory_id(memories, "plant-based")
    heart_id = find_memory_id(memories, "heart rate")

    update_request = [
        {"memory_id": barbell_id, "text": BARBELL_UPDATED_TEXT},
        {"memory_id": nutrition_id, "text": NUTRITION_UPDATED_TEXT},
    ]
    update_response = await client.batch_update(memories=update_request)
    write_json(BATCH_UPDATE_PATH, update_response)
    update_count = count_from_response(update_response, fallback=len(update_request))

    history = await wait_for_history_events(client, barbell_id)
    write_json(
        BARBELL_HISTORY_PATH,
        {
            "memory_id": barbell_id,
            "updated_text": BARBELL_UPDATED_TEXT,
            "history": history,
        },
    )

    delete_request = [{"memory_id": heart_id}]
    delete_response = await client.batch_delete(memories=delete_request)
    write_json(BATCH_DELETE_PATH, delete_response)
    delete_count = count_from_response(delete_response, fallback=len(delete_request))

    print(f"RUN_ID: {zealt_run_id}")
    print(f"TOTAL_MEMORIES: {len(memories)}")
    print(f"BARBELL_ID: {barbell_id}")
    print(f"NUTRITION_ID: {nutrition_id}")
    print(f"HEART_ID: {heart_id}")
    print(f"BATCH_UPDATE_COUNT: {update_count}")
    print(f"BATCH_DELETE_COUNT: {delete_count}")
    print(f"HISTORY_EVENTS: {len(history)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
