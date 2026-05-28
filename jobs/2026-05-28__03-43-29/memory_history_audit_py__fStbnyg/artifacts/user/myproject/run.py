"""
Audit Memory Updates with Mem0 Platform History
Seeds a user profile, updates a memory, and writes an auditable log.
"""

import json
import os
import sys
import time

from mem0 import MemoryClient
from mem0.client.types import GetAllMemoryOptions

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("MEM0_API_KEY", "")
if not API_KEY:
    sys.exit("ERROR: MEM0_API_KEY environment variable is not set.")

RUN_ID = os.environ.get("ZEALT_RUN_ID", "")
if not RUN_ID:
    sys.exit("ERROR: ZEALT_RUN_ID environment variable is not set.")

USER_ID = f"harbor-history-{RUN_ID}"
LOG_PATH = "/home/user/myproject/output.log"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_memories(client: MemoryClient, user_id: str,
                      poll_interval: float = 4.0, max_wait: float = 90.0) -> list:
    """Poll get_all with a user_id filter until at least one memory appears."""
    options = GetAllMemoryOptions(filters={"user_id": user_id})
    deadline = time.time() + max_wait
    while time.time() < deadline:
        result = client.get_all(options=options)
        items = result.get("results", []) if isinstance(result, dict) else list(result)
        if items:
            return items
        print(f"    … still processing, retrying in {poll_interval}s")
        time.sleep(poll_interval)
    return []


def pick_role_memory(memories: list) -> dict | None:
    """Return the memory whose extracted text best mentions the user's role."""
    role_keywords = ("engineer", "developer", "analyst", "manager",
                     "junior", "senior", "acme", "backend", "python")
    for entry in memories:
        text = (entry.get("memory") or "").lower()
        if any(kw in text for kw in role_keywords):
            return entry
    return memories[0] if memories else None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    client = MemoryClient(api_key=API_KEY)

    print(f"[+] User ID: {USER_ID}")

    # ------------------------------------------------------------------
    # 1. Seed the user profile with a multi-turn conversation
    # ------------------------------------------------------------------
    seed_messages = [
        {
            "role": "user",
            "content": (
                "Hi! I just started my new job. I'm a junior software engineer "
                "at Acme Corp, working on backend Python services."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "Welcome! It's great to hear you've started a new role as a junior "
                "software engineer at Acme Corp. Backend Python work sounds exciting. "
                "How can I help you today?"
            ),
        },
        {
            "role": "user",
            "content": (
                "I'd like to track my progress. My team is small – just three engineers – "
                "and I'm focusing on REST API development and unit testing."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "That's a great focus area. REST APIs and unit testing are core skills "
                "for a backend engineer. I'll remember that you're a junior software engineer "
                "at Acme Corp specialising in REST API development and Python."
            ),
        },
    ]

    print("[+] Adding seed memories …")
    add_result = client.add(seed_messages, user_id=USER_ID)
    print(f"    add() returned: {add_result}")

    # ------------------------------------------------------------------
    # 2. Poll until memories appear for this user
    # ------------------------------------------------------------------
    print("[+] Waiting for memories to become available …")
    memories = wait_for_memories(client, USER_ID, poll_interval=4.0, max_wait=90.0)

    if not memories:
        sys.exit("ERROR: No memories were extracted after waiting. "
                 "Check the API key and run-id.")

    print(f"    Found {len(memories)} memory/memories.")
    for m in memories:
        print(f"      id={m['id']}  text={m.get('memory', '')!r}")

    # ------------------------------------------------------------------
    # 3. Pick the target memory (prefer one that mentions the role)
    # ------------------------------------------------------------------
    target = pick_role_memory(memories)
    if target is None:
        sys.exit("ERROR: Could not find a suitable memory to update.")

    memory_id: str = target["id"]
    old_text: str = target.get("memory", "")
    print(f"[+] Selected memory  : {memory_id}")
    print(f"    Original text    : {old_text!r}")

    # ------------------------------------------------------------------
    # 4. Update the memory – promote the engineer to senior
    # ------------------------------------------------------------------
    new_text = (
        "User is a senior software engineer at Acme Corp, "
        "specialising in REST API development and Python backend services."
    )
    new_metadata = {
        "role": "senior software engineer",
        "company": "Acme Corp",
        "skills": ["REST API", "Python", "backend services"],
        "audit_updated": True,
    }

    print("[+] Updating memory …")
    update_result = client.update(
        memory_id=memory_id, text=new_text, metadata=new_metadata
    )
    print(f"    update() returned: {update_result}")

    # Allow the platform a moment to persist the update before fetching history
    print("[+] Waiting for update to propagate …")
    time.sleep(6)

    # ------------------------------------------------------------------
    # 5. Verify the stored text now mentions "senior"
    # ------------------------------------------------------------------
    refreshed = client.get(memory_id)
    stored_text = refreshed.get("memory", "")
    print(f"    Stored text now  : {stored_text!r}")
    if "senior" not in stored_text.lower():
        print("WARNING: Stored text does not yet contain 'senior'. "
              "Waiting a few more seconds …")
        time.sleep(8)
        refreshed = client.get(memory_id)
        stored_text = refreshed.get("memory", "")
        print(f"    Stored text now  : {stored_text!r}")

    # ------------------------------------------------------------------
    # 6. Retrieve the full change history
    # ------------------------------------------------------------------
    print("[+] Fetching history …")
    history = client.history(memory_id)
    print(f"    History entries  : {len(history)}")
    for entry in history:
        print(f"      event={entry.get('event')}  "
              f"old={entry.get('old_memory')!r}  "
              f"new={entry.get('new_memory')!r}")

    # Validate required event types
    events_in_history = {str(entry.get("event", "")).upper() for entry in history}
    if "ADD" not in events_in_history:
        print("WARNING: No ADD event found in history.")
    if "UPDATE" not in events_in_history:
        print("WARNING: No UPDATE event found in history.")

    # Serialise to JSON (handle non-serialisable types gracefully)
    try:
        events_json = json.dumps(history, default=str)
    except (TypeError, ValueError) as exc:
        sys.exit(f"ERROR: Could not serialise history to JSON: {exc}")

    # ------------------------------------------------------------------
    # 7. Write the audit log
    # ------------------------------------------------------------------
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as fh:
        fh.write(f"User ID: {USER_ID}\n")
        fh.write(f"Memory ID: {memory_id}\n")
        fh.write(f"Events JSON: {events_json}\n")

    print(f"[+] Audit log written to {LOG_PATH}")
    print("\n=== Audit Log ===")
    with open(LOG_PATH, encoding="utf-8") as fh:
        print(fh.read())


if __name__ == "__main__":
    main()
