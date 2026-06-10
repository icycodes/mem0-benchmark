import importlib
import os

import pytest

PROJECT_DIR = "/home/user/mem0-task"


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist at the start of the task."
    )


def test_mem0_sdk_importable():
    try:
        mem0 = importlib.import_module("mem0")
    except ImportError as exc:
        pytest.fail(f"Mem0 Python SDK is not importable: {exc}")
    assert hasattr(mem0, "MemoryClient"), (
        "Expected `mem0.MemoryClient` to be available in the installed mem0ai SDK."
    )


def test_mem0_api_key_env_present():
    assert os.environ.get("MEM0_API_KEY"), (
        "MEM0_API_KEY environment variable must be provided for the task."
    )


def test_openai_api_key_env_present():
    assert os.environ.get("OPENAI_API_KEY"), (
        "OPENAI_API_KEY environment variable must be provided per the research plan integration contract."
    )


def test_zealt_run_id_env_present():
    run_id = os.environ.get("ZEALT_RUN_ID", "")
    assert run_id, "ZEALT_RUN_ID environment variable must be provided for parallel-run safety."


def test_output_artifacts_not_yet_created():
    for name in ("alice_memories.json", "bob_memories.json", "output.log"):
        path = os.path.join(PROJECT_DIR, name)
        assert not os.path.exists(path), (
            f"Output artifact {path} must not exist before the executor runs the task."
        )
