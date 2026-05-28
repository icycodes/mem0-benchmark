import os
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id = os.environ.get("ZEALT_RUN_ID", "default_run")
    client = MemoryClient(api_key=api_key)
    
    alice = f"alice_{run_id}"
    print(f"Checking for {alice}")
    res = client.get_all(filters={"user_id": alice})
    print(res)

if __name__ == "__main__":
    main()