#!/usr/bin/env python3
"""Mem0 Platform — Structured Memory Export with Pydantic Schema.

Ingests conversational memories about a lead, defines a Pydantic schema,
submits a memory export job, polls for completion, and persists artifacts.
"""

import json
import os
import sys
import time
from typing import Optional

from pydantic import BaseModel
from mem0 import MemoryClient


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

MEM0_API_KEY = os.environ.get("MEM0_API_KEY")
ZEALT_RUN_ID = os.environ.get("ZEALT_RUN_ID")

if not MEM0_API_KEY:
    print("ERROR: MEM0_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)
if not ZEALT_RUN_ID:
    print("ERROR: ZEALT_RUN_ID environment variable is not set.", file=sys.stderr)
    sys.exit(1)

# Derive entity IDs from the run-id to avoid collisions across concurrent runs.
USER_ID = f"lead-{ZEALT_RUN_ID}"
AGENT_ID = f"csm-{ZEALT_RUN_ID}"
RUN_ID = f"intake-{ZEALT_RUN_ID}"

# Output directory
OUTPUT_DIR = "/home/user/mem0-export-task"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Mem0 client
# ---------------------------------------------------------------------------

client = MemoryClient(api_key=MEM0_API_KEY)

# ---------------------------------------------------------------------------
# Step 1: Ingest memories
# ---------------------------------------------------------------------------

MEMORIES = [
    [{"role": "user", "content": "Hi, my name is Priya Shah and I work as a Senior Data Engineer at Helios Robotics."}],
    [{"role": "user", "content": "I'm based in Bengaluru and I've been at Helios for about 4 years."}],
    [{"role": "user", "content": "I have a Master's degree in Computer Science from IIT Bombay."}],
    [{"role": "user", "content": "You can reach me at priya.shah@helios-robotics.example and my LinkedIn handle is priya-shah-de."}],
]

for i, messages in enumerate(MEMORIES):
    client.add(
        messages,
        user_id=USER_ID,
        agent_id=AGENT_ID,
        run_id=RUN_ID,
    )

# Allow time for server-side processing before the memories are visible.
time.sleep(5)

# ---------------------------------------------------------------------------
# Step 2: Define the Pydantic schema
# ---------------------------------------------------------------------------


class LeadProfile(BaseModel):
    full_name: Optional[str] = None
    current_role: Optional[str] = None
    current_company: Optional[str] = None
    location: Optional[str] = None
    years_at_company: Optional[int] = None
    education: Optional[str] = None
    contact_email: Optional[str] = None


json_schema = LeadProfile.model_json_schema()

# ---------------------------------------------------------------------------
# Step 3: Submit the memory export job
# ---------------------------------------------------------------------------

filters = {
    "AND": [
        {"user_id": USER_ID},
        {"agent_id": AGENT_ID},
        {"run_id": RUN_ID},
    ]
}

create_response = client.create_memory_export(schema=json_schema, filters=filters)

export_id = create_response.get("id", "")
if not export_id:
    print("ERROR: create_memory_export did not return an id.", file=sys.stderr)
    print(f"Response: {create_response}", file=sys.stderr)
    sys.exit(1)

# Persist the raw create_export response.
with open(os.path.join(OUTPUT_DIR, "create_export_response.json"), "w") as f:
    json.dump(create_response, f, indent=2)

# ---------------------------------------------------------------------------
# Step 4: Poll for the export result
# ---------------------------------------------------------------------------

MAX_WAIT_SECONDS = 120
POLL_INTERVAL = 5
elapsed = 0
get_response = None
profile_data = None

while elapsed < MAX_WAIT_SECONDS:
    time.sleep(POLL_INTERVAL)
    elapsed += POLL_INTERVAL

    resp = client.get_memory_export(memory_export_id=export_id)

    # The response may be empty while the job is still running.
    # Treat the export as ready when we find structured profile fields.
    if resp and isinstance(resp, dict):
        # Try to find the profile data — it might be at the top level
        # or nested under a key like "data", "export", or "result".
        candidate = resp.get("data") or resp.get("export") or resp.get("result")
        if candidate and isinstance(candidate, dict):
            # Check if it looks like a profile (has expected fields)
            if any(k in candidate for k in ("full_name", "current_role", "current_company")):
                profile_data = candidate
                get_response = resp
                break
        # Also check if the response itself looks like a profile
        if any(k in resp for k in ("full_name", "current_role", "current_company")):
            profile_data = resp
            get_response = resp
            break

if get_response is None or profile_data is None:
    print("ERROR: Export did not complete within the timeout.", file=sys.stderr)
    sys.exit(1)

# Persist the raw get_export response.
with open(os.path.join(OUTPUT_DIR, "get_export_response.json"), "w") as f:
    json.dump(get_response, f, indent=2)

# ---------------------------------------------------------------------------
# Step 5: Build and persist the normalized lead_profile artifact
# ---------------------------------------------------------------------------

lead_profile = {
    "user_id": USER_ID,
    "agent_id": AGENT_ID,
    "run_id": RUN_ID,
    "export_id": export_id,
    "profile": profile_data,
}

with open(os.path.join(OUTPUT_DIR, "lead_profile.json"), "w") as f:
    json.dump(lead_profile, f, indent=2)

# ---------------------------------------------------------------------------
# Step 6: Output the required log lines to stdout
# ---------------------------------------------------------------------------

print(f"RUN_ID: {ZEALT_RUN_ID}")
print(f"EXPORT_ID: {export_id}")
print(f"EXPORT_STATUS: ready")
print(f"FULL_NAME: {profile_data.get('full_name', '')}")
print(f"CURRENT_COMPANY: {profile_data.get('current_company', '')}")
print(f"LOCATION: {profile_data.get('location', '')}")
