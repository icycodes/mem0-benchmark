"""
Mem0 Group Chat Memory Attribution
-----------------------------------
Ingests a multi-participant planning conversation into the Mem0 Platform,
then polls for memories per participant and writes an attribution log.
"""

import os
import sys
import time

from mem0 import MemoryClient

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("MEM0_API_KEY", "")
if not API_KEY:
    sys.exit("ERROR: MEM0_API_KEY environment variable is not set.")

RUN_ID = os.environ.get("ZEALT_RUN_ID", "")
if not RUN_ID:
    sys.exit("ERROR: ZEALT_RUN_ID environment variable is not set.")

SESSION_RUN_ID = f"planning-{RUN_ID}"

# Suffixed participant identifiers (unique per trial)
ALICE      = f"alice-{RUN_ID}"
BOB        = f"bob-{RUN_ID}"
CHARLIE    = f"charlie-{RUN_ID}"
FACILITATOR = f"facilitator-{RUN_ID}"

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.log")

# ---------------------------------------------------------------------------
# Conversation payload
# ---------------------------------------------------------------------------
# Each message carries `role`, `name`, and `content`.
# The `name` field is what Mem0's Group Chat feature uses to attribute
# memories to individual user_ids (role=user) or agent_ids (role=assistant).
CONVERSATION = [
    {
        "role": "user",
        "name": ALICE,
        "content": (
            "I strongly prefer we use PostgreSQL for the new backend. "
            "I've benchmarked it and it handles our expected 10k RPS without breaking a sweat. "
            "Also, I think we should adopt trunk-based development going forward."
        ),
    },
    {
        "role": "assistant",
        "name": FACILITATOR,
        "content": (
            "Noted. PostgreSQL and trunk-based development are on the table. "
            "My recommendation is to pair that with a feature-flag system so we can "
            "deploy continuously without exposing unfinished work. "
            "I'll track all decisions in this session."
        ),
    },
    {
        "role": "user",
        "name": BOB,
        "content": (
            "I agree with PostgreSQL. "
            "Additionally, I want us to commit to writing integration tests for every new endpoint "
            "before merging — no exceptions. "
            "My preference for the front-end framework is React with TypeScript."
        ),
    },
    {
        "role": "user",
        "name": CHARLIE,
        "content": (
            "I'd like to push back slightly on trunk-based development; "
            "I think short-lived feature branches (max 2 days) are a better fit for our team size. "
            "For the API layer I strongly prefer GraphQL over REST because it reduces over-fetching. "
            "I also volunteer to own the on-call rotation schedule."
        ),
    },
    {
        "role": "user",
        "name": ALICE,
        "content": (
            "Charlie raises a fair point. Two-day feature branches sound workable. "
            "Let's also decide on a 99.9% uptime SLA for the production service — "
            "I'll add that to the architecture doc."
        ),
    },
    {
        "role": "assistant",
        "name": FACILITATOR,
        "content": (
            "Summarising decisions so far: "
            "1) PostgreSQL as the primary database. "
            "2) Short-lived feature branches (≤2 days). "
            "3) Mandatory integration tests before merge. "
            "4) React + TypeScript for the front-end. "
            "5) GraphQL for the API layer. "
            "6) 99.9% uptime SLA. "
            "7) Charlie owns the on-call rotation. "
            "I'll flag any conflicts that arise."
        ),
    },
    {
        "role": "user",
        "name": BOB,
        "content": (
            "Agreed on all points. "
            "One more thing from my side: I prefer we use GitHub Actions for CI/CD "
            "and keep all infrastructure-as-code in Terraform."
        ),
    },
    {
        "role": "user",
        "name": CHARLIE,
        "content": (
            "Sounds good. I'll set up the on-call schedule in PagerDuty by end of week. "
            "Also confirming my preference for Apollo Client on the front-end to pair with GraphQL."
        ),
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def poll_memories(client: MemoryClient, filters: dict, label: str,
                  timeout: int = 120, interval: int = 5) -> list:
    """
    Poll client.get_all(version='v2', filters=filters) until at least one
    memory appears or timeout is reached.
    """
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            result = client.get_all(version="v2", filters=filters)
            # result may be a list directly or a dict with a 'results' key
            memories = result if isinstance(result, list) else result.get("results", [])
            if memories:
                print(f"  [{label}] found {len(memories)} memory/memories after {attempt} poll(s).")
                return memories
        except Exception as exc:  # noqa: BLE001
            print(f"  [{label}] poll error (will retry): {exc}")
        print(f"  [{label}] no memories yet (attempt {attempt}), waiting {interval}s…")
        time.sleep(interval)
    print(f"  [{label}] WARNING: timed out waiting for memories.")
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Session run_id : {SESSION_RUN_ID}")
    print(f"Participants   : {ALICE}, {BOB}, {CHARLIE} (users) | {FACILITATOR} (agent)")
    print(f"Log path       : {LOG_PATH}")
    print()

    # 1. Authenticate
    client = MemoryClient(api_key=API_KEY)

    # 2. Ingest the conversation in one call
    print("Adding conversation to Mem0…")
    add_response = client.add(
        CONVERSATION,
        run_id=SESSION_RUN_ID,
    )
    print(f"add() response: {add_response}")
    print()

    # 3. Poll for memories per participant
    participants = [
        ("user",  "user_id",  ALICE),
        ("user",  "user_id",  BOB),
        ("user",  "user_id",  CHARLIE),
        ("agent", "agent_id", FACILITATOR),
    ]

    attribution: dict[str, list] = {}
    for kind, filter_key, pid in participants:
        print(f"Polling memories for {kind} '{pid}'…")
        memories = poll_memories(
            client,
            filters={filter_key: pid},
            label=pid,
        )
        attribution[pid] = (kind, memories)
        print()

    # 4. Write attribution log
    lines: list[str] = []
    lines.append(f"Session: {SESSION_RUN_ID}")

    for pid, (kind, memories) in attribution.items():
        if kind == "user":
            for mem in memories:
                text = mem.get("memory", str(mem))
                lines.append(f"User memory: {pid} :: {text}")
        else:
            for mem in memories:
                text = mem.get("memory", str(mem))
                lines.append(f"Agent memory: {pid} :: {text}")

    with open(LOG_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("=== Attribution log written ===")
    for line in lines:
        print(line)

    # 5. Verify all required prefixes are present
    has_session   = any(l.startswith(f"Session: {SESSION_RUN_ID}") for l in lines)
    user_lines    = [l for l in lines if l.startswith("User memory:")]
    agent_lines   = [l for l in lines if l.startswith("Agent memory:")]

    user_ids_seen = set()
    for l in user_lines:
        uid = l.split("::")[0].replace("User memory:", "").strip()
        user_ids_seen.add(uid)

    print()
    print("=== Verification ===")
    print(f"Session line present : {has_session}")
    print(f"Distinct users logged: {user_ids_seen} ({len(user_ids_seen)}/3 required)")
    print(f"Agent memory lines   : {len(agent_lines)}")

    ok = has_session and len(user_ids_seen) >= 3 and len(agent_lines) >= 1
    if ok:
        print("PASS: all acceptance criteria met.")
    else:
        print("FAIL: one or more acceptance criteria not met — check output.log and Mem0 dashboard.")
        sys.exit(1)


if __name__ == "__main__":
    main()
