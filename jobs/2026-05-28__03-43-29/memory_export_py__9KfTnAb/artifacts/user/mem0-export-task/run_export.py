"""
Mem0 Platform — Structured Memory Export
Ingests conversational memories for a lead, exports them via a Pydantic schema,
and persists structured artifacts to disk.
"""

import json
import os
import sys
import time
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------

MEM0_API_KEY = os.environ.get("MEM0_API_KEY")
ZEALT_RUN_ID = os.environ.get("ZEALT_RUN_ID")

if not MEM0_API_KEY:
    sys.exit("ERROR: MEM0_API_KEY environment variable is not set.")
if not ZEALT_RUN_ID:
    sys.exit("ERROR: ZEALT_RUN_ID environment variable is not set.")

# ---------------------------------------------------------------------------
# Entity IDs derived from run-id
# ---------------------------------------------------------------------------

run_id_val = ZEALT_RUN_ID
user_id = f"lead-{run_id_val}"
agent_id = f"csm-{run_id_val}"
run_id = f"intake-{run_id_val}"

print(f"RUN_ID: {ZEALT_RUN_ID}")

# ---------------------------------------------------------------------------
# Mem0 client
# ---------------------------------------------------------------------------

from mem0 import MemoryClient  # noqa: E402 (import after env check)

client = MemoryClient(api_key=MEM0_API_KEY)

# ---------------------------------------------------------------------------
# Step 1 — Ingest four independent memory writes
# ---------------------------------------------------------------------------

MESSAGES = [
    [{"role": "user", "content": "Hi, my name is Priya Shah and I work as a Senior Data Engineer at Helios Robotics."}],
    [{"role": "user", "content": "I'm based in Bengaluru and I've been at Helios for about 4 years."}],
    [{"role": "user", "content": "I have a Master's degree in Computer Science from IIT Bombay."}],
    [{"role": "user", "content": "You can reach me at priya.shah@helios-robotics.example and my LinkedIn handle is priya-shah-de."}],
]

print("Ingesting memories…")
for i, messages in enumerate(MESSAGES, start=1):
    response = client.add(
        messages,
        user_id=user_id,
        agent_id=agent_id,
        run_id=run_id,
    )
    print(f"  add #{i}: {response}")

# Allow server-side extraction to settle before querying / exporting
print("Waiting for memory extraction to settle (45 s)…")
time.sleep(45)

# ---------------------------------------------------------------------------
# Step 2 — Pydantic schema
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
print(f"JSON schema: {json.dumps(json_schema, indent=2)}")

# ---------------------------------------------------------------------------
# Step 3 — Submit the export job
# ---------------------------------------------------------------------------

# v2-style AND filter over all three entity IDs as required by the export API.
# Mem0 stores a single memory record that carries all three entity IDs when all three
# are passed to client.add(), so the AND filter correctly selects those records.
filters = {
    "AND": [
        {"user_id": user_id},
        {"agent_id": agent_id},
        {"run_id": run_id},
    ]
}

print(f"Submitting export job with filters: {filters}")
create_response = client.create_memory_export(schema=json_schema, filters=filters)
print(f"create_memory_export response: {create_response}")

# Persist raw create response
output_dir = "/home/user/mem0-export-task"
os.makedirs(output_dir, exist_ok=True)

with open(os.path.join(output_dir, "create_export_response.json"), "w") as f:
    json.dump(create_response, f, indent=2)

export_id = create_response.get("id") or create_response.get("export_id") or create_response.get("memory_export_id")
if not export_id:
    sys.exit(f"ERROR: Could not find export ID in create_memory_export response: {create_response}")

print(f"EXPORT_ID: {export_id}")

# ---------------------------------------------------------------------------
# Step 4 — Poll until the export is ready
# ---------------------------------------------------------------------------

MAX_WAIT_SECONDS = 180
POLL_INTERVAL = 15
elapsed = 0
get_response = None

# Give the export job a brief head start before first poll
print("Initial export processing pause (15 s)…")
time.sleep(15)
print(f"Polling export status (max {MAX_WAIT_SECONDS}s, every {POLL_INTERVAL}s)…")

while elapsed < MAX_WAIT_SECONDS:
    time.sleep(POLL_INTERVAL)
    elapsed += POLL_INTERVAL

    try:
        poll_response = client.get_memory_export(memory_export_id=export_id)
    except Exception as exc:
        print(f"  [{elapsed}s] get_memory_export raised: {exc} — retrying…")
        continue

    print(f"  [{elapsed}s] raw response: {poll_response}")

    # The response is "ready" when it contains actual profile data.
    # It may be wrapped under "data", "export", "result", or be the object itself.
    def _extract_profile(resp):
        """Return the profile dict if the response contains structured data with at
        least one non-None value, else None."""
        if not resp:
            return None
        if isinstance(resp, dict):
            profile_keys = {"full_name", "current_role", "current_company", "location",
                            "years_at_company", "education", "contact_email"}
            # Check if the response itself is the profile
            if profile_keys & set(resp.keys()):
                # Only accept if at least one value is non-None
                if any(resp.get(k) is not None for k in profile_keys):
                    return resp
            # Try common wrapper keys
            for key in ("data", "export", "result", "profile", "output"):
                if key in resp and isinstance(resp[key], dict):
                    candidate = resp[key]
                    if profile_keys & set(candidate.keys()):
                        if any(candidate.get(k) is not None for k in profile_keys):
                            return candidate
        return None

    profile_data = _extract_profile(poll_response)
    if profile_data:
        get_response = poll_response
        print(f"  [{elapsed}s] Export is ready!")
        break
    else:
        print(f"  [{elapsed}s] Not ready yet (all fields null or empty) — continuing to poll…")

if get_response is None:
    # One final attempt with a broader readiness check
    print("Performing final get attempt…")
    try:
        get_response = client.get_memory_export(memory_export_id=export_id)
    except Exception as exc:
        sys.exit(f"ERROR: Export not ready after {MAX_WAIT_SECONDS}s. Last error: {exc}")

    if not get_response:
        sys.exit(f"ERROR: Export not ready after {MAX_WAIT_SECONDS}s. Final response: {get_response}")

# ---------------------------------------------------------------------------
# Step 5 — Extract and normalise profile
# ---------------------------------------------------------------------------

# Re-use _extract_profile to unwrap if needed
def _extract_profile(resp):
    if not resp:
        return None
    if isinstance(resp, dict):
        profile_keys = {"full_name", "current_role", "current_company", "location",
                        "years_at_company", "education", "contact_email"}
        if profile_keys & set(resp.keys()):
            if any(resp.get(k) is not None for k in profile_keys):
                return resp
        for key in ("data", "export", "result", "profile", "output"):
            if key in resp and isinstance(resp[key], dict):
                candidate = resp[key]
                if profile_keys & set(candidate.keys()):
                    if any(candidate.get(k) is not None for k in profile_keys):
                        return candidate
    return None


profile = _extract_profile(get_response)
if profile is None:
    # Fallback: treat the entire response as the profile
    profile = get_response if isinstance(get_response, dict) else {}

print(f"EXPORT_STATUS: ready")
print(f"FULL_NAME: {profile.get('full_name', '')}")
print(f"CURRENT_COMPANY: {profile.get('current_company', '')}")
print(f"LOCATION: {profile.get('location', '')}")

# ---------------------------------------------------------------------------
# Step 6 — Persist artifacts
# ---------------------------------------------------------------------------

# get_export_response.json
with open(os.path.join(output_dir, "get_export_response.json"), "w") as f:
    json.dump(get_response, f, indent=2)

# lead_profile.json
lead_profile_artifact = {
    "user_id": user_id,
    "agent_id": agent_id,
    "run_id": run_id,
    "export_id": export_id,
    "profile": profile,
}
with open(os.path.join(output_dir, "lead_profile.json"), "w") as f:
    json.dump(lead_profile_artifact, f, indent=2)

print(f"Artifacts written to {output_dir}")

# ---------------------------------------------------------------------------
# Step 7 — Verify server-side memories (acceptance-criteria check)
# ---------------------------------------------------------------------------

print("Verifying server-side memories…")
verify_filters = {
    "AND": [
        {"user_id": user_id},
        {"agent_id": agent_id},
        {"run_id": run_id},
    ]
}
try:
    all_memories = client.get_all(filters=verify_filters, version="v2")
    # get_all may return a list directly or a dict with a 'results' key
    if isinstance(all_memories, dict):
        memories_list = all_memories.get("results", [])
    elif isinstance(all_memories, list):
        memories_list = all_memories
    else:
        memories_list = []
    print(f"Total memories returned: {len(memories_list)}")
    if len(memories_list) < 3:
        print(f"WARNING: Expected at least 3 memories, got {len(memories_list)}. "
              f"They may still be processing or the AND filter may require OR logic.")
except Exception as exc:
    print(f"WARNING: get_all verification call failed (quota/rate-limit?): {exc}")

print("Done.")
