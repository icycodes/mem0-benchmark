#!/usr/bin/env python3
import json
import os
import sys
import time
from typing import Optional, Dict, Any

from mem0 import MemoryClient
from pydantic import BaseModel


class LeadProfile(BaseModel):
    full_name: Optional[str]
    current_role: Optional[str]
    current_company: Optional[str]
    location: Optional[str]
    years_at_company: Optional[int]
    education: Optional[str]
    contact_email: Optional[str]


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def extract_profile(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    candidate_containers = [payload]
    for key in ("data", "export", "result", "profile"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidate_containers.append(value)

    fields = set(LeadProfile.model_fields.keys())

    for container in candidate_containers:
        if "profile" in container and isinstance(container["profile"], dict):
            profile_candidate = container["profile"]
            if fields.intersection(profile_candidate.keys()):
                return profile_candidate
        if fields.intersection(container.keys()):
            return container

    return None


def main() -> None:
    api_key = require_env("MEM0_API_KEY")
    run_id = require_env("ZEALT_RUN_ID")

    user_id = f"lead-{run_id}"
    agent_id = f"csm-{run_id}"
    intake_run_id = f"intake-{run_id}"

    client = MemoryClient(api_key=api_key)

    messages_list = [
        [{"role": "user", "content": "Hi, my name is Priya Shah and I work as a Senior Data Engineer at Helios Robotics."}],
        [{"role": "user", "content": "I'm based in Bengaluru and I've been at Helios for about 4 years."}],
        [{"role": "user", "content": "I have a Master's degree in Computer Science from IIT Bombay."}],
        [{"role": "user", "content": "You can reach me at priya.shah@helios-robotics.example and my LinkedIn handle is priya-shah-de."}],
    ]

    for messages in messages_list:
        client.add(messages=messages, user_id=user_id, agent_id=agent_id, run_id=intake_run_id)

    schema = LeadProfile.model_json_schema()
    filters = {
        "AND": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"run_id": intake_run_id},
        ]
    }

    create_response = client.create_memory_export(schema=schema, filters=filters)
    create_path = "/home/user/mem0-export-task/create_export_response.json"
    with open(create_path, "w", encoding="utf-8") as handle:
        json.dump(create_response, handle, indent=2, ensure_ascii=False)

    export_id = None
    if isinstance(create_response, dict):
        export_id = create_response.get("id")

    if not export_id:
        print("Memory export response missing id.", file=sys.stderr)
        sys.exit(1)

    max_wait_seconds = 120
    poll_interval = 4
    attempts = max_wait_seconds // poll_interval
    final_response = None
    profile = None

    for _ in range(attempts):
        time.sleep(poll_interval)
        response = client.get_memory_export(memory_export_id=export_id)
        profile_candidate = extract_profile(response)
        if profile_candidate:
            final_response = response
            profile = profile_candidate
            break

    if profile is None:
        print("Memory export not ready before timeout.", file=sys.stderr)
        sys.exit(1)

    get_path = "/home/user/mem0-export-task/get_export_response.json"
    with open(get_path, "w", encoding="utf-8") as handle:
        json.dump(final_response, handle, indent=2, ensure_ascii=False)

    normalized_profile = {field: profile.get(field) for field in LeadProfile.model_fields}

    lead_profile_payload = {
        "user_id": user_id,
        "agent_id": agent_id,
        "run_id": intake_run_id,
        "export_id": export_id,
        "profile": normalized_profile,
    }

    lead_profile_path = "/home/user/mem0-export-task/lead_profile.json"
    with open(lead_profile_path, "w", encoding="utf-8") as handle:
        json.dump(lead_profile_payload, handle, indent=2, ensure_ascii=False)

    verifier = MemoryClient(api_key=api_key)
    memories = verifier.get_all(filters=filters, version="v2")
    memory_count = 0
    if isinstance(memories, list):
        memory_count = len(memories)
    elif isinstance(memories, dict):
        data = memories.get("data")
        if isinstance(data, list):
            memory_count = len(data)

    if memory_count < 3:
        print("Expected at least 3 memories for entity scope.", file=sys.stderr)
        sys.exit(1)

    full_name = normalized_profile.get("full_name")
    current_company = normalized_profile.get("current_company")
    location = normalized_profile.get("location")

    if not full_name or not current_company or not location:
        print("Profile missing required fields for logging.", file=sys.stderr)
        sys.exit(1)

    print(f"RUN_ID: {run_id}")
    print(f"EXPORT_ID: {export_id}")
    print("EXPORT_STATUS: ready")
    print(f"FULL_NAME: {full_name}")
    print(f"CURRENT_COMPANY: {current_company}")
    print(f"LOCATION: {location}")


if __name__ == "__main__":
    main()
