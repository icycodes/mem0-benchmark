import importlib
import os

import pytest

PROJECT_DIR = "/home/user/mem0-export-task"


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_mem0_sdk_importable():
    try:
        mem0 = importlib.import_module("mem0")
    except ImportError as exc:  # pragma: no cover - diagnostic only
        pytest.fail(f"`mem0` Python SDK is not importable: {exc}")
    assert hasattr(mem0, "MemoryClient"), (
        "`mem0` is importable but `MemoryClient` is not exposed."
    )


def test_pydantic_v2_importable():
    try:
        pydantic = importlib.import_module("pydantic")
    except ImportError as exc:  # pragma: no cover - diagnostic only
        pytest.fail(f"`pydantic` is not importable: {exc}")
    assert hasattr(pydantic, "BaseModel"), (
        "`pydantic` is importable but `BaseModel` is not exposed."
    )


def test_mem0_api_key_present():
    api_key = os.environ.get("MEM0_API_KEY")
    assert api_key, "MEM0_API_KEY environment variable is not set."


def test_zealt_run_id_present():
    run_id = os.environ.get("ZEALT_RUN_ID")
    assert run_id, "ZEALT_RUN_ID environment variable is not set."
