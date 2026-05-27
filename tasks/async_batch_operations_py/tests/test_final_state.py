import asyncio
import json
import os
import re

import pytest

PROJECT_DIR = "/home/user/mem0-async-task"
LOG_FILE = os.path.join(PROJECT_DIR, "output.log")
ALL_MEMORIES_FILE = os.path.join(PROJECT_DIR, "all_memories.json")
BATCH_UPDATE_FILE = os.path.join(PROJECT_DIR, "batch_update_response.json")
BATCH_DELETE_FILE = os.path.join(PROJECT_DIR, "batch_delete_response.json")
HISTORY_FILE = os.path.join(PROJECT_DIR, "barbell_history.json")


def _run_id() -> str:
    run_id = os.environ.get("ZEALT_RUN_ID")
    assert run_id, "ZEALT_RUN_ID is not set in verifier environment."
    return run_id


def _entity_ids():
    rid = _run_id()
    return {
        "user_id": f"athlete-{rid}",
        "agent_id": f"coach-{rid}",
        "app_id": f"fitness-app-{rid}",
        "run_id": f"session-{rid}",
    }


def _read_log() -> str:
    assert os.path.isfile(LOG_FILE), f"Log file does not exist at {LOG_FILE}."
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _load_json(path: str):
    assert os.path.isfile(path), f"Expected artifact does not exist: {path}."
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _memory_text(item) -> str:
    """Extract the textual content from a memory dict."""
    if not isinstance(item, dict):
        return ""
    for key in ("memory", "text", "name", "content", "data"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    return ""


# ---------------------------------------------------------------------------
# Log file assertions
# ---------------------------------------------------------------------------


def test_log_contains_run_id():
    rid = _run_id()
    log = _read_log()
    assert re.search(rf"^RUN_ID:\s*{re.escape(rid)}\s*$", log, re.MULTILINE), (
        f"Log must contain a line 'RUN_ID: {rid}'. Log content:\n{log}"
    )


def test_log_contains_total_memories():
    log = _read_log()
    match = re.search(r"^TOTAL_MEMORIES:\s*(\d+)\s*$", log, re.MULTILINE)
    assert match, f"Log must contain 'TOTAL_MEMORIES: <int>'. Log:\n{log}"
    assert int(match.group(1)) >= 4, (
        f"TOTAL_MEMORIES must be >= 4, got {match.group(1)}."
    )


def test_log_contains_memory_ids():
    log = _read_log()
    for key in ("BARBELL_ID", "NUTRITION_ID", "HEART_ID"):
        match = re.search(rf"^{key}:\s*(\S+)\s*$", log, re.MULTILINE)
        assert match, f"Log must contain '{key}: <non-empty id>'. Log:\n{log}"
        assert match.group(1).strip(), f"{key} value is empty in log."


def test_log_contains_batch_counts():
    log = _read_log()
    assert re.search(r"^BATCH_UPDATE_COUNT:\s*2\s*$", log, re.MULTILINE), (
        f"Log must contain literal line 'BATCH_UPDATE_COUNT: 2'. Log:\n{log}"
    )
    assert re.search(r"^BATCH_DELETE_COUNT:\s*1\s*$", log, re.MULTILINE), (
        f"Log must contain literal line 'BATCH_DELETE_COUNT: 1'. Log:\n{log}"
    )


def test_log_contains_history_events():
    log = _read_log()
    match = re.search(r"^HISTORY_EVENTS:\s*(\d+)\s*$", log, re.MULTILINE)
    assert match, f"Log must contain 'HISTORY_EVENTS: <int>'. Log:\n{log}"
    assert int(match.group(1)) >= 2, (
        f"HISTORY_EVENTS must be >= 2, got {match.group(1)}."
    )


# ---------------------------------------------------------------------------
# Artifact assertions
# ---------------------------------------------------------------------------


def test_all_memories_artifact_shape():
    data = _load_json(ALL_MEMORIES_FILE)
    assert isinstance(data, dict), "all_memories.json must be a JSON object."
    expected = _entity_ids()
    for key, value in expected.items():
        assert data.get(key) == value, (
            f"all_memories.json[{key}] expected {value!r}, got {data.get(key)!r}."
        )
    memories = data.get("memories")
    assert isinstance(memories, list) and len(memories) >= 4, (
        f"all_memories.json['memories'] must be a list with >= 4 items, got {memories!r}."
    )
    for item in memories:
        assert isinstance(item, dict), f"Memory entry not a dict: {item!r}"
        assert item.get("id"), f"Memory entry missing non-empty `id`: {item!r}"
        assert _memory_text(item), (
            f"Memory entry missing non-empty `memory`/text field: {item!r}"
        )


def test_batch_update_response_artifact():
    data = _load_json(BATCH_UPDATE_FILE)
    serialized = json.dumps(data)
    assert serialized.strip() not in ("", "null"), (
        "batch_update_response.json must be a non-empty JSON value."
    )
    assert "Successfully updated" in serialized or len(serialized) > 2, (
        "batch_update_response.json should contain the Mem0 success message or be a non-empty JSON object/list, "
        f"got: {serialized!r}"
    )


def test_batch_delete_response_artifact():
    data = _load_json(BATCH_DELETE_FILE)
    serialized = json.dumps(data)
    assert serialized.strip() not in ("", "null"), (
        "batch_delete_response.json must be a non-empty JSON value."
    )
    assert "Successfully deleted" in serialized or len(serialized) > 2, (
        "batch_delete_response.json should contain the Mem0 success message or be a non-empty JSON object/list, "
        f"got: {serialized!r}"
    )


def test_barbell_history_artifact():
    data = _load_json(HISTORY_FILE)
    assert isinstance(data, dict), "barbell_history.json must be a JSON object."
    assert isinstance(data.get("memory_id"), str) and data["memory_id"].strip(), (
        f"barbell_history.json['memory_id'] must be a non-empty string, got {data.get('memory_id')!r}."
    )
    assert (
        data.get("updated_text") == "Strength training with dumbbells on Thursdays"
    ), (
        "barbell_history.json['updated_text'] must equal "
        "'Strength training with dumbbells on Thursdays', "
        f"got {data.get('updated_text')!r}."
    )
    history = data.get("history")
    assert isinstance(history, list) and len(history) >= 2, (
        f"barbell_history.json['history'] must be a list with >= 2 entries, got {history!r}."
    )
    found_update = False
    for entry in history:
        if not isinstance(entry, dict):
            continue
        for field in ("event", "type", "action"):
            value = entry.get(field)
            if isinstance(value, str) and value.upper() == "UPDATE":
                found_update = True
                break
        if found_update:
            break
    assert found_update, (
        "barbell_history.json['history'] must contain at least one entry with event/type == 'UPDATE'. "
        f"Entries: {history!r}"
    )


# ---------------------------------------------------------------------------
# Server-side state assertions via fresh AsyncMemoryClient
# ---------------------------------------------------------------------------


async def _fetch_all_memories_async():
    from mem0 import AsyncMemoryClient

    ids = _entity_ids()
    client = AsyncMemoryClient()
    response = await client.get_all(
        filters={
            "AND": [
                {"user_id": ids["user_id"]},
                {"agent_id": ids["agent_id"]},
                {"app_id": ids["app_id"]},
                {"run_id": ids["run_id"]},
            ]
        },
        version="v2",
    )
    if isinstance(response, dict) and "results" in response:
        return response["results"]
    if isinstance(response, list):
        return response
    return []


def _fetch_all_memories():
    return asyncio.run(_fetch_all_memories_async())


def test_server_state_after_batch_operations():
    pytest.importorskip("mem0")
    api_key = os.environ.get("MEM0_API_KEY")
    assert api_key, "MEM0_API_KEY required for server-side verification."

    memories = _fetch_all_memories()
    assert isinstance(memories, list), (
        f"Server response should be a list, got {type(memories).__name__}."
    )
    texts = [_memory_text(m).lower() for m in memories]

    assert any("dumbbells" in t for t in texts), (
        f"Expected the batch-updated barbell memory to contain 'dumbbells'. Texts: {texts}"
    )
    assert any("whey" in t for t in texts), (
        f"Expected the batch-updated nutrition memory to contain 'whey'. Texts: {texts}"
    )

    assert not any(("resting" in t) and ("bpm" in t) for t in texts), (
        f"Heart-rate memory should have been deleted via batch_delete. Remaining texts: {texts}"
    )

    assert any(("5 kilometers" in t) or ("tuesday" in t) for t in texts), (
        f"Expected at least one untouched memory (e.g. running on Tuesday) to survive. Texts: {texts}"
    )
