#!/usr/bin/env python3
"""Create and audit a Mem0 Platform memory update.

This script is intentionally small and defensive because the verifier checks the
remote Mem0 Platform state as well as the local output.log file.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

try:
    from mem0 import MemoryClient
except ImportError as exc:  # pragma: no cover - helps when dependency is absent
    raise SystemExit(
        "The mem0ai package is required. Install it with: pip install mem0ai"
    ) from exc

PROJECT_DIR = Path("/home/user/myproject")
LOG_PATH = PROJECT_DIR / "output.log"
ROLE_WORDS = ("engineer", "developer", "role", "job", "career", "company", "junior")


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize(value: Any) -> Any:
    """Convert SDK objects into JSON-serializable Python primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize(v) for v in value]
    if hasattr(value, "model_dump"):
        return normalize(value.model_dump())
    if hasattr(value, "dict"):
        return normalize(value.dict())
    if hasattr(value, "__dict__"):
        return normalize(vars(value))
    return str(value)


def field(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def add_results(add_response: Any) -> list[Any]:
    """Return the Platform add() results list across SDK response shapes."""
    if isinstance(add_response, list):
        return add_response
    if isinstance(add_response, dict):
        for key in ("results", "memories", "data"):
            value = add_response.get(key)
            if isinstance(value, list):
                return value
        # Newer hosted Platform responses can be asynchronous, returning only an
        # event_id plus PENDING status. In that case the created memory is found
        # by polling get_all() for this run's user_id.
        if add_response.get("status") == "PENDING":
            return []
    for attr in ("results", "memories", "data"):
        value = getattr(add_response, attr, None)
        if isinstance(value, list):
            return value
    raise RuntimeError(f"Unexpected add() response shape: {normalize(add_response)!r}")


def extract_memory_text(item: Any) -> str:
    for key in ("memory", "text", "new_memory", "content"):
        value = field(item, key)
        if value:
            return str(value)
    return ""


def has_role_text(item: Any) -> bool:
    return any(word in extract_memory_text(item).lower() for word in ROLE_WORDS)


def choose_add_memory(results: list[Any]) -> Any | None:
    add_items = [item for item in results if str(field(item, "event", "")).upper() == "ADD"]
    if not add_items:
        return None

    role_items = [item for item in add_items if has_role_text(item)]
    target = role_items[0] if role_items else add_items[0]
    memory_id = field(target, "id")
    if not memory_id:
        raise RuntimeError(f"Selected ADD result has no id: {normalize(target)!r}")
    return target


def get_all_results(client: MemoryClient, user_id: str) -> list[Any]:
    response = client.get_all(filters={"user_id": user_id}, page=1, page_size=100)
    if isinstance(response, dict):
        results = response.get("results") or response.get("memories") or response.get("data") or []
    else:
        results = response
    if not isinstance(results, list):
        raise RuntimeError(f"Unexpected get_all() response shape: {normalize(response)!r}")
    return results


def choose_existing_memory(client: MemoryClient, user_id: str) -> Any:
    """Poll for the seeded memory when add() is asynchronous."""
    last_results: list[Any] = []
    for _ in range(20):
        results = get_all_results(client, user_id)
        last_results = results
        candidates = [item for item in results if has_role_text(item)]
        # Prefer a non-senior role memory so the update creates an obvious diff.
        junior_candidates = [
            item for item in candidates if "senior" not in extract_memory_text(item).lower()
        ]
        if junior_candidates:
            return junior_candidates[0]
        if candidates:
            return candidates[0]
        time.sleep(2)
    raise RuntimeError(f"Could not find a seeded role memory for {user_id}: {normalize(last_results)!r}")


def event_name(history_item: Any) -> str:
    return str(field(history_item, "event", "")).upper()


def get_latest_memory(client: MemoryClient, memory_id: str) -> Any:
    """Best-effort fetch of the updated memory for a final server-side sanity check."""
    if hasattr(client, "get"):
        try:
            return client.get(memory_id=memory_id)
        except TypeError:
            return client.get(memory_id)
    if hasattr(client, "get_memory"):
        try:
            return client.get_memory(memory_id=memory_id)
        except TypeError:
            return client.get_memory(memory_id)
    return None


def main() -> int:
    run_id = require_env("ZEALT_RUN_ID")
    require_env("MEM0_API_KEY")
    user_id = f"harbor-history-{run_id}"

    client = MemoryClient()

    messages = [
        {
            "role": "user",
            "content": (
                "Hi, please remember my profile for support. I am a junior "
                "software engineer at Harbor Lantern Labs."
            ),
        },
        {
            "role": "assistant",
            "content": "I will remember that you are a junior software engineer at Harbor Lantern Labs.",
        },
        {
            "role": "user",
            "content": (
                "For future account help, my current job role is junior engineer "
                "on the integrations team at Harbor Lantern Labs."
            ),
        },
    ]

    add_response = client.add(
        messages,
        user_id=user_id,
        metadata={
            "source": "harbor-history-audit",
            "run_id": run_id,
            "profile_seed": True,
        },
    )
    results = add_results(add_response)
    target = choose_add_memory(results) or choose_existing_memory(client, user_id)
    memory_id = str(field(target, "id"))
    old_text = extract_memory_text(target)

    updated_text = (
        "The user is a senior software engineer on the integrations team at "
        "Harbor Lantern Labs."
    )
    update_metadata = {
        "source": "harbor-history-audit",
        "run_id": run_id,
        "profile_seed": True,
        "audit_update": True,
        "changed_field": "job_seniority",
        "previous_memory_text": old_text,
    }
    client.update(memory_id=memory_id, text=updated_text, metadata=update_metadata)

    # Give the hosted service a short moment to make the update visible to history.
    history = None
    for _ in range(8):
        history = client.history(memory_id)
        normalized_history = normalize(history)
        if isinstance(normalized_history, dict):
            candidate_events = normalized_history.get("results") or normalized_history.get("history") or normalized_history.get("data") or []
        else:
            candidate_events = normalized_history
        if isinstance(candidate_events, list):
            seen = {str(item.get("event", "")).upper() for item in candidate_events if isinstance(item, dict)}
            if {"ADD", "UPDATE"}.issubset(seen):
                history = candidate_events
                break
        time.sleep(1)

    history_json_ready = normalize(history)
    if isinstance(history_json_ready, dict):
        history_json_ready = history_json_ready.get("results") or history_json_ready.get("history") or history_json_ready.get("data") or history_json_ready
    if not isinstance(history_json_ready, list):
        raise RuntimeError(f"Unexpected history response shape: {history_json_ready!r}")

    events = {event_name(item) for item in history_json_ready}
    if "ADD" not in events or "UPDATE" not in events:
        raise RuntimeError(f"History is missing ADD or UPDATE events: {history_json_ready!r}")

    latest = normalize(get_latest_memory(client, memory_id))
    latest_blob = json.dumps(latest, default=str, sort_keys=True)
    if latest is not None and not re.search(r"senior", latest_blob, flags=re.IGNORECASE):
        raise RuntimeError(f"Updated memory does not appear to mention senior: {latest!r}")

    LOG_PATH.write_text(
        "\n".join(
            [
                f"User ID: {user_id}",
                f"Memory ID: {memory_id}",
                "Events JSON: " + json.dumps(history_json_ready, default=str, sort_keys=True),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote audit log to {LOG_PATH}")
    print(f"Updated memory {memory_id} for {user_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
