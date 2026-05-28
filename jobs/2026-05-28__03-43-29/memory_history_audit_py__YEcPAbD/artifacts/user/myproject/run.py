import os
import json
import time
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id = os.environ.get("ZEALT_RUN_ID", "default_run")
    user_id = f"harbor-history-{run_id}"

    client = MemoryClient(api_key=api_key)

    # Seed the user profile
    messages = [
        {"role": "user", "content": f"Hi, I just started my new job as a junior engineer at TechCorp today! (Run: {run_id})"},
        {"role": "assistant", "content": "Congratulations on your new role as a junior engineer at TechCorp! How can I help you today?"}
    ]

    print("Adding memory...")
    client.add(messages, user_id=user_id)
    
    # Wait for the background processing
    target_memory = None
    for _ in range(10):
        time.sleep(3)
        memories_response = client.get_all(filters={"user_id": user_id})
        memories = memories_response.get("results", [])
        for m in memories:
            if "junior engineer" in m.get("memory", "").lower():
                target_memory = m
                break
        if target_memory:
            break
            
    if not target_memory:
        memories_response = client.get_all(filters={"user_id": user_id})
        memories = memories_response.get("results", [])
        if memories:
            target_memory = memories[0]
        else:
            raise Exception("No memory found to update after waiting")

    memory_id = target_memory["id"]
    print(f"Target memory ID: {memory_id}")

    # Update memory
    new_text = f"User has been promoted to a senior engineer at TechCorp. (Run: {run_id})"
    client.update(memory_id=memory_id, text=new_text, metadata={"role": "senior"})
    
    # Give it a tiny bit of time to ensure history is updated
    history = []
    for _ in range(5):
        time.sleep(2)
        history = client.history(memory_id)
        has_add = any(e.get("event") == "ADD" for e in history)
        has_update = any(e.get("event") == "UPDATE" for e in history)
        if has_add and has_update:
            break
            
    # Write to log
    log_path = "/home/user/myproject/output.log"
    with open(log_path, "w") as f:
        f.write(f"User ID: {user_id}\n")
        f.write(f"Memory ID: {memory_id}\n")
        f.write(f"Events JSON: {json.dumps(history)}\n")

    print("Audit log generated successfully.")

if __name__ == "__main__":
    main()
