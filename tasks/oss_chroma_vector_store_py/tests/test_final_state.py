import json
import os

import pytest

PROJECT_DIR = "/home/user/myproject"
RESULT_JSON = os.path.join(PROJECT_DIR, "result.json")
OUTPUT_LOG = os.path.join(PROJECT_DIR, "output.log")
CHROMA_DIR = os.path.join(PROJECT_DIR, "chroma_db")
CHROMA_SQLITE = os.path.join(CHROMA_DIR, "chroma.sqlite3")

EXPECTED_UPDATED_TEXT = "Alex now prefers vegetarian food and tracks calories."


@pytest.fixture(scope="session")
def report():
    assert os.path.isfile(RESULT_JSON), f"Result file not found at {RESULT_JSON}."
    with open(RESULT_JSON, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"result.json is not valid JSON: {e}")
    assert isinstance(data, dict), "result.json must contain a JSON object."
    return data


@pytest.fixture(scope="session")
def run_id():
    rid = os.environ.get("ZEALT_RUN_ID", "")
    assert rid, "ZEALT_RUN_ID environment variable is not set in the verifier."
    return rid


def test_output_log_exists_and_nonempty():
    assert os.path.isfile(OUTPUT_LOG), f"Log file not found at {OUTPUT_LOG}."
    assert os.path.getsize(OUTPUT_LOG) > 0, f"Log file {OUTPUT_LOG} is empty."


def test_chroma_persistence_files_exist():
    assert os.path.isdir(CHROMA_DIR), (
        f"Chroma persistence directory {CHROMA_DIR} does not exist."
    )
    assert os.path.isfile(CHROMA_SQLITE), (
        f"Chroma persistent SQLite file {CHROMA_SQLITE} does not exist; "
        "the executor must initialize Chroma with on-disk persistence."
    )


def test_report_has_required_keys(report):
    required_keys = {
        "run_id",
        "collection_name",
        "user_id",
        "added_memory_ids",
        "updated_memory_id",
        "updated_memory_text",
        "deleted_memory_id",
        "search_query",
        "search_result_count",
        "final_memory_count",
    }
    missing = required_keys - set(report.keys())
    assert not missing, f"result.json is missing required keys: {sorted(missing)}"


def test_report_run_id_matches_env(report, run_id):
    assert report["run_id"] == run_id, (
        f"result.json run_id mismatch: report has {report['run_id']!r} "
        f"but ZEALT_RUN_ID is {run_id!r}."
    )


def test_report_collection_name(report, run_id):
    expected = f"mem0_demo_{run_id}"
    assert report["collection_name"] == expected, (
        f"collection_name should be {expected!r}, got {report['collection_name']!r}."
    )


def test_report_user_id(report):
    assert report["user_id"] == "alex", (
        f"user_id should be 'alex', got {report['user_id']!r}."
    )


def test_added_memory_ids_valid(report):
    ids = report["added_memory_ids"]
    assert isinstance(ids, list), "added_memory_ids must be a list."
    assert all(isinstance(i, str) and i for i in ids), (
        "All entries in added_memory_ids must be non-empty strings."
    )
    assert len(ids) >= 2, (
        f"added_memory_ids should contain at least 2 entries, got {len(ids)}."
    )
    assert len(set(ids)) == len(ids), "added_memory_ids must not contain duplicates."


def test_updated_memory_id_is_in_added(report):
    assert report["updated_memory_id"] in report["added_memory_ids"], (
        "updated_memory_id must be one of the originally added memory IDs."
    )


def test_deleted_memory_id_is_in_added_and_distinct(report):
    assert report["deleted_memory_id"] in report["added_memory_ids"], (
        "deleted_memory_id must be one of the originally added memory IDs."
    )
    assert report["deleted_memory_id"] != report["updated_memory_id"], (
        "deleted_memory_id must differ from updated_memory_id."
    )


def test_updated_memory_text_value(report):
    assert report["updated_memory_text"] == EXPECTED_UPDATED_TEXT, (
        f"updated_memory_text must equal {EXPECTED_UPDATED_TEXT!r}, "
        f"got {report['updated_memory_text']!r}."
    )


def test_search_query_nonempty(report):
    assert isinstance(report["search_query"], str) and report["search_query"], (
        "search_query must be a non-empty string."
    )


def test_search_result_count_int(report):
    src = report["search_result_count"]
    assert isinstance(src, int) and src >= 0, (
        f"search_result_count must be a non-negative integer, got {src!r}."
    )


def test_final_memory_count_matches_expected(report):
    expected = len(report["added_memory_ids"]) - 1
    assert report["final_memory_count"] == expected, (
        f"final_memory_count should equal added_memory_ids - 1 = {expected}, "
        f"got {report['final_memory_count']}."
    )


def _normalize_results(value):
    """Mem0 OSS may return either {'results': [...]} (v1.1) or a bare list."""
    if isinstance(value, dict) and "results" in value:
        return value["results"]
    if isinstance(value, list):
        return value
    raise AssertionError(
        f"Unexpected Mem0 response shape: {type(value).__name__}: {value!r}"
    )


def test_mem0_chroma_state_via_sdk(report):
    """Re-open the Chroma-backed Memory and verify functional outcomes."""
    from mem0 import Memory

    config = {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": report["collection_name"],
                "path": CHROMA_DIR,
            },
        }
    }
    m = Memory.from_config(config)

    # 1. Updated memory has the expected text.
    updated = m.get(memory_id=report["updated_memory_id"])
    assert isinstance(updated, dict), (
        f"m.get() should return a dict for an existing memory, got {type(updated)}."
    )
    mem_text = updated.get("memory") or updated.get("text") or ""
    assert mem_text == EXPECTED_UPDATED_TEXT, (
        f"Memory {report['updated_memory_id']!r} content should be "
        f"{EXPECTED_UPDATED_TEXT!r}, got {mem_text!r}."
    )

    # 2. get_all() count matches final_memory_count and deleted ID is absent.
    all_memories = _normalize_results(m.get_all(user_id="alex"))
    actual_ids = {
        item.get("id") for item in all_memories if isinstance(item, dict)
    }
    assert len(all_memories) == report["final_memory_count"], (
        f"m.get_all(user_id='alex') should return {report['final_memory_count']} "
        f"memories, got {len(all_memories)}."
    )
    assert report["deleted_memory_id"] not in actual_ids, (
        f"deleted_memory_id {report['deleted_memory_id']!r} must not appear in "
        f"m.get_all() results, but it does."
    )


def test_chroma_collection_exists():
    """Verify the Chroma collection name directly via the chromadb client."""
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collections = client.list_collections()
    names = []
    for c in collections:
        # Different chromadb versions return Collection objects or dicts.
        name = getattr(c, "name", None) or (c.get("name") if isinstance(c, dict) else None)
        if name:
            names.append(name)

    with open(RESULT_JSON, "r", encoding="utf-8") as f:
        report = json.load(f)
    expected_name = report["collection_name"]
    assert expected_name in names, (
        f"Chroma should contain a collection named {expected_name!r}, "
        f"got collections: {names}."
    )
