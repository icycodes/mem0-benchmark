import json
import os
import sys
import time
from typing import Any, Dict, List, Optional


def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _import_client():
    try:
        from mem0 import MemoryClient  # type: ignore

        return MemoryClient
    except ImportError:
        from mem0ai import MemoryClient  # type: ignore

        return MemoryClient


def _extract_memory_text(result: Dict[str, Any]) -> str:
    for key in ("memory", "text", "memory_text", "content"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _pick_target(results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    role_keywords = {"engineer", "junior", "developer", "role"}
    add_results = [item for item in results if item.get("event") == "ADD"]
    candidates = add_results if add_results else results
    for item in candidates:
        memory_text = _extract_memory_text(item).lower()
        if memory_text and any(keyword in memory_text for keyword in role_keywords):
            return item
    return candidates[0] if candidates else None


def main() -> None:
    api_key = _get_env("MEM0_API_KEY")
    run_id = _get_env("ZEALT_RUN_ID")
    user_id = f"harbor-history-{run_id}"

    MemoryClient = _import_client()
    client = MemoryClient(api_key=api_key)

    messages = [
        {
            "role": "user",
            "content": "I'm Jordan, a junior engineer at Harbor Labs working on internal tooling.",
        },
        {
            "role": "assistant",
            "content": "Thanks Jordan! What projects are you focused on right now?",
        },
        {
            "role": "user",
            "content": "Mostly automation scripts for CI and a dashboard for operations.",
        },
    ]

    add_response = client.add(messages, user_id=user_id, filters={"user_id": user_id})
    add_results: List[Dict[str, Any]] = []
    if isinstance(add_response, list):
        add_results = add_response
    elif isinstance(add_response, dict) and isinstance(add_response.get("results"), list):
        add_results = add_response["results"]
    elif hasattr(add_response, "results") and isinstance(add_response.results, list):
        add_results = add_response.results
    elif hasattr(add_response, "data") and isinstance(add_response.data, list):
        add_results = add_response.data

    target = _pick_target(add_results)

    if not target:
        memory_id = None
        for _ in range(10):
            all_memories = client.get_all(filters={"user_id": user_id})
            results = all_memories.get("results") if isinstance(all_memories, dict) else None
            if isinstance(results, list):
                target = _pick_target(results)
                if target:
                    memory_id = target.get("id")
                    if memory_id:
                        break
            time.sleep(1)
        if not memory_id:
            raise RuntimeError("No ADD memory result available for update")
    else:
        memory_id = target.get("id")

    if not memory_id:
        raise RuntimeError("Selected memory result missing id")

    updated_text = (
        "Jordan is now a senior engineer at Harbor Labs, leading internal tooling efforts."
    )
    updated_metadata = {
        "role": "senior engineer",
        "company": "Harbor Labs",
        "focus": "internal tooling",
    }

    client.update(memory_id=memory_id, text=updated_text, metadata=updated_metadata)

    history = client.history(memory_id)
    if not isinstance(history, list):
        raise RuntimeError("Expected history() to return a list of events")

    output_path = "/home/user/myproject/output.log"
    events_json = json.dumps(history, ensure_ascii=False)

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(f"User ID: {user_id}\n")
        handle.write(f"Memory ID: {memory_id}\n")
        handle.write(f"Events JSON: {events_json}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
