#!/usr/bin/env python3
"""Ingest a deterministic conversation into Mem0 and submit memory feedback.

This script intentionally uses the real Mem0 Platform SDK. It requires:
  * MEM0_API_KEY: Mem0 Platform API key used by MemoryClient
  * ZEALT_RUN_ID: unique run id used to scope the Mem0 user

It writes one audit line per feedback submission to feedback.log.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from mem0 import MemoryClient

PROJECT_DIR = Path(__file__).resolve().parent
LOG_PATH = PROJECT_DIR / "feedback.log"
FEEDBACK_TYPES = ("POSITIVE", "NEGATIVE", "VERY_NEGATIVE")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

CONVERSATION = [
    {
        "role": "user",
        "content": "My name is Robin and I'm planning a trip to Kyoto next April.",
    },
    {
        "role": "assistant",
        "content": "Lovely! I'll keep that in mind for your itinerary.",
    },
    {
        "role": "user",
        "content": "I'm vegetarian, so please remember to flag vegetarian restaurants.",
    },
    {
        "role": "assistant",
        "content": "Got it, I'll only recommend vegetarian-friendly places.",
    },
    {
        "role": "user",
        "content": "Also, I tend to wake up early and prefer morning activities.",
    },
]


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def extract_memory_records(response: Any) -> list[dict[str, Any]]:
    """Return memory dicts from known Mem0 get_all response shapes."""
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]

    if not isinstance(response, dict):
        return []

    for key in ("results", "memories", "data"):
        value = response.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = extract_memory_records(value)
            if nested:
                return nested

    # Some envelopes nest the list under arbitrary metadata; inspect one level deep.
    for value in response.values():
        if isinstance(value, (dict, list)):
            nested = extract_memory_records(value)
            if nested:
                return nested

    return []


def memory_id(memory: dict[str, Any]) -> str | None:
    for key in ("id", "memory_id"):
        value = memory.get(key)
        if isinstance(value, str) and UUID_RE.fullmatch(value):
            return value
    return None


def unique_memory_ids(memories: Iterable[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for memory in memories:
        mid = memory_id(memory)
        if mid and mid not in seen:
            seen.add(mid)
            ids.append(mid)
    return ids


def get_all_for_user(client: MemoryClient, user_id: str) -> list[dict[str, Any]]:
    response = client.get_all(filters={"user_id": user_id}, version="v2")
    return extract_memory_records(response)


def wait_for_memories(
    client: MemoryClient,
    user_id: str,
    minimum_count: int = 3,
    timeout_seconds: int = 180,
) -> list[str]:
    """Poll Mem0 until asynchronous extraction exposes enough memory IDs."""
    deadline = time.monotonic() + timeout_seconds
    last_ids: list[str] = []
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        ids = unique_memory_ids(get_all_for_user(client, user_id))
        if ids:
            last_ids = ids
        if len(ids) >= minimum_count:
            return ids
        sleep_for = min(2 + attempt, 10)
        time.sleep(sleep_for)

    if last_ids:
        return last_ids
    raise RuntimeError(f"No memories became available for user_id={user_id!r}")


def feedback_id(response: dict[str, Any]) -> str:
    value = response.get("id") or response.get("feedback_id")
    if not isinstance(value, str) or not UUID_RE.fullmatch(value):
        raise RuntimeError(f"Mem0 feedback response did not include a UUID id: {response!r}")
    return value


def main() -> int:
    require_env("MEM0_API_KEY")
    run_id = require_env("ZEALT_RUN_ID")
    user_id = f"feedback-user-{run_id}"

    client = MemoryClient()

    client.add(CONVERSATION, user_id=user_id)
    memory_ids = wait_for_memories(client, user_id, minimum_count=3)

    log_lines: list[str] = []
    for index, mid in enumerate(memory_ids):
        feedback = FEEDBACK_TYPES[index % len(FEEDBACK_TYPES)]
        reason = (
            f"Audit feedback for {user_id}: cycle index {index + 1} marked {feedback}."
        )
        response = client.feedback(
            memory_id=mid,
            feedback=feedback,
            feedback_reason=reason,
        )
        fid = feedback_id(response)
        log_lines.append(f"memory_id={mid} feedback={feedback} feedback_id={fid}")

    LOG_PATH.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(log_lines)} feedback records to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - emit a concise CLI failure message
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
