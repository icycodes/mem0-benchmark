#!/usr/bin/env python3
"""Ingest a conversation into Mem0, retrieve extracted memories, submit feedback,
and write a structured audit log.

Environment variables:
    MEM0_API_KEY  – required, Mem0 Platform API key
    ZEALT_RUN_ID  – required, unique run identifier for scoping the user
"""

import os
import sys
import json
import time
import logging

from mem0 import MemoryClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONVERSATION = [
    {"role": "user",      "content": "My name is Robin and I'm planning a trip to Kyoto next April."},
    {"role": "assistant", "content": "Lovely! I'll keep that in mind for your itinerary."},
    {"role": "user",      "content": "I'm vegetarian, so please remember to flag vegetarian restaurants."},
    {"role": "assistant", "content": "Got it, I'll only recommend vegetarian-friendly places."},
    {"role": "user",      "content": "Also, I tend to wake up early and prefer morning activities."},
]

FEEDBACK_TYPES = ["POSITIVE", "NEGATIVE", "VERY_NEGATIVE"]

LOG_PATH = "/home/user/myproject/feedback.log"

MAX_POLL_ATTEMPTS = 30
POLL_INTERVAL_S = 2  # seconds between polls

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)


def die(msg: str) -> None:
    log.error(msg)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # -- validate environment ------------------------------------------------
    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        die("MEM0_API_KEY environment variable is not set")

    run_id = os.environ.get("ZEALT_RUN_ID")
    if not run_id:
        die("ZEALT_RUN_ID environment variable is not set")

    user_id = f"feedback-user-{run_id}"
    log.info("Scoped user_id = %s", user_id)

    # -- initialise client ---------------------------------------------------
    client = MemoryClient(api_key=api_key)

    # -- add conversation ----------------------------------------------------
    log.info("Adding conversation (5 messages) …")
    client.add(CONVERSATION, user_id=user_id)
    log.info("Add call completed")

    # -- poll for extracted memories -----------------------------------------
    log.info("Polling for extracted memories …")
    memories = []
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL_S)
        result = client.get_all(filters={"user_id": user_id}, version="v2")
        # The v2 envelope is typically {"results": [...]}
        if isinstance(result, dict):
            memories = result.get("results", [])
        elif isinstance(result, list):
            memories = result
        else:
            memories = []

        log.info("  Attempt %d: got %d memories", attempt, len(memories))
        if memories:
            break
    else:
        die("Timed out waiting for memories to appear")

    # -- submit feedback -----------------------------------------------------
    log.info("Submitting feedback for %d memories …", len(memories))

    log_lines: list[str] = []

    for idx, mem in enumerate(memories):
        memory_id = mem.get("id")
        if not memory_id:
            log.warning("Memory at index %d has no 'id'; skipping", idx)
            continue

        fb_type = FEEDBACK_TYPES[idx % len(FEEDBACK_TYPES)]
        reason = f"Feedback {idx+1} for run {run_id}"

        resp = client.feedback(
            memory_id=memory_id,
            feedback=fb_type,
            feedback_reason=reason,
        )
        feedback_id = resp.get("id") if isinstance(resp, dict) else None

        if not feedback_id:
            log.warning("Feedback response missing 'id': %s", resp)

        line = f"memory_id={memory_id} feedback={fb_type} feedback_id={feedback_id}"
        log_lines.append(line)
        log.info("  %s", line)

    # -- write log file ------------------------------------------------------
    log.info("Writing %d feedback records to %s", len(log_lines), LOG_PATH)
    with open(LOG_PATH, "w") as fh:
        for line in log_lines:
            fh.write(line + "\n")

    log.info("Done – feedback.log written successfully")


if __name__ == "__main__":
    main()
