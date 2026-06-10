import os
import sys
import time
import json
from mem0 import MemoryClient

def main():
    # 1. Connect to the Mem0 Platform with the mem0ai Python SDK
    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("Error: MEM0_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    # 2. Scope every memory to a user_id derived from the ZEALT_RUN_ID environment variable
    run_id = os.environ.get("ZEALT_RUN_ID")
    if not run_id:
        print("Error: ZEALT_RUN_ID environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    user_id = f"harbor-history-{run_id}"
    print(f"Using User ID: {user_id}")

    client = MemoryClient(api_key=api_key)

    # 3. Seed the user profile with a multi-turn conversation that establishes the user's current job role
    messages = [
        {"role": "user", "content": "Hi! I am starting my new job today at TechCorp. I'm a junior software engineer and I'm really excited but a bit nervous."},
        {"role": "assistant", "content": "Congratulations on your new job at TechCorp as a junior software engineer! It's completely normal to feel nervous, but you'll do great. What stack will you be working with?"},
        {"role": "user", "content": "I'll be working with Python and React. I've done some minor projects with them, but this is my first real industry role."},
        {"role": "assistant", "content": "Python and React are fantastic! Since you are a junior engineer, you'll have plenty of opportunities to learn from your team. Best of luck on your first day!"}
    ]

    print("Adding conversation to seed the user profile...")
    add_response = client.add(messages, user_id=user_id)
    print("Add response:", add_response)

    # Poll the event status to wait for the memories to be processed
    event_id = add_response.get("event_id")
    results = []
    if event_id:
        print(f"Polling event {event_id} for completion...")
        for i in range(30):
            try:
                event_res = client.client.get(f"/v1/event/{event_id}/").json()
                status = event_res.get("status")
                print(f"Attempt {i+1}: Event status is {status}")
                if status == "SUCCEEDED":
                    results = event_res.get("results", [])
                    break
                elif status == "FAILED":
                    print("Error: Memory extraction event failed.", file=sys.stderr)
                    break
            except Exception as e:
                print(f"Warning during polling: {e}", file=sys.stderr)
            time.sleep(2)
    else:
        results = add_response if isinstance(add_response, list) else add_response.get("results", [])

    # 4. Pick exactly one of the extracted memories (prefer one mentioning the junior engineer role)
    target_memory = None
    for item in results:
        if item.get("event") == "ADD":
            mem_text = item.get("data", {}).get("memory", "").lower()
            if any(word in mem_text for word in ["junior", "engineer", "role", "developer"]):
                target_memory = item
                break

    if not target_memory:
        # Fallback to any ADD memory in results
        for item in results:
            if item.get("event") == "ADD":
                target_memory = item
                break

    # If still not found, fetch from get_all
    if not target_memory:
        print("Target memory not found in event results. Fetching all memories for user...")
        time.sleep(3) # Wait a bit more to ensure processing is complete
        try:
            memories_res = client.get_all(filters={"user_id": user_id})
            memories = memories_res.get("results", [])
            print("Fetched memories:", memories)
            for mem in memories:
                mem_text = mem.get("memory", "").lower()
                if any(word in mem_text for word in ["junior", "engineer", "role", "developer"]):
                    target_memory = {"id": mem.get("id"), "data": {"memory": mem.get("memory")}}
                    break
            if not target_memory and memories:
                target_memory = {"id": memories[0].get("id"), "data": {"memory": memories[0].get("memory")}}
        except Exception as e:
            print(f"Error fetching memories: {e}", file=sys.stderr)

    if not target_memory:
        print("Error: Could not find or extract any memory for the user.", file=sys.stderr)
        sys.exit(1)

    memory_id = target_memory.get("id")
    old_text = target_memory.get("data", {}).get("memory") if "data" in target_memory else target_memory.get("memory")
    print(f"Selected memory to update: ID={memory_id}, Text='{old_text}'")

    # Update its text and metadata
    new_text = "User has been promoted to a senior software engineer at TechCorp."
    print(f"Updating memory {memory_id} with new text and metadata...")
    update_res = client.update(
        memory_id=memory_id,
        text=new_text,
        metadata={"role": "senior", "promoted": True}
    )
    print("Update response:", update_res)

    # Wait a moment for history to record
    time.sleep(3)

    # 5. Retrieve the full change history for that memory
    print(f"Retrieving history for memory {memory_id}...")
    history_res = client.history(memory_id=memory_id)
    print("History response:", history_res)

    # Write structured audit log to disk
    log_path = "/home/user/myproject/output.log"
    print(f"Writing audit log to {log_path}...")
    with open(log_path, "w") as f:
        f.write(f"User ID: {user_id}\n")
        f.write(f"Memory ID: {memory_id}\n")
        f.write(f"Events JSON: {json.dumps(history_res)}\n")

    print("Done! Audit log successfully written.")

if __name__ == "__main__":
    main()
