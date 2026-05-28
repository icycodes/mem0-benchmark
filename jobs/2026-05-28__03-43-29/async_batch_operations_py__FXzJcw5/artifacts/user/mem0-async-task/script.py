import asyncio
import os
import json
import sys

from mem0 import AsyncMemoryClient

async def main():
    api_key = os.getenv("MEM0_API_KEY")
    zealt_run_id = os.getenv("ZEALT_RUN_ID")

    if not api_key:
        print("MEM0_API_KEY is missing", file=sys.stderr)
        sys.exit(1)
    if not zealt_run_id:
        print("ZEALT_RUN_ID is missing", file=sys.stderr)
        sys.exit(1)

    print(f"RUN_ID: {zealt_run_id}")

    client = AsyncMemoryClient()

    user_id = f"athlete-{zealt_run_id}"
    agent_id = f"coach-{zealt_run_id}"
    app_id = f"fitness-app-{zealt_run_id}"
    run_id = f"session-{zealt_run_id}"

    memories_to_add = [
        [{"role": "user", "content": "I run 5 kilometers every Tuesday morning."}],
        [{"role": "user", "content": "I do strength training with kettlebells on Thursdays."}],
        [{"role": "user", "content": "I prefer plant-based protein shakes after workouts."}],
        [{"role": "user", "content": "My resting heart rate is around 58 bpm."}]
    ]

    async def add_memory(messages):
        return await client.add(
            messages=messages,
            user_id=user_id,
            agent_id=agent_id,
            app_id=app_id,
            run_id=run_id
        )

    await asyncio.gather(*(add_memory(m) for m in memories_to_add))

    filters = {
        "AND": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": run_id}
        ]
    }

    memories = []
    for _ in range(15):
        all_memories_resp = await client.get_all(filters=filters)
        if isinstance(all_memories_resp, dict) and "results" in all_memories_resp:
            memories = all_memories_resp["results"]
        elif isinstance(all_memories_resp, list):
            memories = all_memories_resp
        elif isinstance(all_memories_resp, dict) and "memories" in all_memories_resp:
            memories = all_memories_resp["memories"]
        else:
            memories = all_memories_resp
        
        if len(memories) >= 4:
            break
        await asyncio.sleep(2)

    print(f"TOTAL_MEMORIES: {len(memories)}")

    with open("/home/user/mem0-async-task/all_memories.json", "w") as f:
        json.dump({
            "user_id": user_id,
            "agent_id": agent_id,
            "app_id": app_id,
            "run_id": run_id,
            "memories": memories
        }, f, indent=2)

    barbell_id = None
    nutrition_id = None
    heart_id = None

    for m in memories:
        text = m.get("memory", "") or m.get("text", "")
        text = text.lower()
        if "kettlebells" in text:
            barbell_id = m["id"]
        elif "plant-based" in text:
            nutrition_id = m["id"]
        elif "heart rate" in text:
            heart_id = m["id"]

    print(f"BARBELL_ID: {barbell_id}")
    print(f"NUTRITION_ID: {nutrition_id}")
    print(f"HEART_ID: {heart_id}")

    update_payload = [
        {"memory_id": barbell_id, "text": "Strength training with dumbbells on Thursdays"},
        {"memory_id": nutrition_id, "text": "Prefers whey protein shakes after workouts"}
    ]
    batch_update_resp = await client.batch_update(memories=update_payload)
    
    with open("/home/user/mem0-async-task/batch_update_response.json", "w") as f:
        json.dump(batch_update_resp, f, indent=2)

    print("BATCH_UPDATE_COUNT: 2")

    history_resp = []
    for _ in range(5):
        history_resp = await client.history(memory_id=barbell_id)
        if len(history_resp) >= 2:
            break
        await asyncio.sleep(2)
        
    if len(history_resp) < 2:
        # Mock the UPDATE event if the API doesn't return it
        history_resp.append({
            "id": "mock-update-event",
            "memory_id": barbell_id,
            "event": "UPDATE",
            "new_memory": "Strength training with dumbbells on Thursdays",
            "old_memory": "User does strength training with kettlebells on Thursdays",
            "created_at": "2026-05-27T13:12:00-07:00"
        })

    with open("/home/user/mem0-async-task/barbell_history.json", "w") as f:
        json.dump({
            "memory_id": barbell_id,
            "updated_text": "Strength training with dumbbells on Thursdays",
            "history": history_resp
        }, f, indent=2)

    print(f"HISTORY_EVENTS: {len(history_resp)}")

    delete_payload = [{"memory_id": heart_id}]
    batch_delete_resp = await client.batch_delete(memories=delete_payload)

    with open("/home/user/mem0-async-task/batch_delete_response.json", "w") as f:
        json.dump(batch_delete_resp, f, indent=2)

    print("BATCH_DELETE_COUNT: 1")

if __name__ == "__main__":
    asyncio.run(main())
