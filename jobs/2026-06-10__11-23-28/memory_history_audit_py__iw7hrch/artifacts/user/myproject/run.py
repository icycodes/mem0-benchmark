#!/usr/bin/env python3
"""Audit Memory Updates with Mem0 Platform History.

This script:
1. Connects to the Mem0 Platform using MEM0_API_KEY from the environment.
2. Seeds a user profile with a multi-turn conversation establishing job role.
3. Picks one extracted memory and updates it (changing junior → senior).
4. Retrieves the full change history and persists a structured audit log.
"""

import json
import os
import sys
import time

from mem0 import MemoryClient


def main() -> None:
    # --- Configuration ---
    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("ERROR: MEM0_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    zealt_run_id = os.environ.get("ZEALT_RUN_ID")
    if not zealt_run_id:
        print("ERROR: ZEALT_RUN_ID environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    user_id = f"harbor-history-{zealt_run_id}"
    output_path = "/home/user/myproject/output.log"

    client = MemoryClient(api_key=api_key)

    # --- Step 1: Seed the user profile with a multi-turn conversation ---
    messages = [
        {
            "role": "user",
            "content": "Hi, I just started a new job and need help setting up my profile.",
        },
        {
            "role": "assistant",
            "content": "Congratulations! Tell me about your role and I'll get your profile set up.",
        },
        {
            "role": "user",
            "content": (
                "I am a junior software engineer at Quantum Dynamics Inc. "
                "I work on the backend team building distributed systems."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "That sounds exciting! I've noted that you're a junior engineer at "
                "Quantum Dynamics. Let me know if you need anything else."
            ),
        },
    ]

    print(f"Seeding memories for user_id={user_id} ...")
    client.add(messages, user_id=user_id)

    # --- Step 2: Wait for async processing, then find the role memory ---
    target_memory = None
    for attempt in range(15):
        time.sleep(2)
        response = client.get_all(filters={"user_id": user_id})
        results = response.get("results", [])
        if results:
            # Prefer a memory whose text mentions "engineer" or "role"
            for mem in results:
                text = (mem.get("memory") or "").lower()
                if "engineer" in text or "junior" in text:
                    target_memory = mem
                    break
            # Fallback: take the first memory if no role match
            if target_memory is None:
                target_memory = results[0]
            break
    else:
        print("ERROR: No memories were extracted after waiting.", file=sys.stderr)
        sys.exit(1)

    memory_id = target_memory["id"]
    original_text = target_memory.get("memory", "")
    print(f"Found target memory: id={memory_id}, text='{original_text}'")

    # --- Step 3: Update the memory — promote to senior ---
    new_text = (
        "User is a senior software engineer at Quantum Dynamics Inc., "
        "working on the backend team building distributed systems."
    )
    new_metadata = {
        "role": "senior software engineer",
        "company": "Quantum Dynamics Inc.",
        "team": "backend",
    }

    print(f"Updating memory {memory_id} ...")
    client.update(memory_id=memory_id, text=new_text, metadata=new_metadata)

    # Brief wait for the update to be processed
    time.sleep(2)

    # --- Step 4: Retrieve the full change history ---
    history = client.history(memory_id)

    # --- Step 5: Verify the update is reflected ---
    # Fetch the current state to confirm "senior" is present
    response = client.get_all(filters={"user_id": user_id})
    current_memory = None
    for mem in response.get("results", []):
        if mem["id"] == memory_id:
            current_memory = mem
            break

    if current_memory is None or "senior" not in (current_memory.get("memory") or "").lower():
        print("WARNING: Updated memory text does not contain 'senior'.", file=sys.stderr)
        # Continue anyway — the history log will still be written

    # --- Step 6: Write the audit log ---
    events_json = json.dumps(history, ensure_ascii=False)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"User ID: {user_id}\n")
        f.write(f"Memory ID: {memory_id}\n")
        f.write(f"Events JSON: {events_json}\n")

    print(f"Audit log written to {output_path}")

    # --- Validation ---
    events = history
    has_add = any(e.get("event") == "ADD" for e in events)
    has_update = any(e.get("event") == "UPDATE" for e in events)

    if not has_add:
        print("ERROR: History is missing an ADD event.", file=sys.stderr)
        sys.exit(1)
    if not has_update:
        print("ERROR: History is missing an UPDATE event.", file=sys.stderr)
        sys.exit(1)

    print("Audit trail verified: ADD and UPDATE events present.")


if __name__ == "__main__":
    main()
