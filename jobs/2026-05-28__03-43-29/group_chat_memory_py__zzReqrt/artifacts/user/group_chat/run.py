import os
import time
from mem0 import MemoryClient

def main():
    run_id = os.environ.get("ZEALT_RUN_ID", "default_run")
    api_key = os.environ.get("MEM0_API_KEY")
    
    if not api_key:
        print("MEM0_API_KEY not set")
        return

    client = MemoryClient(api_key=api_key)
    
    session_id = f"planning-{run_id}"
    
    alice = f"alice-{run_id}"
    bob = f"bob-{run_id}"
    charlie = f"charlie-{run_id}"
    agent = f"facilitator-{run_id}"
    
    messages = [
        {"role": "user", "name": alice, "content": "I prefer using Python for our backend services because I know it well."},
        {"role": "user", "name": bob, "content": "I want to use PostgreSQL as our primary database since I have a lot of experience with it."},
        {"role": "user", "name": charlie, "content": "I think we should deploy on AWS. I've used it in all my previous projects."},
        {"role": "assistant", "name": agent, "content": "I will ensure that our infrastructure scripts are written in Terraform and target AWS, while setting up a PostgreSQL RDS instance and a Python backend."}
    ]
    
    print(f"Adding messages for session {session_id}...")
    # Add messages
    client.add(messages, run_id=session_id)
    
    # Poll for memories
    users = [alice, bob, charlie]
    
    extracted_memories = {u: [] for u in users}
    extracted_memories[agent] = []
    
    max_retries = 30
    for i in range(max_retries):
        all_found = True
        
        # Check users
        for u in users:
            if not extracted_memories[u]:
                res = client.get_all(filters={"user_id": u})
                
                mems = res.get("results", []) if isinstance(res, dict) else res
                if isinstance(mems, list) and len(mems) > 0:
                    extracted_memories[u] = mems
                else:
                    all_found = False
                    
        # Check agent
        if not extracted_memories[agent]:
            res = client.get_all(filters={"agent_id": agent})
            mems = res.get("results", []) if isinstance(res, dict) else res
            if isinstance(mems, list) and len(mems) > 0:
                extracted_memories[agent] = mems
            else:
                all_found = False
                
        if all_found:
            print("All memories extracted!")
            break
            
        print("Waiting for memories to be extracted...")
        time.sleep(3)
        
    # Write to log
    with open("output.log", "w") as f:
        f.write(f"Session: {session_id}\n")
        
        for u in users:
            for m in extracted_memories[u]:
                text = m.get("memory", m.get("text", str(m)))
                f.write(f"User memory: {u} :: {text}\n")
                
        for m in extracted_memories[agent]:
            text = m.get("memory", m.get("text", str(m)))
            f.write(f"Agent memory: {agent} :: {text}\n")

if __name__ == "__main__":
    main()
