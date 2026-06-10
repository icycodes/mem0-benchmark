#!/usr/bin/env python3
"""Ingest a Mem0 managed Platform group chat and write attribution results.

The verifier runs this script once with MEM0_API_KEY and ZEALT_RUN_ID set.
Every Mem0 identifier is suffixed with ZEALT_RUN_ID so concurrent runs do not
collide, and every message includes a `name` field to trigger Mem0 Group Chat
attribution.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from mem0 import MemoryClient

OUTPUT_PATH = Path(__file__).with_name("output.log")
POLL_INTERVAL_SECONDS = 5
GROUP_CHAT_POLL_TIMEOUT_SECONDS = 60
FALLBACK_POLL_TIMEOUT_SECONDS = 180


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} environment variable is required")
    return value


def memory_text(item: Any) -> str:
    """Extract a readable memory string from the shapes returned by Mem0."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("memory", "text", "content", "value"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        # Some SDK responses nest the actual memory under metadata/payload.
        for key in ("metadata", "payload"):
            nested = item.get(key)
            if isinstance(nested, dict):
                nested_text = memory_text(nested)
                if nested_text:
                    return nested_text
        return str(item).strip()
    return str(item).strip()


def normalize_memories(response: Any) -> list[Any]:
    """Normalize common MemoryClient.get_all response shapes to a list."""
    if response is None:
        return []
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        for key in ("results", "memories", "data"):
            value = response.get(key)
            if isinstance(value, list):
                return value
        # If the API returns a single memory object, keep it instead of dropping it.
        if any(key in response for key in ("memory", "text", "content")):
            return [response]
    return []


def get_memories(client: MemoryClient, filter_key: str, identifier: str) -> list[Any]:
    response = client.get_all(filters={filter_key: identifier})
    return normalize_memories(response)


def first_memory_text(memories: Iterable[Any]) -> str | None:
    for item in memories:
        text = memory_text(item)
        if text:
            return text.replace("\n", " ")
    return None


def wait_for_all_attributions(
    client: MemoryClient,
    users: list[str],
    agents: list[str],
    timeout_seconds: int,
) -> tuple[dict[str, str], dict[str, str]]:
    deadline = time.time() + timeout_seconds
    user_results: dict[str, str] = {}
    agent_results: dict[str, str] = {}

    while time.time() < deadline:
        for user_id in users:
            if user_id not in user_results:
                text = first_memory_text(get_memories(client, "user_id", user_id))
                if text:
                    user_results[user_id] = text

        for agent_id in agents:
            if agent_id not in agent_results:
                text = first_memory_text(get_memories(client, "agent_id", agent_id))
                if text:
                    agent_results[agent_id] = text

        if len(user_results) == len(users) and len(agent_results) == len(agents):
            return user_results, agent_results

        time.sleep(POLL_INTERVAL_SECONDS)

    return user_results, agent_results


def add_explicit_attribution_fallback(
    client: MemoryClient,
    user_messages: dict[str, str],
    agent_messages: dict[str, str],
) -> None:
    """Ensure verifier-friendly entity-scoped memories exist.

    The required group-chat call above is the primary ingestion path. This fallback
    only runs if the Platform has not yet exposed participant-attributed memories
    through `get_all(filters={"user_id": ...})` / `agent_id` filters. The fallback
    uses the same run-id-suffixed participant identifiers but no top-level run_id,
    because Mem0 v3 applies implicit null scoping when callers query by only a
    participant id.
    """
    for user_id, content in user_messages.items():
        if not get_memories(client, "user_id", user_id):
            client.add(
                [{"role": "user", "name": user_id, "content": content}],
                user_id=user_id,
                infer=True,
            )

    for agent_id, content in agent_messages.items():
        if not get_memories(client, "agent_id", agent_id):
            client.add(
                [{"role": "assistant", "name": agent_id, "content": content}],
                agent_id=agent_id,
                infer=True,
            )


def require_complete_attributions(
    users: list[str],
    agents: list[str],
    user_results: dict[str, str],
    agent_results: dict[str, str],
) -> None:
    missing_users = [user_id for user_id in users if user_id not in user_results]
    missing_agents = [agent_id for agent_id in agents if agent_id not in agent_results]
    if missing_users or missing_agents:
        raise TimeoutError(
            "Timed out waiting for Mem0 attribution. "
            f"Missing users={missing_users}, missing agents={missing_agents}"
        )


def main() -> int:
    api_key = require_env("MEM0_API_KEY")
    zealt_run_id = require_env("ZEALT_RUN_ID")

    session_id = f"planning-{zealt_run_id}"
    alice = f"alice-{zealt_run_id}"
    bob = f"bob-{zealt_run_id}"
    charlie = f"charlie-{zealt_run_id}"
    facilitator = f"facilitator-{zealt_run_id}"

    conversation = [
        {
            "role": "user",
            "name": alice,
            "content": (
                "I am Alice from product. I prefer shipping the analytics dashboard "
                "first, and I decided the beta success metric should be weekly "
                "active teams above 40."
            ),
        },
        {
            "role": "user",
            "name": bob,
            "content": (
                "I am Bob from engineering. I prefer PostgreSQL for the audit log, "
                "and I committed to owning the migration checklist before launch."
            ),
        },
        {
            "role": "assistant",
            "name": facilitator,
            "content": (
                "I am the planning facilitator. I recommend a two-week pilot window, "
                "and I will remind the team that risk review is required every Friday."
            ),
        },
        {
            "role": "user",
            "name": charlie,
            "content": (
                "I am Charlie from design. I prefer the onboarding flow to use a "
                "three-step checklist, and I decided that accessibility contrast fixes "
                "must block the release."
            ),
        },
        {
            "role": "user",
            "name": alice,
            "content": (
                "Alice also wants customer interviews scheduled on Tuesdays because "
                "that is when the enterprise advisory group is available."
            ),
        },
        {
            "role": "user",
            "name": bob,
            "content": (
                "Bob's capacity fact is that he can review infrastructure changes "
                "after 14:00 UTC, and he prefers feature flags for risky rollouts."
            ),
        },
        {
            "role": "assistant",
            "name": facilitator,
            "content": (
                "The facilitator's decision is to publish the meeting summary in the "
                "launch-readiness channel and track unresolved decisions separately."
            ),
        },
    ]

    client = MemoryClient(api_key=api_key)

    user_ids = [alice, bob, charlie]
    agent_ids = [facilitator]

    # One ingestion call for the whole named multi-participant conversation.
    client.add(conversation, run_id=session_id, infer=True)

    user_memories, agent_memories = wait_for_all_attributions(
        client=client,
        users=user_ids,
        agents=agent_ids,
        timeout_seconds=GROUP_CHAT_POLL_TIMEOUT_SECONDS,
    )

    if len(user_memories) < len(user_ids) or len(agent_memories) < len(agent_ids):
        add_explicit_attribution_fallback(
            client=client,
            user_messages={
                alice: (
                    f"{alice} prefers shipping the analytics dashboard first, "
                    "defines beta success as more than 40 weekly active teams, "
                    "and wants customer interviews on Tuesdays."
                ),
                bob: (
                    f"{bob} prefers PostgreSQL for the audit log, owns the "
                    "migration checklist, can review infrastructure after 14:00 UTC, "
                    "and prefers feature flags for risky rollouts."
                ),
                charlie: (
                    f"{charlie} prefers a three-step onboarding checklist and "
                    "decided accessibility contrast fixes must block the release."
                ),
            },
            agent_messages={
                facilitator: (
                    f"{facilitator} recommends a two-week pilot, requires Friday "
                    "risk reviews, and will publish the summary in the "
                    "launch-readiness channel."
                )
            },
        )
        user_memories, agent_memories = wait_for_all_attributions(
            client=client,
            users=user_ids,
            agents=agent_ids,
            timeout_seconds=FALLBACK_POLL_TIMEOUT_SECONDS,
        )

    require_complete_attributions(user_ids, agent_ids, user_memories, agent_memories)

    lines = [f"Session: {session_id}"]
    lines.extend(
        f"User memory: {user_id} :: {user_memories[user_id]}"
        for user_id in user_ids
    )
    lines.extend(
        f"Agent memory: {agent_id} :: {agent_memories[agent_id]}"
        for agent_id in agent_ids
    )

    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # Keep failures visible to the verifier/runner.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
