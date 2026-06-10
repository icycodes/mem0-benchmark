import importlib
import os

import pytest

PROJECT_DIR = "/home/user/myproject"


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_mem0_importable():
    try:
        mem0 = importlib.import_module("mem0")
    except ImportError as e:
        pytest.fail(f"Failed to import mem0: {e}")
    assert hasattr(mem0, "Memory"), (
        "mem0 module does not expose the `Memory` class required for OSS usage."
    )


def test_chromadb_importable():
    try:
        chromadb = importlib.import_module("chromadb")
    except ImportError as e:
        pytest.fail(f"Failed to import chromadb: {e}")
    assert hasattr(chromadb, "PersistentClient"), (
        "chromadb module does not expose `PersistentClient`."
    )


def test_openai_api_key_set():
    assert os.environ.get("OPENAI_API_KEY"), (
        "OPENAI_API_KEY environment variable must be set for Mem0 OSS defaults."
    )


def test_zealt_run_id_set():
    run_id = os.environ.get("ZEALT_RUN_ID", "")
    assert run_id, "ZEALT_RUN_ID environment variable must be set for run isolation."


def test_chroma_db_not_pre_created():
    # The executor is responsible for creating the chroma_db directory; it must
    # not exist before the task starts so we can verify it was created.
    chroma_dir = os.path.join(PROJECT_DIR, "chroma_db")
    assert not os.path.exists(chroma_dir), (
        f"{chroma_dir} should not exist before the task runs; the executor must create it."
    )


def test_result_json_not_pre_created():
    result_path = os.path.join(PROJECT_DIR, "result.json")
    assert not os.path.exists(result_path), (
        f"{result_path} should not exist before the task runs; the executor must create it."
    )
