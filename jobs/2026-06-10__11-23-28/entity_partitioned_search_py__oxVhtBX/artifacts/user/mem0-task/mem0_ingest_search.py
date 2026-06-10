import os
import sys
import json
import time
from mem0 import MemoryClient

def main():
    # Read environment variables
    api_key = os.environ.get("MEM0_API_KEY")
    zealt_run_id = os.environ.get("ZEALT_RUN_ID")

    if not api_key:
        print("Error: MEM0_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    if not zealt_run_id:
        print("Error: ZEALT_RUN_ID environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    # Scoping identifiers using ZEALT_RUN_ID as run-id suffix
    run_id_suffix = zealt_run_id
    alice_user_id = f"alice-{run_id_suffix}"
    bob_user_id = f"bob-{run_id_suffix}"
    agent_id = f"travel-agent-{run_id_suffix}"
    app_id = f"concierge-{run_id_suffix}"
    run_id = f"trip-{run_id_suffix}"

    # Initialize Mem0 MemoryClient
    client = MemoryClient(api_key=api_key)

    # 1. Clean up prior memories if any exist to ensure idempotency
    print("Cleaning up existing memories for this run scope (if any)...")
    try:
        client.delete_all(user_id=alice_user_id, agent_id=agent_id, app_id=app_id, run_id=run_id)
        print("Cleaned up Alice's memories.")
    except Exception as e:
        print(f"No prior memories to delete or error deleting for Alice: {e}")

    try:
        client.delete_all(user_id=bob_user_id, agent_id=agent_id, app_id=app_id, run_id=run_id)
        print("Cleaned up Bob's memories.")
    except Exception as e:
        print(f"No prior memories to delete or error deleting for Bob: {e}")

    # Verbatim messages to ingest
    messages_alice = [
        {"role": "user", "content": "I am vegetarian and I love boutique hotels in Lisbon."},
        {"role": "assistant", "content": "Noted. I'll save your dietary preference and Lisbon hotel taste."},
        {"role": "user", "content": "Also, I always book aisle seats on flights."}
    ]

    messages_bob = [
        {"role": "user", "content": "I'm allergic to shellfish and I prefer ski resorts in Hokkaido."},
        {"role": "assistant", "content": "Got it. Logged your shellfish allergy and Hokkaido ski preference."},
        {"role": "user", "content": "I always want a window seat on flights."}
    ]

    # Ingest Traveler A (Alice)
    print("Adding Traveler A (Alice) memories...")
    add_alice_resp = client.add(
        messages=messages_alice,
        user_id=alice_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id
    )
    print(f"Alice add response: {add_alice_resp}")

    # Ingest Traveler B (Bob)
    print("Adding Traveler B (Bob) memories...")
    add_bob_resp = client.add(
        messages=messages_bob,
        user_id=bob_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id
    )
    print(f"Bob add response: {add_bob_resp}")

    # 2. Poll/Wait for memories to be processed and extracted
    print("Waiting for memories to be asynchronously extracted and indexed...")
    max_retries = 30
    delay_seconds = 5
    alice_results = []
    bob_results = []

    search_query = "What are this traveler's flight, food, and lodging preferences?"

    for attempt in range(1, max_retries + 1):
        print(f"Polling attempt {attempt}/{max_retries} (waiting {delay_seconds}s between attempts)...")
        time.sleep(delay_seconds)

        # Search Alice
        try:
            alice_search = client.search(
                query=search_query,
                version="v2",
                filters={
                    "AND": [
                        {"user_id": alice_user_id},
                        {"agent_id": agent_id},
                        {"app_id": app_id},
                        {"run_id": run_id}
                    ]
                },
                top_k=20
            )
        except Exception as e:
            print(f"Error searching Alice's memories: {e}")
            alice_search = []

        # Search Bob
        try:
            bob_search = client.search(
                query=search_query,
                version="v2",
                filters={
                    "AND": [
                        {"user_id": bob_user_id},
                        {"agent_id": agent_id},
                        {"app_id": app_id},
                        {"run_id": run_id}
                    ]
                },
                top_k=20
            )
        except Exception as e:
            print(f"Error searching Bob's memories: {e}")
            bob_search = []

        # Normalize results (either list or dict containing 'results')
        current_alice_results = []
        if isinstance(alice_search, list):
            current_alice_results = alice_search
        elif isinstance(alice_search, dict):
            current_alice_results = alice_search.get("results", [])

        current_bob_results = []
        if isinstance(bob_search, list):
            current_bob_results = bob_search
        elif isinstance(bob_search, dict):
            current_bob_results = bob_search.get("results", [])

        print(f"Retrieved {len(current_alice_results)} memories for Alice.")
        print(f"Retrieved {len(current_bob_results)} memories for Bob.")

        # Check for required keywords
        has_alice_veg = any("vegetarian" in r.get("memory", "").lower() for r in current_alice_results)
        has_bob_shell = any("shellfish" in r.get("memory", "").lower() for r in current_bob_results)

        print(f"Alice has 'vegetarian' memory: {has_alice_veg}")
        print(f"Bob has 'shellfish' memory: {has_bob_shell}")

        if current_alice_results and current_bob_results and has_alice_veg and has_bob_shell:
            alice_results = current_alice_results
            bob_results = current_bob_results
            print("Successfully retrieved non-empty and correct memories for both travelers!")
            break
    else:
        print("Warning: Polling timed out. Proceeding with last retrieved results.")
        alice_results = current_alice_results
        bob_results = current_bob_results

    # 3. Write outputs to JSON artifacts
    os.makedirs("/home/user/mem0-task", exist_ok=True)

    alice_artifact = {
        "user_id": alice_user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": run_id,
        "results": alice_results
    }

    bob_artifact = {
        "user_id": bob_user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": run_id,
        "results": bob_results
    }

    alice_path = "/home/user/mem0-task/alice_memories.json"
    bob_path = "/home/user/mem0-task/bob_memories.json"

    with open(alice_path, "w") as f:
        json.dump(alice_artifact, f, indent=2)
    print(f"Wrote Alice memories to {alice_path}")

    with open(bob_path, "w") as f:
        json.dump(bob_artifact, f, indent=2)
    print(f"Wrote Bob memories to {bob_path}")

    # 4. Final log lines to stdout
    print(f"RUN_ID: {zealt_run_id}")
    print(f"TRAVELER_A_MEMORIES: {len(alice_results)}")
    print(f"TRAVELER_B_MEMORIES: {len(bob_results)}")

if __name__ == "__main__":
    main()
