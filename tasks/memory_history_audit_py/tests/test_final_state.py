import json
import os
import re
import time

import pytest

LOG_PATH = "/home/user/myproject/output.log"
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _read_log_lines():
    assert os.path.isfile(LOG_PATH), (
        f"Expected log file {LOG_PATH} to exist after the task ran."
    )
    with open(LOG_PATH, "r", encoding="utf-8") as fh:
        return fh.read().splitlines()


def _extract_value(lines, prefix):
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def _expected_user_id():
    run_id = os.environ.get("ZEALT_RUN_ID")
    assert run_id, "ZEALT_RUN_ID must be set in the verifier environment."
    return f"harbor-history-{run_id}"


def _make_client():
    from mem0 import MemoryClient

    api_key = os.environ.get("MEM0_API_KEY")
    assert api_key, "MEM0_API_KEY must be set in the verifier environment."
    return MemoryClient(api_key=api_key)


@pytest.fixture(scope="session")
def log_lines():
    return _read_log_lines()


@pytest.fixture(scope="session")
def expected_user_id():
    return _expected_user_id()


@pytest.fixture(scope="session")
def logged_memory_id(log_lines):
    value = _extract_value(log_lines, "Memory ID:")
    assert value, "Log file must contain a 'Memory ID: <uuid>' line."
    assert UUID_RE.match(value), (
        f"'Memory ID' value '{value}' does not look like a UUID."
    )
    return value


@pytest.fixture(scope="session")
def logged_events(log_lines):
    raw = _extract_value(log_lines, "Events JSON:")
    assert raw, "Log file must contain an 'Events JSON: <json-array>' line."
    try:
        events = json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.fail(f"'Events JSON' value is not valid JSON: {exc}\nRaw value: {raw!r}")
    assert isinstance(events, list) and events, (
        "Events JSON must be a non-empty JSON array."
    )
    return events


@pytest.fixture(scope="session")
def mem0_client():
    return _make_client()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_user(expected_user_id):
    yield
    try:
        client = _make_client()
        client.delete_all(user_id=expected_user_id)
    except Exception:
        # Best-effort cleanup; do not fail the verification because of it.
        pass


def test_log_user_id_matches_run_scope(log_lines, expected_user_id):
    value = _extract_value(log_lines, "User ID:")
    assert value, "Log file must contain a 'User ID: <id>' line."
    assert value == expected_user_id, (
        f"Expected log User ID to be '{expected_user_id}', got '{value}'."
    )


def test_log_events_contain_add_and_update(logged_events):
    event_types = [str(e.get("event", "")).upper() for e in logged_events]
    assert "ADD" in event_types, (
        f"Logged history must contain at least one ADD event; got {event_types}."
    )
    assert "UPDATE" in event_types, (
        f"Logged history must contain at least one UPDATE event; got {event_types}."
    )


def test_memory_exists_on_platform_for_user(
    mem0_client, expected_user_id, logged_memory_id
):
    memories = mem0_client.get_all(user_id=expected_user_id)
    # The Platform may return either a list or a dict with a "results" key.
    if isinstance(memories, dict):
        memories = memories.get("results", memories.get("memories", []))
    assert isinstance(memories, list) and memories, (
        f"Expected at least one memory for user '{expected_user_id}', got {memories!r}."
    )
    ids = {str(m.get("id")) for m in memories if isinstance(m, dict)}
    assert logged_memory_id in ids, (
        f"Logged Memory ID '{logged_memory_id}' was not found among memories for "
        f"user '{expected_user_id}'. Got ids: {ids}"
    )


def test_updated_memory_text_mentions_senior(mem0_client, logged_memory_id):
    memory = mem0_client.get(memory_id=logged_memory_id)
    assert isinstance(memory, dict), (
        f"Expected mem0 get() to return a dict, got {type(memory).__name__}."
    )
    text = ""
    for key in ("memory", "text", "data"):
        value = memory.get(key)
        if isinstance(value, str) and value:
            text = value
            break
    assert text, (
        f"Could not find a memory/text field in the get() response: {memory!r}"
    )
    assert "senior" in text.lower(), (
        f"Stored memory text must reference 'senior' after the update; got: {text!r}"
    )


def test_platform_history_contains_add_and_update(mem0_client, logged_memory_id):
    # Allow a brief retry window in case the history endpoint is eventually
    # consistent after an update.
    last_error = None
    for _ in range(5):
        try:
            history = mem0_client.history(memory_id=logged_memory_id)
        except Exception as exc:  # pragma: no cover - retried below
            last_error = exc
            time.sleep(2)
            continue

        if isinstance(history, dict):
            history = history.get("results", history.get("history", []))
        if not isinstance(history, list):
            last_error = AssertionError(
                f"history() must return a list; got {type(history).__name__}."
            )
            time.sleep(2)
            continue

        events = [str(item.get("event", "")).upper() for item in history if isinstance(item, dict)]
        if "ADD" in events and "UPDATE" in events:
            update_entries = [
                item for item in history
                if isinstance(item, dict)
                and str(item.get("event", "")).upper() == "UPDATE"
            ]
            new_memories = [
                str(entry.get("new_memory") or "") for entry in update_entries
            ]
            assert any("senior" in nm.lower() for nm in new_memories), (
                "At least one UPDATE event must have new_memory containing 'senior'; "
                f"got new_memories={new_memories!r}."
            )
            return
        last_error = AssertionError(
            f"Platform history must contain both ADD and UPDATE events; got {events!r}."
        )
        time.sleep(2)

    if last_error:
        raise last_error
