import os
import re
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/bulk-import"
LOG_FILE = os.path.join(PROJECT_DIR, "output.log")


def _run_id() -> str:
    run_id = os.environ.get("ZEALT_RUN_ID", "").strip()
    assert run_id, "ZEALT_RUN_ID must be set in the verifier environment."
    return run_id


def _user_id() -> str:
    return f"harbor-bulk-import-{_run_id()}"


@pytest.fixture(scope="module")
def mem0_client():
    api_key = os.environ.get("MEM0_API_KEY", "").strip()
    assert api_key, "MEM0_API_KEY must be set in the verifier environment."
    from mem0 import MemoryClient

    return MemoryClient(api_key=api_key)


@pytest.fixture(scope="module")
def log_lines():
    assert os.path.isfile(LOG_FILE), (
        f"Log file {LOG_FILE} does not exist. The task must produce it."
    )
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        raw = f.read()
    lines = [ln.rstrip("\r\n") for ln in raw.splitlines() if ln.strip()]
    return lines


@pytest.fixture(scope="module")
def parsed_log(log_lines):
    """
    Parse the log file into structured pieces:
      {
        "user_id_line": str,
        "memory_ids": [id1, id2, id3, id4],
        "search_hits": int,
      }
    """
    assert len(log_lines) >= 6, (
        f"Expected at least 6 non-empty lines in {LOG_FILE}, "
        f"got {len(log_lines)}: {log_lines!r}"
    )

    expected_user_line = f"User ID: {_user_id()}"
    assert log_lines[0] == expected_user_line, (
        f"First log line must be '{expected_user_line}', got '{log_lines[0]}'."
    )

    memory_ids = []
    add_pattern = re.compile(r"^Added memory:\s+(\S+)\s*$")
    for idx in range(1, 5):
        match = add_pattern.match(log_lines[idx])
        assert match, (
            f"Log line {idx + 1} must match 'Added memory: <id>', "
            f"got '{log_lines[idx]}'."
        )
        memory_ids.append(match.group(1))

    search_pattern = re.compile(r"^Search hits:\s+(\d+)\s*$")
    search_match = search_pattern.match(log_lines[5])
    assert search_match, (
        f"Log line 6 must match 'Search hits: <non-negative integer>', "
        f"got '{log_lines[5]}'."
    )
    return {
        "user_id_line": log_lines[0],
        "memory_ids": memory_ids,
        "search_hits": int(search_match.group(1)),
    }


def test_mem0_cli_binary_available():
    assert shutil.which("mem0") is not None, (
        "The 'mem0' CLI binary is not on PATH; the task requires it to be "
        "installed (mem0-cli or @mem0/cli)."
    )
    result = subprocess.run(
        ["mem0", "--version"], capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"'mem0 --version' exited with code {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.stdout.strip() or result.stderr.strip(), (
        "'mem0 --version' produced no output."
    )


def test_log_file_exists():
    assert os.path.isfile(LOG_FILE), (
        f"Log file {LOG_FILE} does not exist. The task must produce it."
    )


def test_log_file_user_and_count(parsed_log):
    assert len(parsed_log["memory_ids"]) == 4, (
        f"Expected exactly 4 'Added memory:' lines, "
        f"got {len(parsed_log['memory_ids'])}."
    )
    for mid in parsed_log["memory_ids"]:
        assert mid and mid.strip(), (
            "Each 'Added memory:' line must contain a non-empty memory id."
        )


def test_search_hits_non_negative(parsed_log):
    assert parsed_log["search_hits"] >= 0, (
        f"'Search hits:' value must be a non-negative integer, "
        f"got {parsed_log['search_hits']}."
    )


def test_each_logged_memory_exists_on_platform(parsed_log, mem0_client):
    user_id = _user_id()
    for mid in parsed_log["memory_ids"]:
        try:
            memory = mem0_client.get(memory_id=mid)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"Failed to fetch memory {mid} from the Mem0 Platform: {exc}"
            )
        # MemoryClient.get returns a dict-like payload.
        owner = (
            memory.get("user_id")
            if isinstance(memory, dict)
            else getattr(memory, "user_id", None)
        )
        assert owner == user_id, (
            f"Memory {mid} is scoped to user_id={owner!r}, "
            f"expected {user_id!r}."
        )


def test_get_all_contains_all_logged_ids(parsed_log, mem0_client):
    user_id = _user_id()
    try:
        results = mem0_client.get_all(
            version="v2",
            filters={"AND": [{"user_id": user_id}]},
            page_size=100,
        )
    except TypeError:
        # Older SDK signatures may not accept page_size; fall back.
        results = mem0_client.get_all(
            version="v2", filters={"AND": [{"user_id": user_id}]}
        )

    # Normalise SDK response shape.
    if isinstance(results, dict) and "results" in results:
        items = results["results"]
    else:
        items = results
    assert isinstance(items, list), (
        f"Unexpected get_all response shape: {type(items).__name__}"
    )
    fetched_ids = {item.get("id") for item in items if isinstance(item, dict)}
    missing = [mid for mid in parsed_log["memory_ids"] if mid not in fetched_ids]
    assert not missing, (
        f"The following memory ids recorded in the log are missing from "
        f"get_all for user {user_id}: {missing}. "
        f"get_all returned ids: {sorted(fetched_ids)}"
    )


def test_dietary_search_finds_vegetarian_or_peanut(mem0_client):
    user_id = _user_id()
    try:
        search_results = mem0_client.search(
            "dietary restrictions",
            version="v2",
            filters={"AND": [{"user_id": user_id}]},
            top_k=5,
        )
    except TypeError:
        search_results = mem0_client.search(
            "dietary restrictions",
            version="v2",
            filters={"AND": [{"user_id": user_id}]},
        )

    if isinstance(search_results, dict) and "results" in search_results:
        items = search_results["results"]
    else:
        items = search_results
    assert isinstance(items, list) and items, (
        f"Expected at least one search hit for 'dietary restrictions' "
        f"scoped to {user_id}, got: {search_results!r}"
    )

    needle_pattern = re.compile(r"vegetarian|peanut", re.IGNORECASE)
    matched = False
    for item in items:
        text = (
            item.get("memory")
            if isinstance(item, dict)
            else getattr(item, "memory", "")
        )
        if text and needle_pattern.search(text):
            matched = True
            break
    assert matched, (
        "Expected at least one search result to mention 'vegetarian' or "
        f"'peanut' for user {user_id}, got: {items!r}"
    )
