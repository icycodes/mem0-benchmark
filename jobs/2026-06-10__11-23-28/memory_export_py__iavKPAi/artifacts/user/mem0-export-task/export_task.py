import os
import sys
import json
import time
from typing import Optional
from pydantic import BaseModel
from mem0 import MemoryClient

def main():
    # 1. Read and validate environment variables
    api_key = os.environ.get("MEM0_API_KEY")
    zealt_run_id = os.environ.get("ZEALT_RUN_ID")

    if not api_key:
        sys.exit("Error: MEM0_API_KEY environment variable is missing")
    if not zealt_run_id:
        sys.exit("Error: ZEALT_RUN_ID environment variable is missing")

    # 2. Derive entity IDs
    user_id = f"lead-{zealt_run_id}"
    agent_id = f"csm-{zealt_run_id}"
    run_id = f"intake-{zealt_run_id}"

    # 3. Initialize MemoryClient
    client = MemoryClient(api_key=api_key)

    # 4. Ingest conversational memories
    messages_list = [
        [{"role": "user", "content": "Hi, my name is Priya Shah and I work as a Senior Data Engineer at Helios Robotics."}],
        [{"role": "user", "content": "I'm based in Bengaluru and I've been at Helios for about 4 years."}],
        [{"role": "user", "content": "I have a Master's degree in Computer Science from IIT Bombay."}],
        [{"role": "user", "content": "You can reach me at priya.shah@helios-robotics.example and my LinkedIn handle is priya-shah-de."}]
    ]

    print("Ingesting memories...", file=sys.stderr)
    for idx, messages in enumerate(messages_list, 1):
        print(f"Adding memory {idx}/4...", file=sys.stderr)
        add_res = client.add(messages, user_id=user_id, agent_id=agent_id, run_id=run_id)
        print(f"Add response: {add_res}", file=sys.stderr)

    # 5. Wait/poll get_all until at least 3 memories are processed/extracted
    print("Waiting for memories to be processed on the server...", file=sys.stderr)
    max_get_all_retries = 10
    get_all_success = False
    filters = {
        "AND": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"run_id": run_id}
        ]
    }

    for i in range(max_get_all_retries):
        # Use a fresh client instance to verify server-side effects under same scope
        fresh_client = MemoryClient(api_key=api_key)
        try:
            res = fresh_client.get_all(filters=filters, version="v2")
            memories = res.get("results", [])
            print(f"get_all Attempt {i+1}: Found {len(memories)} memories on server.", file=sys.stderr)
            if len(memories) >= 3:
                get_all_success = True
                break
        except Exception as e:
            print(f"get_all Attempt {i+1} failed with error: {e}. Proceeding with fallback sleep.", file=sys.stderr)
            time.sleep(15)
            break
        time.sleep(5)

    # 6. Define Pydantic schema
    class LeadProfile(BaseModel):
        full_name: Optional[str] = None
        current_role: Optional[str] = None
        current_company: Optional[str] = None
        location: Optional[str] = None
        years_at_company: Optional[int] = None
        education: Optional[str] = None
        contact_email: Optional[str] = None

    schema_dict = LeadProfile.model_json_schema()

    # 7. Submit memory export job
    print("Creating memory export job...", file=sys.stderr)
    create_response = client.create_memory_export(schema=schema_dict, filters=filters)
    print(f"Create Export response: {create_response}", file=sys.stderr)

    # Verify create_response structure
    export_id = create_response.get("id")
    if not export_id:
        sys.exit(f"Error: create_memory_export did not return an ID. Response: {create_response}")

    # Save raw create response
    os.makedirs("/home/user/mem0-export-task", exist_ok=True)
    with open("/home/user/mem0-export-task/create_export_response.json", "w") as f:
        json.dump(create_response, f, indent=2)

    # 8. Poll get_memory_export
    print(f"Polling memory export {export_id}...", file=sys.stderr)
    max_poll_retries = 24  # 24 * 5 = 120 seconds
    get_export_response = None
    profile = None

    for i in range(max_poll_retries):
        try:
            get_res = client.get_memory_export(memory_export_id=export_id, filters=filters)
            print(f"Poll Attempt {i+1} response: {get_res}", file=sys.stderr)
            
            # Check if get_res contains the structured fields
            # The structured fields could be wrapped or direct. Let's check.
            target_keys = ["full_name", "current_role", "current_company", "location", "education", "contact_email"]
            
            # Let's extract the profile if present
            # 1. Check top level
            direct_match_count = sum(1 for k in target_keys if get_res.get(k))
            if direct_match_count >= 3:
                profile = {k: get_res.get(k) for k in target_keys}
                get_export_response = get_res
                break
                
            # 2. Check wrappers like "data", "export", "result"
            found_wrapper = False
            for wrapper in ["data", "export", "result"]:
                if wrapper in get_res and isinstance(get_res[wrapper], dict):
                    wrapper_dict = get_res[wrapper]
                    match_count = sum(1 for k in target_keys if wrapper_dict.get(k))
                    if match_count >= 3:
                        profile = {k: wrapper_dict.get(k) for k in target_keys}
                        get_export_response = get_res
                        found_wrapper = True
                        break
            if found_wrapper:
                break
                
        except Exception as e:
            print(f"Poll Attempt {i+1} failed with error: {e}", file=sys.stderr)
            
        time.sleep(5)

    if not profile or not get_export_response:
        sys.exit("Error: Memory export is still not ready or failed to extract structured fields after 120 seconds.")

    # 9. Save raw get response
    with open("/home/user/mem0-export-task/get_export_response.json", "w") as f:
        json.dump(get_export_response, f, indent=2)

    # 10. Save normalized profile artifact
    lead_profile_data = {
        "user_id": user_id,
        "agent_id": agent_id,
        "run_id": run_id,
        "export_id": export_id,
        "profile": profile
    }
    with open("/home/user/mem0-export-task/lead_profile.json", "w") as f:
        json.dump(lead_profile_data, f, indent=2)

    # 11. Write stdout log requirements (this script's stdout will be redirected to output.log)
    print(f"RUN_ID: {zealt_run_id}")
    print(f"EXPORT_ID: {export_id}")
    print(f"EXPORT_STATUS: ready")
    print(f"FULL_NAME: {profile.get('full_name')}")
    print(f"CURRENT_COMPANY: {profile.get('current_company')}")
    print(f"LOCATION: {profile.get('location')}")

if __name__ == "__main__":
    main()
