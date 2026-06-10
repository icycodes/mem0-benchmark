import os
from mem0 import MemoryClient

api_key = os.environ.get("MEM0_API_KEY")
zealt_run_id = os.environ.get("ZEALT_RUN_ID")
client = MemoryClient(api_key=api_key)

print("Checking memories for run_id:", f"planning-{zealt_run_id}")
try:
    res = client.get_all(filters={"run_id": f"planning-{zealt_run_id}"})
    print("get_all by run_id results:")
    for r in res.get("results", []):
        print(f"Memory: {r.get('memory')} | User: {r.get('user_id')} | Agent: {r.get('agent_id')}")
except Exception as e:
    print("Error:", e)

print("\nChecking memories for user_id wildcard:")
try:
    res = client.get_all(filters={"AND": [{"user_id": "*"}, {"run_id": f"planning-{zealt_run_id}"}]})
    print("get_all with wildcard results:")
    for r in res.get("results", []):
        print(f"Memory: {r.get('memory')} | User: {r.get('user_id')} | Agent: {r.get('agent_id')}")
except Exception as e:
    print("Error:", e)

print("\nChecking memories for each participant:")
for p in [f"alice-{zealt_run_id}", f"bob-{zealt_run_id}", f"charlie-{zealt_run_id}"]:
    try:
        res = client.get_all(filters={"user_id": p})
        print(f"User {p} memories:")
        for r in res.get("results", []):
            print(f"- {r.get('memory')}")
    except Exception as e:
        print("Error:", e)

try:
    p = f"facilitator-{zealt_run_id}"
    res = client.get_all(filters={"agent_id": p})
    print(f"Agent {p} memories:")
    for r in res.get("results", []):
        print(f"- {r.get('memory')}")
except Exception as e:
    print("Error:", e)
