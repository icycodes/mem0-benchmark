import json
import os
import re

import pytest

PROJECT_DIR = "/home/user/mem0-export-task"
LOG_FILE = os.path.join(PROJECT_DIR, "output.log")
CREATE_EXPORT_FILE = os.path.join(PROJECT_DIR, "create_export_response.json")
GET_EXPORT_FILE = os.path.join(PROJECT_DIR, "get_export_response.json")
LEAD_PROFILE_FILE = os.path.join(PROJECT_DIR, "lead_profile.json")


def _run_id() -> str:
    run_id = os.environ.get("ZEALT_RUN_ID")
    assert run_id, "ZEALT_RUN_ID is not set in verifier environment."
    return run_id


def _entity_ids():
    rid = _run_id()
    return {
        "user_id": f"lead-{rid}",
        "agent_id": f"csm-{rid}",
        "run_id": f"intake-{rid}",
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


def test_log_contains_export_id():
    log = _read_log()
    match = re.search(r"^EXPORT_ID:\s*(\S+)\s*$", log, re.MULTILINE)
    assert match, f"Log must contain 'EXPORT_ID: <non-empty id>'. Log:\n{log}"
    assert match.group(1).strip(), "EXPORT_ID value is empty in log."


def test_log_contains_export_status_ready():
    log = _read_log()
    assert re.search(r"^EXPORT_STATUS:\s*ready\s*$", log, re.MULTILINE), (
        f"Log must contain literal line 'EXPORT_STATUS: ready'. Log:\n{log}"
    )


def test_log_contains_profile_fields():
    log = _read_log()
    for key in ("FULL_NAME", "CURRENT_COMPANY", "LOCATION"):
        match = re.search(rf"^{key}:\s*(.+?)\s*$", log, re.MULTILINE)
        assert match, f"Log must contain '{key}: <non-empty value>'. Log:\n{log}"
        assert match.group(1).strip(), f"{key} value is empty in log."


# ---------------------------------------------------------------------------
# Artifact assertions
# ---------------------------------------------------------------------------


def test_create_export_response_artifact():
    data = _load_json(CREATE_EXPORT_FILE)
    assert isinstance(data, dict) and data, (
        f"create_export_response.json must be a non-empty JSON object, got {data!r}."
    )
    export_id = data.get("id")
    assert isinstance(export_id, str) and export_id.strip(), (
        f"create_export_response.json must contain a non-empty `id` field, got {export_id!r}."
    )


def test_get_export_response_artifact():
    data = _load_json(GET_EXPORT_FILE)
    assert data, f"get_export_response.json must be a non-empty JSON value, got {data!r}."
    assert isinstance(data, (dict, list)), (
        f"get_export_response.json must be a JSON object or list, got {type(data).__name__}."
    )


def test_lead_profile_artifact():
    data = _load_json(LEAD_PROFILE_FILE)
    assert isinstance(data, dict), "lead_profile.json must be a JSON object."
    expected = _entity_ids()
    for key, value in expected.items():
        assert data.get(key) == value, (
            f"lead_profile.json[{key}] expected {value!r}, got {data.get(key)!r}."
        )

    # export_id must match the one in create_export_response.json
    create_data = _load_json(CREATE_EXPORT_FILE)
    assert data.get("export_id") == create_data.get("id"), (
        "lead_profile.json['export_id'] must match the `id` from create_export_response.json. "
        f"export_id={data.get('export_id')!r}, create.id={create_data.get('id')!r}"
    )

    # also confirm log line uses the same export id
    log = _read_log()
    log_match = re.search(r"^EXPORT_ID:\s*(\S+)\s*$", log, re.MULTILINE)
    assert log_match and log_match.group(1) == data.get("export_id"), (
        "EXPORT_ID line in output.log must match lead_profile.json['export_id']. "
        f"log_export_id={log_match.group(1) if log_match else None!r}, "
        f"profile_export_id={data.get('export_id')!r}"
    )

    profile = data.get("profile")
    assert isinstance(profile, dict), (
        f"lead_profile.json['profile'] must be a JSON object, got {type(profile).__name__}."
    )

    required_keys = {
        "full_name",
        "current_role",
        "current_company",
        "location",
        "education",
        "contact_email",
    }
    missing = required_keys - set(profile.keys())
    assert not missing, (
        f"lead_profile.json['profile'] is missing required keys: {sorted(missing)}. "
        f"Got keys: {sorted(profile.keys())}"
    )


def test_lead_profile_content_matches_source_memories():
    data = _load_json(LEAD_PROFILE_FILE)
    profile = data.get("profile", {})

    full_name = (profile.get("full_name") or "").lower()
    company = (profile.get("current_company") or "").lower()
    location = (profile.get("location") or "").lower()
    email = (profile.get("contact_email") or "").lower()

    assert "priya" in full_name and "shah" in full_name, (
        f"profile.full_name must contain 'priya' and 'shah' (case-insensitive), got {full_name!r}."
    )
    assert "helios" in company, (
        f"profile.current_company must contain 'helios' (case-insensitive), got {company!r}."
    )
    assert "bengaluru" in location, (
        f"profile.location must contain 'bengaluru' (case-insensitive), got {location!r}."
    )
    assert "helios-robotics.example" in email, (
        f"profile.contact_email must contain 'helios-robotics.example', got {email!r}."
    )


# ---------------------------------------------------------------------------
# Server-side state via fresh MemoryClient
# ---------------------------------------------------------------------------


def _fetch_server_memories():
    from mem0 import MemoryClient

    ids = _entity_ids()
    client = MemoryClient()
    response = client.get_all(
        filters={
            "AND": [
                {"user_id": ids["user_id"]},
                {"agent_id": ids["agent_id"]},
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


def test_server_state_has_lead_memories():
    pytest.importorskip("mem0")
    api_key = os.environ.get("MEM0_API_KEY")
    assert api_key, "MEM0_API_KEY required for server-side verification."

    memories = _fetch_server_memories()
    assert isinstance(memories, list), (
        f"Server response should be a list, got {type(memories).__name__}."
    )
    assert len(memories) >= 3, (
        f"Expected >= 3 memories under the run-scoped entity IDs, got {len(memories)}: {memories!r}"
    )

    texts = [_memory_text(m).lower() for m in memories]
    assert any("priya" in t for t in texts), (
        f"Expected at least one memory containing 'Priya'. Texts: {texts}"
    )
    assert any("helios" in t for t in texts), (
        f"Expected at least one memory containing 'Helios'. Texts: {texts}"
    )
    assert any("bengaluru" in t for t in texts), (
        f"Expected at least one memory containing 'Bengaluru'. Texts: {texts}"
    )


def test_export_retrievable_again():
    """Confirm the export can be re-fetched via get_memory_export by id."""
    pytest.importorskip("mem0")
    from mem0 import MemoryClient

    profile = _load_json(LEAD_PROFILE_FILE)
    export_id = profile.get("export_id")
    assert export_id, "lead_profile.json must contain a non-empty export_id."

    client = MemoryClient()
    response = client.get_memory_export(memory_export_id=export_id)
    assert response, (
        f"get_memory_export({export_id!r}) returned an empty/None response, expected a JSON payload."
    )
    assert isinstance(response, (dict, list)), (
        f"get_memory_export must return a dict or list, got {type(response).__name__}: {response!r}"
    )
