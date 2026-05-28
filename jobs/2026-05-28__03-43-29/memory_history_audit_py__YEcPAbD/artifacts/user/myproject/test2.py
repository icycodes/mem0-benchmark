import os
import json
import time
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id = os.environ.get("ZEALT_RUN_ID", "test_run")
    user_id = f"harbor-history-{run_id}"

    client = MemoryClient(api_key=api_key)

    messages = [
        {"role": "user", "content": "Hi, I just started my new job as a junior engineer at TechCorp today!"}
    ]

    add_response = client.add(messages, user_id=user_id)
    print("Add response:", json.dumps(add_response, indent=2))
    
    time.sleep(5)
    
    memories = client.get_all(user_id=user_id)
    print("Memories:", json.dumps(memories, indent=2))

if __name__ == "__main__":
    main()
