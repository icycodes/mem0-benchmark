import os
import json
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    client = MemoryClient(api_key=api_key)

    history = client.history("419f036b-429c-48e3-9139-7b932b7b460c")
    print("History:", json.dumps(history, indent=2))

if __name__ == "__main__":
    main()
