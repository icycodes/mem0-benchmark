import os
import sys
import json
import time
from typing import Optional
from pydantic import BaseModel
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id_env = os.environ.get("ZEALT_RUN_ID")
    
    if not api_key or not run_id_env:
        print("Missing MEM0_API_KEY or ZEALT_RUN_ID", file=sys.stderr)
        sys.exit(1)
        
    print(f"RUN_ID: {run_id_env}", flush=True)
    
    user_id = f"lead-{run_id_env}"
    agent_id = f"csm-{run_id_env}"
    run_id = f"intake-{run_id_env}"
    
    client = MemoryClient(api_key=api_key)
    
    messages = [
        [{"role": "user", "content": "Hi, my name is Priya Shah and I work as a Senior Data Engineer at Helios Robotics."}],
        [{"role": "user", "content": "I'm based in Bengaluru and I've been at Helios for about 4 years."}],
        [{"role": "user", "content": "I have a Master's degree in Computer Science from IIT Bombay."}],
        [{"role": "user", "content": "You can reach me at priya.shah@helios-robotics.example and my LinkedIn handle is priya-shah-de."}]
    ]
    
    for msg in messages:
        client.add(messages=msg, user_id=user_id, agent_id=agent_id, run_id=run_id)
        
    # Wait for Mem0 server-side extraction to complete
    print("Waiting 60 seconds for memories to be extracted...", file=sys.stderr, flush=True)
    time.sleep(60)
    
    class LeadProfile(BaseModel):
        full_name: Optional[str]
        current_role: Optional[str]
        current_company: Optional[str]
        location: Optional[str]
        years_at_company: Optional[int]
        education: Optional[str]
        contact_email: Optional[str]
        
    schema = LeadProfile.model_json_schema()
    
    filters = {
        "AND": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"run_id": run_id}
        ]
    }
    
    create_resp = client.create_memory_export(schema=schema, filters=filters)
    
    with open("/home/user/mem0-export-task/create_export_response.json", "w") as f:
        json.dump(create_resp, f, indent=2)
        
    export_id = create_resp.get("id")
    if not export_id:
        print("No export ID returned", file=sys.stderr)
        sys.exit(1)
        
    print(f"EXPORT_ID: {export_id}", flush=True)
    
    # Poll for export
    max_retries = 24
    get_resp = None
    for i in range(max_retries):
        get_resp = client.get_memory_export(memory_export_id=export_id)
        print(f"Poll {i}: {get_resp}", file=sys.stderr, flush=True)
        
        if isinstance(get_resp, dict):
            if get_resp.get("status") in ["processing", "pending", "in_progress"]:
                time.sleep(5)
                continue
            
            profile = get_resp
            if "data" in profile and isinstance(profile["data"], dict):
                profile = profile["data"]
            elif "export" in profile and isinstance(profile["export"], dict):
                profile = profile["export"]
            elif "result" in profile and isinstance(profile["result"], dict):
                profile = profile["result"]
                
            if profile.get("full_name") is not None:
                break
                
            if get_resp.get("status") == "completed":
                break
                
        time.sleep(5)
    else:
        print("Export not ready or returned empty", file=sys.stderr)
        sys.exit(1)
        
    print("EXPORT_STATUS: ready", flush=True)
    
    with open("/home/user/mem0-export-task/get_export_response.json", "w") as f:
        json.dump(get_resp, f, indent=2)
        
    profile_data = get_resp
    if "data" in profile_data and isinstance(profile_data["data"], dict):
        profile_data = profile_data["data"]
    elif "export" in profile_data and isinstance(profile_data["export"], dict):
        profile_data = profile_data["export"]
    elif "result" in profile_data and isinstance(profile_data["result"], dict):
        profile_data = profile_data["result"]
        
    lead_profile = {
        "user_id": user_id,
        "agent_id": agent_id,
        "run_id": run_id,
        "export_id": export_id,
        "profile": profile_data
    }
    
    with open("/home/user/mem0-export-task/lead_profile.json", "w") as f:
        json.dump(lead_profile, f, indent=2)
        
    print(f"FULL_NAME: {profile_data.get('full_name')}", flush=True)
    print(f"CURRENT_COMPANY: {profile_data.get('current_company')}", flush=True)
    print(f"LOCATION: {profile_data.get('location')}", flush=True)

if __name__ == "__main__":
    main()
