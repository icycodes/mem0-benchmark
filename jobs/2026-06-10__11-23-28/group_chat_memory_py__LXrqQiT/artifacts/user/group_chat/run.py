#!/usr/bin/env python3
"""Group Chat memory attribution script for Mem0 Platform.

Reads ZEALT_RUN_ID and MEM0_API_KEY from the environment, constructs a
multi-participant conversation, ingests it via MemoryClient, polls for
extracted memories, and writes an attribution log to output.log.
"""

import os
import sys
import time

from mem0 import MemoryClient


def main():
    # --- Environment ---
    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("ERROR: MEM0_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    run_id_raw = os.environ.get("ZEALT_RUN_ID")
    if not run_id_raw:
        print("ERROR: ZEALT_RUN_ID not set", file=sys.stderr)
        sys.exit(1)

    # Suffix everything with the run id so concurrent trials don't collide.
    run_id = f"planning-{run_id_raw}"

    # Participant identifiers (suffixed with run_id_raw per requirements).
    alice_id = f"alice-{run_id_raw}"
    bob_id = f"bob-{run_id_raw}"
    charlie_id = f"charlie-{run_id_raw}"
    facilitator_id = f"facilitator-{run_id_raw}"

    # --- Client ---
    client = MemoryClient(api_key=api_key)

    # --- Build the conversation ---
    # Three distinct user participants + one assistant, all with `name`.
    messages = [
        {
            "role": "user",
            "name": alice_id,
            "content": (
                "I think we should use PostgreSQL for the database layer. "
                "It has strong ACID compliance and excellent JSON support "
                "for semi-structured data."
            ),
        },
        {
            "role": "user",
            "name": bob_id,
            "content": (
                "I'd prefer we stick with Redis for caching and session "
                "storage. We already have operational expertise with it, "
                "and it handles our throughput easily."
            ),
        },
        {
            "role": "user",
            "name": charlie_id,
            "content": (
                "For the API layer I strongly recommend FastAPI. It gives "
                "us automatic OpenAPI docs and async support out of the box, "
                "which will save us a ton of boilerplate."
            ),
        },
        {
            "role": "assistant",
            "name": facilitator_id,
            "content": (
                "Those are all solid picks. Let me summarise: Alice wants "
                "PostgreSQL, Bob wants Redis, and Charlie wants FastAPI. "
                "I'll note these as the team's technology preferences and "
                "we can revisit trade-offs at the architecture review."
            ),
        },
        {
            "role": "user",
            "name": alice_id,
            "content": (
                "Also, I want to make sure we set up database replication "
                "from day one. I've been burned by single-node setups before."
            ),
        },
        {
            "role": "user",
            "name": bob_id,
            "content": (
                "Agreed on replication. For Redis I'd like to use sentinel "
                "mode so failover is automatic. That's worked well for us "
                "in the past."
            ),
        },
        {
            "role": "user",
            "name": charlie_id,
            "content": (
                "One more thing — I think we should deploy everything on "
                "Kubernetes. It'll make our CI/CD pipeline much simpler and "
                "we can use Helm charts for repeatable deployments."
            ),
        },
        {
            "role": "assistant",
            "name": facilitator_id,
            "content": (
                "Great additions everyone. I've captured the replication "
                "requirement from Alice, Redis Sentinel from Bob, and "
                "Kubernetes from Charlie. Let's reconvene after the spike."
            ),
        },
    ]

    # --- Ingest ---
    # IMPORTANT: Do NOT pass user_id here — that would override the per-message
    # `name` field and cause all memories to be attributed to a single user.
    # The group-chat feature relies on the `name` field in each message.
    print(f"Ingesting conversation with run_id={run_id} ...")
    client.add(messages, run_id=run_id)
    print("Ingestion submitted (async). Polling for memories...")

    # --- Poll for memories ---
    # Memory extraction is async; poll get_all with filters until we see
    # at least one memory per participant, or timeout.
    deadline = time.time() + 60  # 60-second timeout
    poll_interval = 3

    participant_ids = [alice_id, bob_id, charlie_id, facilitator_id]
    # user participants -> user_id filter; facilitator -> agent_id filter
    user_participants = {alice_id, bob_id, charlie_id}
    agent_participants = {facilitator_id}

    memories_by_participant = {pid: [] for pid in participant_ids}

    while time.time() < deadline:
        all_found = True
        for pid in participant_ids:
            if not memories_by_participant[pid]:
                if pid in user_participants:
                    resp = client.get_all(filters={"user_id": pid})
                else:
                    resp = client.get_all(filters={"agent_id": pid})
                results = resp.get("results", []) if isinstance(resp, dict) else []
                if results:
                    memories_by_participant[pid] = results
                else:
                    all_found = False

        if all_found:
            print("All participant memories retrieved.")
            break

        print(f"Waiting for memories... ({int(deadline - time.time())}s left)")
        time.sleep(poll_interval)
    else:
        print("WARNING: Timed out waiting for some participant memories.",
              file=sys.stderr)

    # --- Write attribution log ---
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "output.log")

    with open(output_path, "w") as f:
        # Session line (exactly once)
        f.write(f"Session: {run_id}\n")

        # User memory lines
        for uid in [alice_id, bob_id, charlie_id]:
            for mem in memories_by_participant.get(uid, []):
                memory_text = mem.get("memory", "")
                f.write(f"User memory: {uid} :: {memory_text}\n")

        # Agent memory lines
        for aid in [facilitator_id]:
            for mem in memories_by_participant.get(aid, []):
                memory_text = mem.get("memory", "")
                f.write(f"Agent memory: {aid} :: {memory_text}\n")

    print(f"Attribution log written to {output_path}")


if __name__ == "__main__":
    main()
