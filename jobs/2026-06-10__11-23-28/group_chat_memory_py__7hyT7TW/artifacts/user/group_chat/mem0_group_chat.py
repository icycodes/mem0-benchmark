import os
import sys
import time
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    zealt_run_id = os.environ.get("ZEALT_RUN_ID")

    if not api_key:
        print("Error: MEM0_API_KEY environment variable is not set.")
        sys.exit(1)
    if not zealt_run_id:
        print("Error: ZEALT_RUN_ID environment variable is not set.")
        sys.exit(1)

    print(f"Initializing MemoryClient with API key ending in ...{api_key[-4:]}")
    client = MemoryClient(api_key=api_key)

    session_run_id = f"planning-{zealt_run_id}"
    alice_id = f"alice-{zealt_run_id}"
    bob_id = f"bob-{zealt_run_id}"
    charlie_id = f"charlie-{zealt_run_id}"
    facilitator_id = f"facilitator-{zealt_run_id}"

    # Construct the group chat conversation
    messages = [
        {
            "role": "user",
            "name": alice_id,
            "content": f"Hi team, I prefer to schedule our weekly status meetings on Tuesday mornings at 10 AM because that is when I am most productive and focused."
        },
        {
            "role": "user",
            "name": bob_id,
            "content": f"Tuesday at 10 AM works for me. Please keep in mind that I work exclusively with Python and PostgreSQL for backend development, so I cannot take any Node.js tasks."
        },
        {
            "role": "user",
            "name": charlie_id,
            "content": f"I can also make Tuesday at 10 AM work. I want to highlight that my primary goal for this quarter is to improve our overall test coverage to at least 90%."
        },
        {
            "role": "assistant",
            "name": facilitator_id,
            "content": f"Understood. As your meeting facilitator, I prefer to use Zoom for all our video calls and will always document our decisions in Notion. I will send out the Tuesday 10 AM calendar invites shortly."
        }
    ]

    print(f"Adding group chat conversation to session {session_run_id}...")
    add_response = client.add(
        messages=messages,
        run_id=session_run_id,
        infer=True
    )
    print("Add Response:", add_response)

    print("Polling Mem0 Platform for extracted memories...")
    
    participants = {
        "user": [alice_id, bob_id, charlie_id],
        "agent": [facilitator_id]
    }

    memories_by_participant = {}
    timeout = 300  # 5 minutes timeout
    start_time = time.time()

    while time.time() - start_time < timeout:
        all_found = True
        
        # Check users
        for user_id in participants["user"]:
            if user_id not in memories_by_participant:
                try:
                    res = client.get_all(filters={"user_id": user_id})
                    results = res.get("results", [])
                    if results:
                        memories_by_participant[user_id] = [r["memory"] for r in results]
                        print(f"Found memories for user {user_id}: {memories_by_participant[user_id]}")
                    else:
                        all_found = False
                except Exception as e:
                    print(f"Error fetching memories for user {user_id}: {e}")
                    all_found = False
                    
        # Check agents
        for agent_id in participants["agent"]:
            if agent_id not in memories_by_participant:
                try:
                    res = client.get_all(filters={"agent_id": agent_id})
                    results = res.get("results", [])
                    if results:
                        memories_by_participant[agent_id] = [r["memory"] for r in results]
                        print(f"Found memories for agent {agent_id}: {memories_by_participant[agent_id]}")
                    else:
                        all_found = False
                except Exception as e:
                    print(f"Error fetching memories for agent {agent_id}: {e}")
                    all_found = False

        if all_found:
            print("All participant memories successfully extracted and retrieved!")
            break

        print("Some memories are not yet available. Retrying in 10 seconds...")
        time.sleep(10)

    # Ensure output directory exists (though /home/user/group_chat is expected to exist)
    os.makedirs("/home/user/group_chat", exist_ok=True)
    log_path = "/home/user/group_chat/output.log"

    print(f"Writing memories to log file: {log_path}")
    with open(log_path, "w") as f:
        f.write(f"Session: {session_run_id}\n")
        
        # Write user memories
        for user_id in participants["user"]:
            mems = memories_by_participant.get(user_id, [])
            if mems:
                for mem in mems:
                    f.write(f"User memory: {user_id} :: {mem}\n")
            else:
                f.write(f"User memory: {user_id} :: [No memory extracted within timeout]\n")

        # Write agent memories
        for agent_id in participants["agent"]:
            mems = memories_by_participant.get(agent_id, [])
            if mems:
                for mem in mems:
                    f.write(f"Agent memory: {agent_id} :: {mem}\n")
            else:
                f.write(f"Agent memory: {agent_id} :: [No memory extracted within timeout]\n")

    print("Log writing complete. Contents of output.log:")
    with open(log_path, "r") as f:
        print(f.read())

if __name__ == "__main__":
    main()
