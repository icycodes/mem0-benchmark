"""
Mem0 feedback submission script.

- Ingests a deterministic conversation under a scoped user_id derived from
  ZEALT_RUN_ID environment variable.
- Retrieves the extracted memories.
- Submits one feedback record per memory, cycling POSITIVE → NEGATIVE → VERY_NEGATIVE.
- Writes a structured log to /home/user/myproject/feedback.log.
"""

import os
import time
import json

from mem0 import MemoryClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LOG_FILE = "/home/user/myproject/feedback.log"
FEEDBACK_CYCLE = ["POSITIVE", "NEGATIVE", "VERY_NEGATIVE"]
FEEDBACK_REASONS = {
    "POSITIVE": "Memory is accurate and highly relevant to the user's trip planning.",
    "NEGATIVE": "Memory could be more specific about the dietary preference context.",
    "VERY_NEGATIVE": "Memory does not accurately capture the nuance of the user's schedule preference.",
}

# Deterministic conversation to ingest
CONVERSATION = [
    {"role": "user",      "content": "My name is Robin and I'm planning a trip to Kyoto next April."},
    {"role": "assistant", "content": "Lovely! I'll keep that in mind for your itinerary."},
    {"role": "user",      "content": "I'm vegetarian, so please remember to flag vegetarian restaurants."},
    {"role": "assistant", "content": "Got it, I'll only recommend vegetarian-friendly places."},
    {"role": "user",      "content": "Also, I tend to wake up early and prefer morning activities."},
]

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
api_key = os.environ.get("MEM0_API_KEY")
if not api_key:
    raise EnvironmentError("MEM0_API_KEY environment variable is not set.")

run_id = os.environ.get("ZEALT_RUN_ID")
if not run_id:
    raise EnvironmentError("ZEALT_RUN_ID environment variable is not set.")

user_id = f"feedback-user-{run_id}"
print(f"[INFO] Using user_id: {user_id}")

client = MemoryClient(api_key=api_key)

# ---------------------------------------------------------------------------
# Step 1 – Add the conversation to Mem0
# ---------------------------------------------------------------------------
print("[INFO] Adding conversation to Mem0 …")
add_response = client.add(CONVERSATION, user_id=user_id)
print(f"[INFO] add() response: {json.dumps(add_response, default=str)}")

# ---------------------------------------------------------------------------
# Step 2 – Poll until memories are available (async extraction)
# ---------------------------------------------------------------------------
MAX_WAIT_SECONDS = 60
POLL_INTERVAL = 3

memories = []
elapsed = 0
print("[INFO] Polling for extracted memories …")
while elapsed < MAX_WAIT_SECONDS:
    result = client.get_all(filters={"user_id": user_id}, version="v2")
    # v2 envelope: {"results": [...], ...} or a list directly
    if isinstance(result, dict):
        memories = result.get("results", [])
    elif isinstance(result, list):
        memories = result
    else:
        memories = []

    if memories:
        print(f"[INFO] Retrieved {len(memories)} memor{'y' if len(memories) == 1 else 'ies'} after {elapsed}s.")
        break

    print(f"[INFO] No memories yet; waiting {POLL_INTERVAL}s … ({elapsed}s elapsed)")
    time.sleep(POLL_INTERVAL)
    elapsed += POLL_INTERVAL
else:
    raise RuntimeError(
        f"No memories were available after {MAX_WAIT_SECONDS}s for user_id={user_id!r}. "
        "The conversation may not have been processed. Check the API key and try again."
    )

# ---------------------------------------------------------------------------
# Step 3 – Submit feedback for each memory, cycling through the three types
# ---------------------------------------------------------------------------
log_lines = []

for idx, memory in enumerate(memories):
    memory_id = memory.get("id") or memory.get("memory_id")
    if not memory_id:
        print(f"[WARN] Memory at index {idx} has no id field; skipping. Raw: {memory}")
        continue

    feedback_type = FEEDBACK_CYCLE[idx % len(FEEDBACK_CYCLE)]
    # Pick a reason that matches the type, or fall back to a generic one
    reason = FEEDBACK_REASONS.get(
        feedback_type,
        f"Automated feedback submission for memory index {idx}."
    )

    print(f"[INFO] Submitting {feedback_type} feedback for memory_id={memory_id} …")
    fb_response = client.feedback(
        memory_id=memory_id,
        feedback=feedback_type,
        feedback_reason=reason,
    )
    print(f"[INFO] feedback() response: {json.dumps(fb_response, default=str)}")

    # Extract the feedback id from the response
    if isinstance(fb_response, dict):
        feedback_id = (
            fb_response.get("id")
            or fb_response.get("feedback_id")
            or fb_response.get("feedbackId")
            or "unknown"
        )
    else:
        feedback_id = str(fb_response)

    log_line = f"memory_id={memory_id} feedback={feedback_type} feedback_id={feedback_id}"
    log_lines.append(log_line)
    print(f"[INFO] Logged: {log_line}")

# ---------------------------------------------------------------------------
# Step 4 – Write the structured log file
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
with open(LOG_FILE, "w") as fh:
    fh.write("\n".join(log_lines) + "\n")

print(f"[INFO] Log written to {LOG_FILE} ({len(log_lines)} record(s)).")
print("[DONE] Script completed successfully.")
