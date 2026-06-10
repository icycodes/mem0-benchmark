import json
import os
import re

import pytest

PROJECT_DIR = "/home/user/mem0-metadata-task"
LOG_FILE = os.path.join(PROJECT_DIR, "output.log")
FINANCE_FILE = os.path.join(PROJECT_DIR, "finance_memories.json")
HIGH_PRIORITY_FILE = os.path.join(PROJECT_DIR, "high_priority_search.json")
HISTORY_FILE = os.path.join(PROJECT_DIR, "finance_history.json")
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")
NODE_MODULES_MEM0 = os.path.join(PROJECT_DIR, "node_modules", "mem0ai")


def _run_id() -> str:
    run_id = os.environ.get("ZEALT_RUN_ID")
    assert run_id, "ZEALT_RUN_ID is not set in verifier environment."
    return run_id


def _user_id() -> str:
    return f"planner-{_run_id()}"


def _read_log() -> str:
    assert os.path.isfile(LOG_FILE), f"Log file does not exist at {LOG_FILE}."
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _load_json(path: str):
    assert os.path.isfile(path), f"Expected artifact does not exist: {path}."
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _memory_text(item) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("memory", "text", "name", "content", "data"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    return ""


# ---------------------------------------------------------------------------
# package.json / node_modules
# ---------------------------------------------------------------------------


def test_package_json_is_es_module_with_mem0ai_dep():
    data = _load_json(PACKAGE_JSON)
    assert isinstance(data, dict), "package.json must be a JSON object."
    assert data.get("type") == "module", (
        f"package.json must declare \"type\": \"module\", got {data.get('type')!r}."
    )
    deps = {}
    for section in ("dependencies", "devDependencies"):
        if isinstance(data.get(section), dict):
            deps.update(data[section])
    assert "mem0ai" in deps, (
        f"package.json must list `mem0ai` under dependencies or devDependencies. Found: {deps!r}"
    )


def test_node_modules_mem0ai_installed():
    assert os.path.isdir(NODE_MODULES_MEM0), (
        f"`mem0ai` package not installed at {NODE_MODULES_MEM0}. Run `npm install`."
    )


# ---------------------------------------------------------------------------
# Log file assertions
# ---------------------------------------------------------------------------


def test_log_contains_run_id():
    rid = _run_id()
    log = _read_log()
    assert re.search(rf"^RUN_ID:\s*{re.escape(rid)}\s*$", log, re.MULTILINE), (
        f"Log must contain a line 'RUN_ID: {rid}'. Log content:\n{log}"
    )


def test_log_contains_user_id():
    uid = _user_id()
    log = _read_log()
    assert re.search(rf"^USER_ID:\s*{re.escape(uid)}\s*$", log, re.MULTILINE), (
        f"Log must contain a line 'USER_ID: {uid}'. Log content:\n{log}"
    )


def test_log_contains_finance_count():
    log = _read_log()
    match = re.search(r"^FINANCE_COUNT:\s*(\d+)\s*$", log, re.MULTILINE)
    assert match, f"Log must contain 'FINANCE_COUNT: <int>'. Log:\n{log}"
    assert int(match.group(1)) >= 2, (
        f"FINANCE_COUNT must be >= 2, got {match.group(1)}."
    )


def test_log_contains_high_priority_count():
    log = _read_log()
    match = re.search(r"^HIGH_PRIORITY_COUNT:\s*(\d+)\s*$", log, re.MULTILINE)
    assert match, f"Log must contain 'HIGH_PRIORITY_COUNT: <int>'. Log:\n{log}"
    assert int(match.group(1)) >= 3, (
        f"HIGH_PRIORITY_COUNT must be >= 3, got {match.group(1)}."
    )


def test_log_contains_finance_id():
    log = _read_log()
    match = re.search(r"^FINANCE_ID:\s*(\S+)\s*$", log, re.MULTILINE)
    assert match, f"Log must contain 'FINANCE_ID: <non-empty id>'. Log:\n{log}"
    assert match.group(1).strip(), "FINANCE_ID value is empty in log."


def test_log_contains_multivitamin_id():
    log = _read_log()
    match = re.search(r"^MULTIVITAMIN_ID:\s*(\S+)\s*$", log, re.MULTILINE)
    assert match, f"Log must contain 'MULTIVITAMIN_ID: <non-empty id>'. Log:\n{log}"
    assert match.group(1).strip(), "MULTIVITAMIN_ID value is empty in log."


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


def test_finance_memories_artifact_shape():
    data = _load_json(FINANCE_FILE)
    assert isinstance(data, dict), "finance_memories.json must be a JSON object."
    assert data.get("user_id") == _user_id(), (
        f"finance_memories.json['user_id'] expected {_user_id()!r}, got {data.get('user_id')!r}."
    )
    assert data.get("filter_category") == "finance", (
        f"finance_memories.json['filter_category'] must be 'finance', got {data.get('filter_category')!r}."
    )
    results = data.get("results")
    assert isinstance(results, list) and len(results) >= 2, (
        f"finance_memories.json['results'] must be a list with >= 2 items, got {results!r}."
    )
    for item in results:
        assert isinstance(item, dict), f"Memory entry not a dict: {item!r}"
        assert item.get("id"), f"Memory entry missing non-empty `id`: {item!r}"
        assert _memory_text(item), (
            f"Memory entry missing non-empty text field: {item!r}"
        )


def test_high_priority_search_artifact_shape():
    data = _load_json(HIGH_PRIORITY_FILE)
    assert isinstance(data, dict), "high_priority_search.json must be a JSON object."
    assert data.get("user_id") == _user_id(), (
        f"high_priority_search.json['user_id'] expected {_user_id()!r}, got {data.get('user_id')!r}."
    )
    assert data.get("filter_priority") == "high", (
        f"high_priority_search.json['filter_priority'] must be 'high', got {data.get('filter_priority')!r}."
    )
    results = data.get("results")
    assert isinstance(results, list) and len(results) >= 3, (
        f"high_priority_search.json['results'] must be a list with >= 3 items, got {results!r}."
    )
    for item in results:
        assert isinstance(item, dict), f"Memory entry not a dict: {item!r}"
        assert item.get("id"), f"Memory entry missing non-empty `id`: {item!r}"
        assert _memory_text(item), (
            f"Memory entry missing non-empty text field: {item!r}"
        )


def test_finance_history_artifact():
    data = _load_json(HISTORY_FILE)
    assert isinstance(data, dict), "finance_history.json must be a JSON object."
    memory_id = data.get("memory_id")
    assert isinstance(memory_id, str) and memory_id.strip(), (
        f"finance_history.json['memory_id'] must be a non-empty string, got {memory_id!r}."
    )
    assert (
        data.get("updated_text")
        == "Files quarterly tax estimates in March and September with the accountant"
    ), (
        "finance_history.json['updated_text'] must equal "
        "'Files quarterly tax estimates in March and September with the accountant', "
        f"got {data.get('updated_text')!r}."
    )
    history = data.get("history")
    assert isinstance(history, list) and len(history) >= 2, (
        f"finance_history.json['history'] must be a list with >= 2 entries, got {history!r}."
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
        "finance_history.json['history'] must contain at least one entry with event/type == 'UPDATE'. "
        f"Entries: {history!r}"
    )


# ---------------------------------------------------------------------------
# Server-side verification using the Python MemoryClient (shared REST API)
# ---------------------------------------------------------------------------


def _fetch_metadata_scope(category: str):
    pytest.importorskip("mem0")
    from mem0 import MemoryClient

    api_key = os.environ.get("MEM0_API_KEY")
    assert api_key, "MEM0_API_KEY required for server-side verification."

    client = MemoryClient()
    response = client.get_all(
        filters={
            "AND": [
                {"user_id": _user_id()},
                {"metadata": {"category": category}},
            ]
        },
        version="v2",
    )
    if isinstance(response, dict) and "results" in response:
        return response["results"]
    if isinstance(response, list):
        return response
    return []


def test_server_state_finance_updated_to_september():
    memories = _fetch_metadata_scope("finance")
    assert isinstance(memories, list), (
        f"Server response should be a list, got {type(memories).__name__}."
    )
    texts = [_memory_text(m).lower() for m in memories]
    assert any("september" in t for t in texts), (
        f"Expected the updated finance memory to contain 'september'. Texts: {texts}"
    )


def test_server_state_multivitamin_deleted():
    memories = _fetch_metadata_scope("health")
    assert isinstance(memories, list), (
        f"Server response should be a list, got {type(memories).__name__}."
    )
    texts = [_memory_text(m).lower() for m in memories]
    assert not any("multivitamin" in t for t in texts), (
        f"Multivitamin memory should have been deleted. Remaining health texts: {texts}"
    )


def test_server_state_travel_survived():
    memories = _fetch_metadata_scope("travel")
    assert isinstance(memories, list), (
        f"Server response should be a list, got {type(memories).__name__}."
    )
    texts = [_memory_text(m).lower() for m in memories]
    assert any("tokyo" in t for t in texts), (
        f"Expected at least one travel memory containing 'tokyo' to survive. Texts: {texts}"
    )
