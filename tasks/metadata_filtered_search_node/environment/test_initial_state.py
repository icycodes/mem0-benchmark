import os
import shutil

PROJECT_DIR = "/home/user/mem0-metadata-task"


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_node_binary_available():
    assert shutil.which("node") is not None, (
        "`node` binary is not available in PATH."
    )


def test_npm_binary_available():
    assert shutil.which("npm") is not None, (
        "`npm` binary is not available in PATH."
    )


def test_mem0_python_sdk_importable():
    """The verifier uses the Python SDK to validate server-side state."""
    import importlib

    try:
        mem0 = importlib.import_module("mem0")
    except ImportError as exc:  # pragma: no cover - diagnostic message only
        import pytest

        pytest.fail(f"`mem0` Python SDK is not importable for the verifier: {exc}")
    assert hasattr(mem0, "MemoryClient"), (
        "`mem0` is importable but `MemoryClient` is not exposed."
    )


def test_mem0_api_key_present():
    api_key = os.environ.get("MEM0_API_KEY")
    assert api_key, "MEM0_API_KEY environment variable is not set."


def test_zealt_run_id_present():
    run_id = os.environ.get("ZEALT_RUN_ID")
    assert run_id, "ZEALT_RUN_ID environment variable is not set."
