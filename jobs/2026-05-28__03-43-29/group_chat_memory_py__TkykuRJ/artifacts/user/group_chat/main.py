import os
import time
from mem0 import MemoryClient


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_conversation(run_id: str):
    alice = f"alice-{run_id}"
    bob = f"bob-{run_id}"
    charlie = f"charlie-{run_id}"
    facilitator = f"facilitator-{run_id}"

    messages = [
        {
            "role": "user",
            "name": alice,
            "content": "I prefer a weekly planning cadence and want a lightweight agenda shared ahead of time.",
        },
        {
            "role": "user",
            "name": bob,
            "content": "I want us to prioritize the onboarding flow and ship the new tutorial by next sprint.",
        },
        {
            "role": "user",
            "name": charlie,
            "content": "I think we should keep the dashboard metrics limited to three KPIs to avoid noise.",
        },
        {
            "role": "assistant",
            "name": facilitator,
            "content": "Noted: weekly planning, onboarding tutorial priority, and a three-KPI dashboard focus.",
        },
    ]

    participants = {
        "users": [alice, bob, charlie],
        "agent": facilitator,
    }

    return messages, participants


def poll_memories(client: MemoryClient, filters: dict, timeout_seconds: int = 60):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = client.get_all(filters=filters)
        except Exception:
            return []
        if isinstance(response, dict):
            memories = response.get("results") or []
        else:
            memories = response or []
        if memories:
            return memories
        time.sleep(2)
    return []


def main():
    api_key = require_env("MEM0_API_KEY")
    run_id_env = require_env("ZEALT_RUN_ID")
    session_run_id = f"planning-{run_id_env}"

    client = MemoryClient(api_key=api_key)

    messages, participants = build_conversation(run_id_env)
    client.add(messages, run_id=session_run_id)

    log_lines = [f"Session: {session_run_id}"]

    def normalize_memory(entry):
        if isinstance(entry, dict):
            return entry.get("memory", "")
        return str(entry)

    for user_id in participants["users"]:
        memories = poll_memories(client, filters={"user_id": user_id})
        if not memories:
            log_lines.append(f"User memory: {user_id} :: ")
        for memory in memories:
            memory_text = normalize_memory(memory)
            log_lines.append(f"User memory: {user_id} :: {memory_text}")

    agent_id = participants["agent"]
    agent_memories = poll_memories(client, filters={"agent_id": agent_id})
    if not agent_memories:
        log_lines.append(f"Agent memory: {agent_id} :: ")
    for memory in agent_memories:
        memory_text = normalize_memory(memory)
        log_lines.append(f"Agent memory: {agent_id} :: {memory_text}")

    output_path = "/home/user/group_chat/output.log"
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(log_lines))


if __name__ == "__main__":
    main()
