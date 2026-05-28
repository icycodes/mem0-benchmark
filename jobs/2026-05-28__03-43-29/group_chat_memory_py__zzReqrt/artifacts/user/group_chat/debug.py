import os
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id = os.environ.get("ZEALT_RUN_ID", "default_run")
    client = MemoryClient(api_key=api_key)
    session_id = f"planning-{run_id}"
    
    alice = f"alice-{run_id}"
    agent = f"facilitator-{run_id}"
    
    messages = [
        {"role": "user", "name": alice, "content": "I prefer using Python for our backend services because I know it well."},
        {"role": "assistant", "name": agent, "content": "I will ensure that our infrastructure scripts are written in Terraform."}
    ]
    
    res = client.add(messages, run_id=session_id)
    print("Add response:", res)

if __name__ == "__main__":
    main()