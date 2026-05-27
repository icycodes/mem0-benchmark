import importlib
import os

import pytest

PROJECT_DIR = "/home/user/myproject"


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist before the task starts."
    )


def test_mem0ai_package_importable():
    try:
        mem0 = importlib.import_module("mem0")
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail(f"Failed to import the mem0ai Python package: {exc!r}")
    assert hasattr(mem0, "MemoryClient"), (
        "The mem0ai package is installed but does not expose MemoryClient."
    )


def test_mem0_api_key_env_var_set():
    value = os.environ.get("MEM0_API_KEY")
    assert value, (
        "MEM0_API_KEY environment variable must be set so the task can authenticate "
        "with the Mem0 Platform."
    )


def test_zealt_run_id_env_var_set():
    value = os.environ.get("ZEALT_RUN_ID")
    assert value, (
        "ZEALT_RUN_ID environment variable must be set so the task can scope memories "
        "to an isolated user_id."
    )
