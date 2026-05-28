import os
import json
import time
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id = os.environ.get("ZEALT_RUN_ID")
    
    if not api_key:
        raise ValueError("MEM0_API_KEY environment variable is missing")
    if not run_id:
        raise ValueError("ZEALT_RUN_ID environment variable is missing")

    client = MemoryClient() # uses MEM0_API_KEY by default
    
    alice_user_id = f"alice-{run_id}"
    bob_user_id = f"bob-{run_id}"
    agent_id = f"travel-agent-{run_id}"
    app_id = f"concierge-{run_id}"
    run_id_val = f"trip-{run_id}"
    
    # Alice's messages
    alice_messages = [
        {"role": "user", "content": "I am vegetarian and I love boutique hotels in Lisbon."},
        {"role": "assistant", "content": "Noted. I'll save your dietary preference and Lisbon hotel taste."},
        {"role": "user", "content": "Also, I always book aisle seats on flights."}
    ]
    
    # Bob's messages
    bob_messages = [
        {"role": "user", "content": "I'm allergic to shellfish and I prefer ski resorts in Hokkaido."},
        {"role": "assistant", "content": "Got it. Logged your shellfish allergy and Hokkaido ski preference."},
        {"role": "user", "content": "I always want a window seat on flights."}
    ]
    
    # Ingest Alice
    client.add(
        alice_messages,
        user_id=alice_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id_val
    )
    
    # Ingest Bob
    client.add(
        bob_messages,
        user_id=bob_user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=run_id_val
    )
    
    # Wait for memory extraction
    time.sleep(10)
    
    query = "What are this traveler's flight, food, and lodging preferences?"
    
    # Search for Alice
    alice_filters = {
        "AND": [
            {"user_id": alice_user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": run_id_val}
        ]
    }
    
    alice_search = client.search(
        query,
        version="v2",
        filters=alice_filters,
        top_k=20
    )
    
    alice_results = alice_search.get("results", []) if isinstance(alice_search, dict) else alice_search
    
    alice_output = {
        "user_id": alice_user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": run_id_val,
        "results": alice_results
    }
    
    with open("/home/user/mem0-task/alice_memories.json", "w") as f:
        json.dump(alice_output, f, indent=2)
        
    # Search for Bob
    bob_filters = {
        "AND": [
            {"user_id": bob_user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": run_id_val}
        ]
    }
    
    bob_search = client.search(
        query,
        version="v2",
        filters=bob_filters,
        top_k=20
    )
    
    bob_results = bob_search.get("results", []) if isinstance(bob_search, dict) else bob_search
    
    bob_output = {
        "user_id": bob_user_id,
        "agent_id": agent_id,
        "app_id": app_id,
        "run_id": run_id_val,
        "results": bob_results
    }
    
    with open("/home/user/mem0-task/bob_memories.json", "w") as f:
        json.dump(bob_output, f, indent=2)
        
    print(f"RUN_ID: {run_id}")
    print(f"TRAVELER_A_MEMORIES: {len(alice_results)}")
    print(f"TRAVELER_B_MEMORIES: {len(bob_results)}")

if __name__ == "__main__":
    main()
