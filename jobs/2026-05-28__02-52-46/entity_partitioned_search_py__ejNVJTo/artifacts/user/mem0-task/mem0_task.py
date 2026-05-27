import os
import json
import time
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id_suffix = os.environ.get("ZEALT_RUN_ID")

    if not api_key:
        raise ValueError("MEM0_API_KEY environment variable is not set")
    if not run_id_suffix:
        raise ValueError("ZEALT_RUN_ID environment variable is not set")

    client = MemoryClient(api_key=api_key)

    agent_id = f"travel-agent-{run_id_suffix}"
    app_id = f"concierge-{run_id_suffix}"
    trip_run_id = f"trip-{run_id_suffix}"
    
    alice_id = f"alice-{run_id_suffix}"
    bob_id = f"bob-{run_id_suffix}"

    # Traveler A messages
    alice_messages = [
        {"role": "user", "content": "I am vegetarian and I love boutique hotels in Lisbon."},
        {"role": "assistant", "content": "Noted. I'll save your dietary preference and Lisbon hotel taste."},
        {"role": "user", "content": "Also, I always book aisle seats on flights."}
    ]

    # Traveler B messages
    bob_messages = [
        {"role": "user", "content": "I'm allergic to shellfish and I prefer ski resorts in Hokkaido."},
        {"role": "assistant", "content": "Got it. Logged your shellfish allergy and Hokkaido ski preference."},
        {"role": "user", "content": "I always want a window seat on flights."}
    ]

    print(f"Ingesting memories for Alice ({alice_id})...")
    client.add(messages=alice_messages, user_id=alice_id, agent_id=agent_id, app_id=app_id, run_id=trip_run_id)

    print(f"Ingesting memories for Bob ({bob_id})...")
    client.add(messages=bob_messages, user_id=bob_id, agent_id=agent_id, app_id=app_id, run_id=trip_run_id)

    # Wait for async extraction
    print("Waiting for memories to be processed...")
    max_retries = 10
    alice_results = []
    bob_results = []

    search_query = "What are this traveler's flight, food, and lodging preferences?"

    for i in range(max_retries):
        time.sleep(5) # Wait 5 seconds between polls
        
        # Search for Alice
        alice_filters = {
            "AND": [
                {"user_id": alice_id},
                {"agent_id": agent_id},
                {"app_id": app_id},
                {"run_id": trip_run_id}
            ]
        }
        resp_alice = client.search(search_query, version="v2", filters=alice_filters, top_k=20)
        alice_results = resp_alice.get("results", []) if isinstance(resp_alice, dict) else resp_alice

        # Search for Bob
        bob_filters = {
            "AND": [
                {"user_id": bob_id},
                {"agent_id": agent_id},
                {"app_id": app_id},
                {"run_id": trip_run_id}
            ]
        }
        resp_bob = client.search(search_query, version="v2", filters=bob_filters, top_k=20)
        bob_results = resp_bob.get("results", []) if isinstance(resp_bob, dict) else resp_bob

        if len(alice_results) > 0 and len(bob_results) > 0:
            print(f"Found {len(alice_results)} memories for Alice and {len(bob_results)} for Bob.")
            break
        print(f"Retry {i+1}/{max_retries}: Alice={len(alice_results)}, Bob={len(bob_results)}")

    # Write Alice's results
    alice_output = {
        "user_id": alice_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": trip_run_id,
        "results": alice_results
    }
    with open("/home/user/mem0-task/alice_memories.json", "w") as f:
        json.dump(alice_output, f, indent=2)

    # Write Bob's results
    bob_output = {
        "user_id": bob_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": trip_run_id,
        "results": bob_results
    }
    with open("/home/user/mem0-task/bob_memories.json", "w") as f:
        json.dump(bob_output, f, indent=2)

    # Final logs
    print(f"RUN_ID: {run_id_suffix}")
    print(f"TRAVELER_A_MEMORIES: {len(alice_results)}")
    print(f"TRAVELER_B_MEMORIES: {len(bob_results)}")

if __name__ == "__main__":
    main()
