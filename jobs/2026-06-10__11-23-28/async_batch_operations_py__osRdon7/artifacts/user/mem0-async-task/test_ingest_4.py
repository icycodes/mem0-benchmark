import os
import sys
import asyncio
from mem0 import AsyncMemoryClient

async def main():
    run_id = os.environ.get("ZEALT_RUN_ID")
    client = AsyncMemoryClient()
    
    user_id = f"athlete-{run_id}"
    agent_id = f"coach-{run_id}"
    app_id = f"fitness-app-{run_id}"
    session_id = f"session-{run_id}"
    
    memories_to_add = [
        [{"role": "user", "content": "I run 5 kilometers every Tuesday morning."}],
        [{"role": "user", "content": "I do strength training with kettlebells on Thursdays."}],
        [{"role": "user", "content": "I prefer plant-based protein shakes after workouts."}],
        [{"role": "user", "content": "My resting heart rate is around 58 bpm."}]
    ]
    
    print("Adding 4 memories concurrently...")
    tasks = [
        client.add(messages=msg, user_id=user_id, agent_id=agent_id, app_id=app_id, run_id=session_id)
        for msg in memories_to_add
    ]
    results = await asyncio.gather(*tasks)
    print("Add results:", results)
    
    print("Waiting for extraction...")
    filters_three = {
        "AND": [
            {"user_id": user_id},
            {"app_id": app_id},
            {"run_id": session_id}
        ]
    }
    
    for i in range(12):
        res = await client.get_all(filters=filters_three)
        memories = res.get("results", [])
        print(f"Attempt {i+1}: Retrieved {len(memories)} memories")
        if len(memories) >= 4:
            for m in memories:
                print(m.get("id"), "->", m.get("memory"))
            break
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
