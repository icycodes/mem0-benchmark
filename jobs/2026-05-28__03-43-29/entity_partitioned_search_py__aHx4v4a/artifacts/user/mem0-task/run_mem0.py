import json
import os
import sys
import time
from typing import Any, Dict, List

from mem0 import MemoryClient


def normalize_results(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, dict) and "results" in raw:
        return raw["results"]
    if isinstance(raw, list):
        return raw
    return []


def search_with_retry(client: MemoryClient, query: str, filters: Dict[str, Any], retries: int = 6, delay: float = 2.0) -> List[Dict[str, Any]]:
    last_results: List[Dict[str, Any]] = []
    for _ in range(retries):
        raw = client.search(query, version="v2", filters=filters, top_k=20)
        last_results = normalize_results(raw)
        if last_results:
            return last_results
        time.sleep(delay)
    return last_results


def main() -> None:
    api_key = os.getenv("MEM0_API_KEY")
    run_id = os.getenv("ZEALT_RUN_ID")
    if not api_key:
        raise RuntimeError("MEM0_API_KEY is required")
    if not run_id:
        raise RuntimeError("ZEALT_RUN_ID is required")

    run_suffix = run_id

    alice_user_id = f"alice-{run_suffix}"
    bob_user_id = f"bob-{run_suffix}"
    agent_id = f"travel-agent-{run_suffix}"
    app_id = f"concierge-{run_suffix}"
    scoped_run_id = f"trip-{run_suffix}"

    client = MemoryClient(api_key=api_key)

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

    client.add(
        alice_messages,
        user_id=alice_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=scoped_run_id,
    )

    client.add(
        bob_messages,
        user_id=bob_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=scoped_run_id,
    )

    query = "What are this traveler's flight, food, and lodging preferences?"

    alice_filters = {
        "AND": [
            {"user_id": alice_user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": scoped_run_id},
        ]
    }

    bob_filters = {
        "AND": [
            {"user_id": bob_user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": scoped_run_id},
        ]
    }

    alice_results = search_with_retry(client, query, alice_filters)
    bob_results = search_with_retry(client, query, bob_filters)

    alice_payload = {
        "user_id": alice_user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": scoped_run_id,
        "results": alice_results,
    }

    bob_payload = {
        "user_id": bob_user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": scoped_run_id,
        "results": bob_results,
    }

    base_dir = "/home/user/mem0-task"
    with open(os.path.join(base_dir, "alice_memories.json"), "w", encoding="utf-8") as handle:
        json.dump(alice_payload, handle, indent=2)
    with open(os.path.join(base_dir, "bob_memories.json"), "w", encoding="utf-8") as handle:
        json.dump(bob_payload, handle, indent=2)

    print(f"RUN_ID: {run_id}")
    print(f"TRAVELER_A_MEMORIES: {len(alice_results)}")
    print(f"TRAVELER_B_MEMORIES: {len(bob_results)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise
