import os
import sys
import asyncio
from mem0 import AsyncMemoryClient

async def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id = os.environ.get("ZEALT_RUN_ID")
    print("API KEY exists:", bool(api_key))
    print("RUN ID:", run_id)
    
    client = AsyncMemoryClient()
    # Let's test adding a simple memory
    user_id = f"test-user-{run_id}"
    agent_id = f"test-agent-{run_id}"
    app_id = f"test-app-{run_id}"
    session_id = f"test-session-{run_id}"
    
    print("Adding memory...")
    res = await client.add(
        messages="I love running on Tuesdays",
        user_id=user_id,
        agent_id=agent_id,
        app_id=app_id,
        run_id=session_id
    )
    print("Add response:", res)
    
    print("Getting all memories...")
    filters = {
        "AND": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": session_id}
        ]
    }
    get_res = await client.get_all(filters=filters)
    print("Get response type:", type(get_res))
    print("Get response:", get_res)

if __name__ == "__main__":
    asyncio.run(main())
