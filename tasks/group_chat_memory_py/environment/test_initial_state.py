import importlib
import os

import pytest

PROJECT_DIR = "/home/user/group_chat"


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist before the task starts."
    )


def test_mem0_python_sdk_importable():
    try:
        mem0 = importlib.import_module("mem0")
    except Exception as exc:  # pragma: no cover - failure path is informative only
        pytest.fail(f"Failed to import the mem0 Python SDK: {exc!r}")
    assert hasattr(mem0, "MemoryClient"), (
        "mem0.MemoryClient is not available; the managed Mem0 SDK is required for this task."
    )


def test_mem0_api_key_env_present():
    assert os.environ.get("MEM0_API_KEY"), (
        "MEM0_API_KEY environment variable must be set so the task can authenticate against the Mem0 Platform."
    )


def test_zealt_run_id_env_present():
    run_id = os.environ.get("ZEALT_RUN_ID", "")
    assert run_id, "ZEALT_RUN_ID environment variable must be set for parallel-run isolation."
    assert run_id.startswith("zr-") and all(
        ch.isalnum() or ch == "-" for ch in run_id
    ), f"ZEALT_RUN_ID={run_id!r} does not match the expected 'zr-[a-z0-9]+' format."
