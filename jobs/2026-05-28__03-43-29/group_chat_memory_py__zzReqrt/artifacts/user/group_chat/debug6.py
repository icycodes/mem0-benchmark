import os
import httpx
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id = os.environ.get("ZEALT_RUN_ID", "default_run")
    client = MemoryClient(api_key=api_key)
    session_id = f"planning-test3-{run_id}"
    
    alice = f"alice_{run_id}"  # try underscore instead of hyphen
    
    messages = [
        {"role": "user", "name": alice, "content": "I prefer using Python for our backend services because I know it well."}
    ]
    
    res = client.add(messages, run_id=session_id)
    print("Add response:", res)

if __name__ == "__main__":
    main()