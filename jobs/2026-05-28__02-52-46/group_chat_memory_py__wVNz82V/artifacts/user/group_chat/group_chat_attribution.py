import os
import time
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id_suffix = os.environ.get("ZEALT_RUN_ID")
    
    if not api_key:
        print("Error: MEM0_API_KEY not set")
        return
    if not run_id_suffix:
        print("Error: ZEALT_RUN_ID not set")
        return

    client = MemoryClient(api_key=api_key)
    
    session_run_id = f"planning-v4-{run_id_suffix}"
    u1 = f"alice-v4-{run_id_suffix}"
    u2 = f"bob-v4-{run_id_suffix}"
    u3 = f"charlie-v4-{run_id_suffix}"
    a1 = f"facilitator-v4-{run_id_suffix}"

    messages = [
        {"role": "user", "content": "I prefer using React for the frontend because of its ecosystem.", "name": u1, "user_id": u1},
        {"role": "user", "content": "I think we should use PostgreSQL for our primary database to ensure data integrity.", "name": u2, "user_id": u2},
        {"role": "user", "content": "I suggest we deploy on AWS using EKS for scalability.", "name": u3, "user_id": u3},
        {"role": "assistant", "content": "I will record that we decided on React, PostgreSQL and AWS. Also, I think we should use Python for the backend.", "name": a1, "agent_id": a1}
    ]

    print(f"Adding conversation to session: {session_run_id}")
    response = client.add(messages, run_id=session_run_id)
    print(f"Add response: {response}")
    
    # Wait for memories to be processed
    print("Waiting for memories to be extracted...")
    
    participants = [
        ("user", u1),
        ("user", u2),
        ("user", u3),
        ("agent", a1)
    ]
    
    memories_found = {}
    timeout = 300  # 5 minutes timeout
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        all_ready = True
        for role_type, pid in participants:
            if pid in memories_found:
                continue
            
            filters = {role_type + "_id": pid}
            response = client.get_all(filters=filters)
            
            mems = []
            if isinstance(response, dict):
                mems = response.get("results", [])
            elif isinstance(response, list):
                mems = response
                
            if mems:
                print(f"Found memories for {pid}: {mems}")
                extracted = []
                for m in mems:
                    if isinstance(m, dict):
                        extracted.append(m.get("memory") or m.get("text"))
                    elif isinstance(m, str):
                        extracted.append(m)
                if extracted:
                    memories_found[pid] = extracted
                else:
                    all_ready = False
            else:
                all_ready = False
        
        if all_ready:
            break
        
        print("Still waiting for some memories...")
        time.sleep(10)

    # Write output log
    log_path = "/home/user/group_chat/output.log"
    with open(log_path, "w") as f:
        f.write(f"Session: {session_run_id}\n")
        for role_type, pid in participants:
            mems = memories_found.get(pid, [])
            prefix = "User memory" if role_type == "user" else "Agent memory"
            for m in mems:
                f.write(f"{prefix}: {pid} :: {m}\n")
    
    print(f"Log written to {log_path}")

if __name__ == "__main__":
    main()
