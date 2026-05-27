import os
from mem0 import MemoryClient

api_key = os.environ.get("MEM0_API_KEY")
run_id = os.environ.get("ZEALT_RUN_ID")
client = MemoryClient(api_key=api_key)
res = client.get_all(filters={"run_id": f"planning-{run_id}"})
for m in res.get("results", []):
    print(f"Memory: {m.get('memory')}")
    for k, v in m.items():
        if v is not None:
            print(f"  {k}: {v}")
    print("-" * 20)
