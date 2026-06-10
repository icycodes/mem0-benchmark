import os
import re
import time

import pytest

PROJECT_DIR = "/home/user/myproject"
LOG_PATH = os.path.join(PROJECT_DIR, "feedback.log")

LOG_LINE_RE = re.compile(
    r"^memory_id=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}) "
    r"feedback=(POSITIVE|NEGATIVE|VERY_NEGATIVE) "
    r"feedback_id=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)

EXPECTED_FIRST_THREE = ["POSITIVE", "NEGATIVE", "VERY_NEGATIVE"]


def _expected_user_id():
    run_id = os.environ.get("ZEALT_RUN_ID", "")
    assert run_id, "ZEALT_RUN_ID is required for verification."
    return f"feedback-user-{run_id}"


@pytest.fixture(scope="module")
def parsed_log_records():
    assert os.path.isfile(LOG_PATH), (
        f"Expected feedback log at '{LOG_PATH}' to exist after the task runs."
    )

    with open(LOG_PATH, "r", encoding="utf-8") as fh:
        raw_lines = [line.strip() for line in fh.readlines()]

    non_empty = [line for line in raw_lines if line]
    assert non_empty, f"feedback.log at '{LOG_PATH}' must not be empty."

    records = []
    for idx, line in enumerate(non_empty, start=1):
        match = LOG_LINE_RE.match(line)
        assert match is not None, (
            f"Line {idx} of feedback.log does not match the required format "
            f"'memory_id=<uuid> feedback=<TYPE> feedback_id=<uuid>': {line!r}"
        )
        records.append(
            {
                "memory_id": match.group(1),
                "feedback": match.group(2),
                "feedback_id": match.group(3),
            }
        )

    return records


def test_log_has_at_least_three_records(parsed_log_records):
    assert len(parsed_log_records) >= 3, (
        f"feedback.log must contain at least 3 records; found {len(parsed_log_records)}."
    )


def test_first_three_feedback_types_are_in_order(parsed_log_records):
    actual_first_three = [r["feedback"] for r in parsed_log_records[:3]]
    assert actual_first_three == EXPECTED_FIRST_THREE, (
        "The first three feedback types in feedback.log must be "
        f"{EXPECTED_FIRST_THREE} in this exact order, got {actual_first_three}."
    )


def test_feedback_ids_are_unique(parsed_log_records):
    feedback_ids = [r["feedback_id"] for r in parsed_log_records]
    assert len(set(feedback_ids)) == len(feedback_ids), (
        f"feedback_id values in feedback.log must be unique; got {feedback_ids}."
    )


def test_memories_exist_in_mem0_for_scoped_user(parsed_log_records):
    """Use the Mem0 Platform SDK to verify the memories exist for the scoped user."""
    from mem0 import MemoryClient

    api_key = os.environ.get("MEM0_API_KEY")
    assert api_key, "MEM0_API_KEY must be available to the verifier."

    client = MemoryClient(api_key=api_key)
    user_id = _expected_user_id()

    server_memory_ids = set()
    last_error = None
    # The platform may need a brief moment to expose the memories; retry a few times.
    for _ in range(6):
        try:
            response = client.get_all(filters={"user_id": user_id}, version="v2")
        except Exception as exc:  # pragma: no cover - defensive
            last_error = exc
            time.sleep(2)
            continue

        if isinstance(response, dict):
            memories = response.get("results") or response.get("memories") or []
        else:
            memories = response or []

        for mem in memories:
            mem_id = mem.get("id") if isinstance(mem, dict) else None
            if mem_id:
                server_memory_ids.add(mem_id)

        if server_memory_ids:
            break
        time.sleep(2)

    assert server_memory_ids, (
        f"Mem0 returned no memories for user_id='{user_id}'. "
        f"Last error (if any): {last_error}"
    )

    logged_memory_ids = {r["memory_id"] for r in parsed_log_records}
    missing = logged_memory_ids - server_memory_ids
    assert not missing, (
        "Every memory_id recorded in feedback.log must correspond to a memory "
        f"that exists in Mem0 for user_id='{user_id}'. Missing IDs: {sorted(missing)}"
    )
