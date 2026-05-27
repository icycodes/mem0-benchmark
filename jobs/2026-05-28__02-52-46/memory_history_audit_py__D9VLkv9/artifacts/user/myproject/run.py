import os
import json
import time
from mem0 import MemoryClient

def run():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id = os.environ.get("ZEALT_RUN_ID")
    
    if not api_key:
        print("MEM0_API_KEY not found")
        return
    if not run_id:
        print("ZEALT_RUN_ID not found")
        return

    user_id = f"harbor-history-{run_id}"
    client = MemoryClient(api_key=api_key)

    print(f"Adding memory for user: {user_id}")
    # Seed the user profile with a multi-turn conversation
    messages = [
        {"role": "user", "content": "Hi, I'm Alex. I just started as a junior software engineer at TechCorp."},
        {"role": "assistant", "content": "Welcome Alex! How is your first week going at TechCorp?"},
        {"role": "user", "content": "It's great, although I'm still learning the ropes of our legacy codebase. I love being a junior engineer here."},
    ]
    
    add_results = client.add(messages, user_id=user_id)
    print(f"Add results: {json.dumps(add_results, indent=2)}")
    
    target_memory = None
    
    # Wait for processing and fetch all memories
    print("Waiting and fetching all memories...")
    for _ in range(10):
        time.sleep(2)
        resp = client.get_all(filters={"user_id": user_id})
        print(f"All memories response count: {resp.get('count') if isinstance(resp, dict) else len(resp)}")
        
        results = []
        if isinstance(resp, dict) and "results" in resp:
            results = resp["results"]
        elif isinstance(resp, list):
            results = resp
        
        if results:
            for m in results:
                if isinstance(m, dict):
                    mem_text = m.get("memory", "").lower()
                    if "engineer" in mem_text or "junior" in mem_text or "techcorp" in mem_text:
                        target_memory = m
                        break
            if target_memory:
                break
            if results:
                target_memory = results[0]
                break
        print("Still waiting...")

    if not target_memory:
        print("Failed to find or create any memory.")
        return

    memory_id = target_memory["id"]
    print(f"Target Memory ID: {memory_id}")
    
    # Update the memory: promote to senior
    new_text = "Alex is now a senior software engineer at TechCorp, having been promoted from his junior role."
    new_metadata = {"seniority": "senior", "updated_by": "audit_script", "timestamp": time.time()}
    
    print(f"Updating memory {memory_id}...")
    client.update(memory_id=memory_id, text=new_text, metadata=new_metadata)
    
    # Wait a bit for history to update
    time.sleep(2)
    
    # Retrieve history
    print(f"Retrieving history for {memory_id}...")
    history = client.history(memory_id=memory_id)
    print(f"History: {json.dumps(history, indent=2)}")
    
    # Output to log
    output_path = "/home/user/myproject/output.log"
    with open(output_path, "w") as f:
        f.write(f"User ID: {user_id}\n")
        f.write(f"Memory ID: {memory_id}\n")
        f.write(f"Events JSON: {json.dumps(history)}\n")
    print(f"Done. Log written to {output_path}")

if __name__ == "__main__":
    run()
