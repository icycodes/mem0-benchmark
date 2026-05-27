import json
import os
import re

import pytest

PROJECT_DIR = "/home/user/mem0-node-task"
ALICE_SEARCH = os.path.join(PROJECT_DIR, "alice_search.json")
BOB_SEARCH = os.path.join(PROJECT_DIR, "bob_search.json")
ALICE_HISTORY = os.path.join(PROJECT_DIR, "alice_history.json")
OUTPUT_LOG = os.path.join(PROJECT_DIR, "output.log")
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")
MEM0_NODE_MODULE = os.path.join(PROJECT_DIR, "node_modules", "mem0ai")


def _load_json(path):
    assert os.path.isfile(path), f"Expected artifact file does not exist: {path}"
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            pytest.fail(f"File {path} is not valid JSON: {exc}")


def _run_id():
    run_id = os.environ.get("ZEALT_RUN_ID")
    assert run_id, "ZEALT_RUN_ID environment variable is not set; cannot derive scoped identifiers."
    return run_id


def test_package_json_is_esm_with_mem0ai_dependency():
    pkg = _load_json(PACKAGE_JSON)
    assert pkg.get("type") == "module", (
        f"Expected package.json `type` to be 'module' to enable ESM imports for `mem0ai/oss`, "
        f"got: {pkg.get('type')!r}"
    )
    deps = {}
    deps.update(pkg.get("dependencies") or {})
    deps.update(pkg.get("devDependencies") or {})
    assert "mem0ai" in deps, (
        f"Expected `mem0ai` in package.json dependencies, found keys: {sorted(deps.keys())}"
    )


def test_mem0ai_node_module_installed():
    assert os.path.isdir(MEM0_NODE_MODULE), (
        f"Expected the mem0ai SDK to be installed at {MEM0_NODE_MODULE}; "
        f"did the agent forget to run `npm install`?"
    )


def test_alice_search_artifact_shape():
    run_id = _run_id()
    data = _load_json(ALICE_SEARCH)
    assert isinstance(data, dict), f"{ALICE_SEARCH} must be a JSON object, got {type(data).__name__}."
    assert data.get("userId") == f"alice-{run_id}", (
        f"Expected `userId` in {ALICE_SEARCH} to be 'alice-{run_id}', got {data.get('userId')!r}."
    )
    results = data.get("results")
    assert isinstance(results, list) and len(results) >= 1, (
        f"Expected `results` in {ALICE_SEARCH} to be a non-empty list, got {results!r}."
    )
    for i, item in enumerate(results):
        assert isinstance(item, dict), f"Result #{i} in {ALICE_SEARCH} must be an object, got {type(item).__name__}."
        assert isinstance(item.get("id"), str) and item["id"], (
            f"Result #{i} in {ALICE_SEARCH} is missing a non-empty string `id` field: {item!r}"
        )
        assert isinstance(item.get("memory"), str) and item["memory"], (
            f"Result #{i} in {ALICE_SEARCH} is missing a non-empty string `memory` field: {item!r}"
        )


def test_bob_search_artifact_shape():
    run_id = _run_id()
    data = _load_json(BOB_SEARCH)
    assert isinstance(data, dict), f"{BOB_SEARCH} must be a JSON object, got {type(data).__name__}."
    assert data.get("userId") == f"bob-{run_id}", (
        f"Expected `userId` in {BOB_SEARCH} to be 'bob-{run_id}', got {data.get('userId')!r}."
    )
    results = data.get("results")
    assert isinstance(results, list) and len(results) >= 1, (
        f"Expected `results` in {BOB_SEARCH} to be a non-empty list, got {results!r}."
    )
    for i, item in enumerate(results):
        assert isinstance(item, dict), f"Result #{i} in {BOB_SEARCH} must be an object, got {type(item).__name__}."
        assert isinstance(item.get("id"), str) and item["id"], (
            f"Result #{i} in {BOB_SEARCH} is missing a non-empty string `id` field: {item!r}"
        )
        assert isinstance(item.get("memory"), str) and item["memory"], (
            f"Result #{i} in {BOB_SEARCH} is missing a non-empty string `memory` field: {item!r}"
        )


def test_alice_history_artifact_shape():
    data = _load_json(ALICE_HISTORY)
    assert isinstance(data, dict), f"{ALICE_HISTORY} must be a JSON object, got {type(data).__name__}."

    memory_id = data.get("memoryId")
    assert isinstance(memory_id, str) and memory_id, (
        f"Expected non-empty string `memoryId` in {ALICE_HISTORY}, got {memory_id!r}."
    )

    updated_text = data.get("updatedText")
    assert updated_text == "Alice is vegan and avoids all animal products", (
        f"Expected `updatedText` in {ALICE_HISTORY} to be exactly "
        f"'Alice is vegan and avoids all animal products', got {updated_text!r}."
    )

    history = data.get("history")
    assert isinstance(history, list) and len(history) >= 2, (
        f"Expected `history` in {ALICE_HISTORY} to be a list with at least 2 entries "
        f"(initial ADD + subsequent UPDATE), got {history!r}."
    )

    # At least one history entry should reference the UPDATE operation OR include the new text.
    def _entry_signals_update(entry):
        if not isinstance(entry, dict):
            return False
        for key in ("event", "action", "type", "operation"):
            value = entry.get(key)
            if isinstance(value, str) and "update" in value.lower():
                return True
        for value in entry.values():
            if isinstance(value, str) and "Alice is vegan and avoids all animal products" in value:
                return True
        return False

    assert any(_entry_signals_update(entry) for entry in history), (
        f"Expected at least one history entry in {ALICE_HISTORY} to record an UPDATE event "
        f"(or contain the new text), got: {history!r}"
    )


def test_output_log_contains_required_lines():
    assert os.path.isfile(OUTPUT_LOG), f"Expected stdout log at {OUTPUT_LOG} to exist."

    with open(OUTPUT_LOG, "r", encoding="utf-8") as f:
        log = f.read()

    run_id = _run_id()
    expected_run_line = f"RUN_ID: {run_id}"
    assert any(line.strip() == expected_run_line for line in log.splitlines()), (
        f"Expected a line exactly equal to '{expected_run_line}' in {OUTPUT_LOG}.\nLog content:\n{log}"
    )

    alice_match = re.search(r"^ALICE_RESULTS:\s+(\d+)\s*$", log, re.MULTILINE)
    assert alice_match, f"Expected a line matching `ALICE_RESULTS: <int>` in {OUTPUT_LOG}.\nLog content:\n{log}"
    alice_count = int(alice_match.group(1))
    assert alice_count >= 1, f"ALICE_RESULTS must be >= 1, got {alice_count}."

    bob_match = re.search(r"^BOB_RESULTS:\s+(\d+)\s*$", log, re.MULTILINE)
    assert bob_match, f"Expected a line matching `BOB_RESULTS: <int>` in {OUTPUT_LOG}.\nLog content:\n{log}"
    bob_count = int(bob_match.group(1))
    assert bob_count >= 1, f"BOB_RESULTS must be >= 1, got {bob_count}."

    updated_match = re.search(r"^UPDATED_MEMORY_ID:\s+(\S+)\s*$", log, re.MULTILINE)
    assert updated_match, (
        f"Expected a line matching `UPDATED_MEMORY_ID: <id>` in {OUTPUT_LOG}.\nLog content:\n{log}"
    )

    history_match = re.search(r"^HISTORY_EVENTS:\s+(\d+)\s*$", log, re.MULTILINE)
    assert history_match, (
        f"Expected a line matching `HISTORY_EVENTS: <int>` in {OUTPUT_LOG}.\nLog content:\n{log}"
    )
    history_count = int(history_match.group(1))
    assert history_count >= 2, f"HISTORY_EVENTS must be >= 2, got {history_count}."

    # Cross-check counts against the JSON artifacts.
    alice_results = _load_json(ALICE_SEARCH).get("results") or []
    bob_results = _load_json(BOB_SEARCH).get("results") or []
    alice_history = _load_json(ALICE_HISTORY)
    history_entries = alice_history.get("history") or []
    history_memory_id = alice_history.get("memoryId")

    assert alice_count == len(alice_results), (
        f"ALICE_RESULTS in log ({alice_count}) does not match len(alice_search.json.results)={len(alice_results)}."
    )
    assert bob_count == len(bob_results), (
        f"BOB_RESULTS in log ({bob_count}) does not match len(bob_search.json.results)={len(bob_results)}."
    )
    assert history_count == len(history_entries), (
        f"HISTORY_EVENTS in log ({history_count}) does not match len(alice_history.json.history)={len(history_entries)}."
    )
    assert updated_match.group(1) == history_memory_id, (
        f"UPDATED_MEMORY_ID in log ({updated_match.group(1)!r}) does not match "
        f"alice_history.json.memoryId ({history_memory_id!r})."
    )


def test_scope_isolation_keywords():
    alice_results = _load_json(ALICE_SEARCH).get("results") or []
    bob_results = _load_json(BOB_SEARCH).get("results") or []

    alice_texts = [str(item.get("memory", "")) for item in alice_results]
    bob_texts = [str(item.get("memory", "")) for item in bob_results]

    assert any("vegetarian" in text.lower() for text in alice_texts), (
        f"Expected at least one memory in alice_search.json.results to contain 'vegetarian' "
        f"(case-insensitive). Got: {alice_texts!r}"
    )
    assert any("shellfish" in text.lower() for text in bob_texts), (
        f"Expected at least one memory in bob_search.json.results to contain 'shellfish' "
        f"(case-insensitive). Got: {bob_texts!r}"
    )
    assert not any("shellfish" in text.lower() for text in alice_texts), (
        f"Scope leak: alice_search.json.results unexpectedly contains a 'shellfish' memory. "
        f"Got: {alice_texts!r}"
    )
    assert not any("vegetarian" in text.lower() for text in bob_texts), (
        f"Scope leak: bob_search.json.results unexpectedly contains a 'vegetarian' memory. "
        f"Got: {bob_texts!r}"
    )
