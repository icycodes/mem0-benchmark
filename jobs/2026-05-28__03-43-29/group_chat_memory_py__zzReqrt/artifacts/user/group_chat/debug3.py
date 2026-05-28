import os
from mem0 import MemoryClient
import json

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id = os.environ.get("ZEALT_RUN_ID", "default_run")
    client = MemoryClient(api_key=api_key)
    session_id = f"planning-{run_id}"
    print(f"Checking for run_id {session_id}")
    res = client.get_all(filters={"run_id": session_id})
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()