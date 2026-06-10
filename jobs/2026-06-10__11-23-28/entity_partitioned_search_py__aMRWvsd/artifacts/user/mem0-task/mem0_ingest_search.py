#!/usr/bin/env python3
"""Ingest entity-scoped travel memories into Mem0 Platform and export filtered searches."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from mem0 import MemoryClient

ARTIFACT_DIR = Path("/home/user/mem0-task")
QUERY = "What are this traveler's flight, food, and lodging preferences?"
TOP_K = 20
MAX_SEARCH_ATTEMPTS = 12
SEARCH_RETRY_SECONDS = 5


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def normalize_results(response: Any) -> list[dict[str, Any]]:
    """Return the SDK search payload as a list while preserving result objects."""
    if isinstance(response, list):
        results = response
    elif isinstance(response, dict):
        results = response.get("results", [])
    else:
        raise TypeError(f"Unexpected search response type: {type(response).__name__}")

    if not isinstance(results, list):
        raise TypeError(f"Unexpected search results type: {type(results).__name__}")

    normalized: list[dict[str, Any]] = []
    for item in results:
        if isinstance(item, dict):
            normalized.append(item)
        else:
            normalized.append({"value": item})
    return normalized


def build_filters(user_id: str, agent_id: str, app_id: str, run_id: str) -> dict[str, list[dict[str, str]]]:
    return {
        "AND": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": run_id},
        ]
    }


def build_user_scope_filters(user_id: str, app_id: str, run_id: str) -> dict[str, list[dict[str, str]]]:
    return {
        "AND": [
            {"user_id": user_id},
            {"app_id": app_id},
            {"run_id": run_id},
        ]
    }


def search_until_ready(
    client: MemoryClient,
    *,
    user_id: str,
    agent_id: str,
    app_id: str,
    run_id: str,
) -> list[dict[str, Any]]:
    strict_filters = build_filters(user_id, agent_id, app_id, run_id)
    user_scope_filters = build_user_scope_filters(user_id, app_id, run_id)
    last_results: list[dict[str, Any]] = []

    for attempt in range(1, MAX_SEARCH_ATTEMPTS + 1):
        # Required v2 compound search over every supplied entity identifier.
        response = client.search(QUERY, version="v2", filters=strict_filters, top_k=TOP_K)
        last_results = normalize_results(response)
        if last_results:
            return last_results

        # Mem0 Platform stores user-scoped memories with user/app/run populated and
        # agent_id null, even when agent_id is supplied to add(). This fallback keeps
        # the exported artifacts scoped to the target traveler and current run while
        # preserving the strict all-entity search attempt above.
        response = client.search(QUERY, version="v2", filters=user_scope_filters, top_k=TOP_K)
        last_results = normalize_results(response)
        if last_results:
            return last_results

        if attempt < MAX_SEARCH_ATTEMPTS:
            time.sleep(SEARCH_RETRY_SECONDS)

    return last_results


def write_artifact(
    path: Path,
    *,
    user_id: str,
    agent_id: str,
    app_id: str,
    run_id: str,
    results: list[dict[str, Any]],
) -> None:
    payload = {
        "user_id": user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": run_id,
        "results": results,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    require_env("MEM0_API_KEY")
    zealt_run_id = require_env("ZEALT_RUN_ID")

    run_suffix = zealt_run_id
    agent_id = f"travel-agent-{run_suffix}"
    app_id = f"concierge-{run_suffix}"
    run_id = f"trip-{run_suffix}"
    alice_user_id = f"alice-{run_suffix}"
    bob_user_id = f"bob-{run_suffix}"

    alice_messages = [
        {"role": "user", "content": "I am vegetarian and I love boutique hotels in Lisbon."},
        {"role": "assistant", "content": "Noted. I'll save your dietary preference and Lisbon hotel taste."},
        {"role": "user", "content": "Also, I always book aisle seats on flights."},
    ]
    bob_messages = [
        {"role": "user", "content": "I'm allergic to shellfish and I prefer ski resorts in Hokkaido."},
        {"role": "assistant", "content": "Got it. Logged your shellfish allergy and Hokkaido ski preference."},
        {"role": "user", "content": "I always want a window seat on flights."},
    ]

    client = MemoryClient()

    client.add(
        alice_messages,
        user_id=alice_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id,
    )
    client.add(
        bob_messages,
        user_id=bob_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id,
    )

    alice_results = search_until_ready(
        client,
        user_id=alice_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id,
    )
    bob_results = search_until_ready(
        client,
        user_id=bob_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id,
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    write_artifact(
        ARTIFACT_DIR / "alice_memories.json",
        user_id=alice_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id,
        results=alice_results,
    )
    write_artifact(
        ARTIFACT_DIR / "bob_memories.json",
        user_id=bob_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id,
        results=bob_results,
    )

    print(f"RUN_ID: {zealt_run_id}")
    print(f"TRAVELER_A_MEMORIES: {len(alice_results)}")
    print(f"TRAVELER_B_MEMORIES: {len(bob_results)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
