import json
import os
import re
import time

import pytest
from mem0 import MemoryClient

PROJECT_DIR = "/home/user/mem0-task"
ALICE_FILE = os.path.join(PROJECT_DIR, "alice_memories.json")
BOB_FILE = os.path.join(PROJECT_DIR, "bob_memories.json")
LOG_FILE = os.path.join(PROJECT_DIR, "output.log")


def _run_id() -> str:
    rid = os.environ.get("ZEALT_RUN_ID", "").strip()
    assert rid, "ZEALT_RUN_ID must be set for verification."
    return rid


def _ids():
    rid = _run_id()
    return {
        "alice_user": f"alice-{rid}",
        "bob_user": f"bob-{rid}",
        "agent": f"travel-agent-{rid}",
        "app": f"concierge-{rid}",
        "run": f"trip-{rid}",
    }


def _normalize_results(payload):
    """Mem0 search may return a list or a dict containing 'results'."""
    if isinstance(payload, dict) and "results" in payload:
        return payload["results"]
    if isinstance(payload, list):
        return payload
    return []


@pytest.fixture(scope="session")
def client():
    api_key = os.environ.get("MEM0_API_KEY")
    assert api_key, "MEM0_API_KEY is required for verification."
    return MemoryClient(api_key=api_key)


@pytest.fixture(scope="session", autouse=True)
def cleanup_after(client):
    yield
    ids = _ids()
    # Best-effort cleanup; do not fail the test if these error out.
    for user in (ids["alice_user"], ids["bob_user"]):
        try:
            client.delete_all(
                user_id=user,
                agent_id=ids["agent"],
                app_id=ids["app"],
                run_id=ids["run"],
            )
        except Exception:
            pass


def test_alice_artifact_exists_and_valid():
    assert os.path.isfile(ALICE_FILE), f"Expected artifact {ALICE_FILE} to exist."
    with open(ALICE_FILE) as f:
        data = json.load(f)
    ids = _ids()
    assert data.get("user_id") == ids["alice_user"], (
        f"alice_memories.json user_id should be {ids['alice_user']}, got {data.get('user_id')}"
    )
    assert data.get("agent_id") == ids["agent"], (
        f"alice_memories.json agent_id should be {ids['agent']}, got {data.get('agent_id')}"
    )
    assert data.get("app_id") == ids["app"], (
        f"alice_memories.json app_id should be {ids['app']}, got {data.get('app_id')}"
    )
    assert data.get("run_id") == ids["run"], (
        f"alice_memories.json run_id should be {ids['run']}, got {data.get('run_id')}"
    )
    results = data.get("results")
    assert isinstance(results, list) and len(results) > 0, (
        "alice_memories.json must contain a non-empty 'results' list."
    )
    for item in results:
        assert isinstance(item, dict), "Each result must be a dict."
        assert "id" in item, f"Each result must have an 'id' field; got {item}"
        assert "memory" in item, f"Each result must have a 'memory' field; got {item}"


def test_bob_artifact_exists_and_valid():
    assert os.path.isfile(BOB_FILE), f"Expected artifact {BOB_FILE} to exist."
    with open(BOB_FILE) as f:
        data = json.load(f)
    ids = _ids()
    assert data.get("user_id") == ids["bob_user"], (
        f"bob_memories.json user_id should be {ids['bob_user']}, got {data.get('user_id')}"
    )
    assert data.get("agent_id") == ids["agent"]
    assert data.get("app_id") == ids["app"]
    assert data.get("run_id") == ids["run"]
    results = data.get("results")
    assert isinstance(results, list) and len(results) > 0, (
        "bob_memories.json must contain a non-empty 'results' list."
    )
    for item in results:
        assert isinstance(item, dict)
        assert "id" in item, f"Each result must have an 'id' field; got {item}"
        assert "memory" in item, f"Each result must have a 'memory' field; got {item}"


def test_log_file_contents():
    assert os.path.isfile(LOG_FILE), f"Expected log file {LOG_FILE} to exist."
    with open(LOG_FILE) as f:
        content = f.read()

    rid = _run_id()
    # RUN_ID line exactly matches
    assert re.search(rf"^RUN_ID:\s*{re.escape(rid)}\s*$", content, re.MULTILINE), (
        f"Log must contain a line 'RUN_ID: {rid}'. Got:\n{content}"
    )

    a_match = re.search(r"^TRAVELER_A_MEMORIES:\s*(\d+)\s*$", content, re.MULTILINE)
    b_match = re.search(r"^TRAVELER_B_MEMORIES:\s*(\d+)\s*$", content, re.MULTILINE)
    assert a_match, f"Log must contain 'TRAVELER_A_MEMORIES: <int>'. Got:\n{content}"
    assert b_match, f"Log must contain 'TRAVELER_B_MEMORIES: <int>'. Got:\n{content}"

    with open(ALICE_FILE) as f:
        alice_results = json.load(f)["results"]
    with open(BOB_FILE) as f:
        bob_results = json.load(f)["results"]
    assert int(a_match.group(1)) == len(alice_results), (
        f"TRAVELER_A_MEMORIES ({a_match.group(1)}) must match alice_memories.json result count ({len(alice_results)})."
    )
    assert int(b_match.group(1)) == len(bob_results), (
        f"TRAVELER_B_MEMORIES ({b_match.group(1)}) must match bob_memories.json result count ({len(bob_results)})."
    )


def _search_scope(client, user_id, agent_id, app_id, run_id, query):
    filters = {
        "AND": [
            {"user_id": user_id},
            {"agent_id": agent_id},
            {"app_id": app_id},
            {"run_id": run_id},
        ]
    }
    # Retry briefly because the platform extracts memories asynchronously.
    last = None
    for _ in range(5):
        try:
            last = client.search(query, version="v2", filters=filters, top_k=20)
            results = _normalize_results(last)
            if results:
                return results
        except Exception as exc:  # pragma: no cover - network jitter
            last = exc
        time.sleep(2)
    return _normalize_results(last) if not isinstance(last, Exception) else []


def test_server_side_alice_has_vegetarian_memory(client):
    ids = _ids()
    results = _search_scope(
        client,
        ids["alice_user"],
        ids["agent"],
        ids["app"],
        ids["run"],
        "vegetarian Lisbon hotels and seat preferences",
    )
    assert results, "Expected at least one Alice-scoped memory on the server."
    joined = " || ".join(str(item.get("memory", "")).lower() for item in results)
    assert "vegetarian" in joined, (
        f"Alice's scope must contain a memory mentioning 'vegetarian'. Got: {joined}"
    )


def test_server_side_bob_has_shellfish_memory(client):
    ids = _ids()
    results = _search_scope(
        client,
        ids["bob_user"],
        ids["agent"],
        ids["app"],
        ids["run"],
        "shellfish allergy ski Hokkaido seat preference",
    )
    assert results, "Expected at least one Bob-scoped memory on the server."
    joined = " || ".join(str(item.get("memory", "")).lower() for item in results)
    assert "shellfish" in joined, (
        f"Bob's scope must contain a memory mentioning 'shellfish'. Got: {joined}"
    )


def test_cross_isolation_alice_not_seeing_bob(client):
    ids = _ids()
    results = _search_scope(
        client,
        ids["alice_user"],
        ids["agent"],
        ids["app"],
        ids["run"],
        "shellfish allergy ski",
    )
    joined = " ".join(str(item.get("memory", "")).lower() for item in results)
    assert "shellfish" not in joined, (
        f"Alice's scope must NOT contain Bob's 'shellfish' fact. Got: {joined}"
    )


def test_cross_isolation_bob_not_seeing_alice(client):
    ids = _ids()
    results = _search_scope(
        client,
        ids["bob_user"],
        ids["agent"],
        ids["app"],
        ids["run"],
        "vegetarian Lisbon hotels",
    )
    joined = " ".join(str(item.get("memory", "")).lower() for item in results)
    assert "vegetarian" not in joined, (
        f"Bob's scope must NOT contain Alice's 'vegetarian' fact. Got: {joined}"
    )
