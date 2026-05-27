import os
import sys
import json
import time
from typing import Optional
from pydantic import BaseModel
from mem0 import MemoryClient

def main():
    # 1. Environment variables
    api_key = os.environ.get("MEM0_API_KEY")
    zealt_run_id = os.environ.get("ZEALT_RUN_ID")

    if not api_key:
        print("Error: MEM0_API_KEY is missing", file=sys.stderr)
        sys.exit(1)
    if not zealt_run_id:
        print("Error: ZEALT_RUN_ID is missing", file=sys.stderr)
        sys.exit(1)

    print(f"RUN_ID: {zealt_run_id}")

    # Derive entity IDs
    user_id = f"lead-{zealt_run_id}"
    agent_id = f"csm-{zealt_run_id}"
    run_id = f"intake-{zealt_run_id}"

    client = MemoryClient(api_key=api_key)

    # 2. Ingest memories
    messages_list = [
        [{"role": "user", "content": "Hi, my name is Priya Shah and I work as a Senior Data Engineer at Helios Robotics."}],
        [{"role": "user", "content": "I'm based in Bengaluru and I've been at Helios for about 4 years."}],
        [{"role": "user", "content": "I have a Master's degree in Computer Science from IIT Bombay."}],
        [{"role": "user", "content": "You can reach me at priya.shah@helios-robotics.example and my LinkedIn handle is priya-shah-de."}]
    ]

    for messages in messages_list:
        client.add(messages=messages, user_id=user_id, agent_id=agent_id, run_id=run_id)
        print(f"Added memory: {messages[0]['content']}")

    # Wait a bit for server-side extraction
    print("Waiting for server-side extraction...")
    time.sleep(30)

    # 3. Define Pydantic schema
    class LeadProfile(BaseModel):
        full_name: Optional[str] = None
        current_role: Optional[str] = None
        current_company: Optional[str] = None
        location: Optional[str] = None
        years_at_company: Optional[int] = None
        education: Optional[str] = None
        contact_email: Optional[str] = None

    schema_dict = LeadProfile.model_json_schema()

    # 4. Submit memory export job
    filters = {
        "AND": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"run_id": run_id}
        ]
    }

    create_response = client.create_memory_export(schema=schema_dict, filters=filters)
    
    # Save create_export_response.json
    artifact_dir = "/home/user/mem0-export-task"
    os.makedirs(artifact_dir, exist_ok=True)
    with open(f"{artifact_dir}/create_export_response.json", "w") as f:
        json.dump(create_response, f, indent=2)

    export_id = create_response.get("id")
    if not export_id:
        print("Error: Export ID not found in response", file=sys.stderr)
        sys.exit(1)

    print(f"EXPORT_ID: {export_id}")

    # 5. Poll export status
    max_retries = 24 # 24 * 5s = 120s
    ready = False
    get_response = {}
    
    for i in range(max_retries):
        get_response = client.get_memory_export(memory_export_id=export_id)
        
        # Check if structured data is available
        profile_data = None
        if isinstance(get_response, dict):
            # Check for common wrappers
            for key in ["data", "export", "result"]:
                if key in get_response and isinstance(get_response[key], dict):
                    potential_profile = get_response[key]
                    if any(potential_profile.get(k) is not None for k in schema_dict["properties"]):
                        profile_data = potential_profile
                        break
            
            # If not wrapped, check if the response itself has the fields
            if profile_data is None:
                if any(get_response.get(k) is not None for k in schema_dict["properties"]):
                    profile_data = get_response
        
        if profile_data:
            ready = True
            break
            
        print(f"Polling export status... (attempt {i+1}/{max_retries})")
        time.sleep(5)

    if not ready:
        print("Error: Export job timed out or failed to return structured data", file=sys.stderr)
        sys.exit(1)

    print("EXPORT_STATUS: ready")
    
    # Extract profile fields for logging
    full_name = profile_data.get("full_name", "")
    current_company = profile_data.get("current_company", "")
    location = profile_data.get("location", "")
    
    print(f"FULL_NAME: {full_name}")
    print(f"CURRENT_COMPANY: {current_company}")
    print(f"LOCATION: {location}")

    # 6. Persist artifacts
    with open(f"{artifact_dir}/get_export_response.json", "w") as f:
        json.dump(get_response, f, indent=2)

    lead_profile = {
        "user_id": user_id,
        "agent_id": agent_id,
        "run_id": run_id,
        "export_id": export_id,
        "profile": profile_data
    }
    with open(f"{artifact_dir}/lead_profile.json", "w") as f:
        json.dump(lead_profile, f, indent=2)

    # 7. Verification of server-side effects
    # "client.get_all(...) returns at least 3 memories"
    memories = client.get_all(filters=filters, version="v2")
    print(f"Total memories found: {len(memories)}")

if __name__ == "__main__":
    main()
