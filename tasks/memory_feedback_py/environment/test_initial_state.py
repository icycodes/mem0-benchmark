import importlib
import os

import pytest

PROJECT_DIR = "/home/user/myproject"


def test_mem0_sdk_importable():
    """The mem0 Python SDK must be installed in the task environment."""
    module = importlib.import_module("mem0")
    assert hasattr(module, "MemoryClient"), (
        "Expected 'MemoryClient' to be exposed by the 'mem0' package."
    )


def test_project_directory_exists():
    """The task explicitly names /home/user/myproject as the project path."""
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory '{PROJECT_DIR}' to exist before the task runs."
    )


def test_mem0_api_key_available():
    """The Mem0 Platform task requires MEM0_API_KEY to be present."""
    assert os.environ.get("MEM0_API_KEY"), (
        "MEM0_API_KEY must be set in the environment for the Mem0 Platform task."
    )


def test_zealt_run_id_available():
    """ZEALT_RUN_ID is used to scope the user identifier for parallel-safe runs."""
    run_id = os.environ.get("ZEALT_RUN_ID", "")
    assert run_id, "ZEALT_RUN_ID must be set in the environment."


def test_feedback_log_does_not_exist_yet():
    """The executor is responsible for creating feedback.log; it must not pre-exist."""
    log_path = os.path.join(PROJECT_DIR, "feedback.log")
    assert not os.path.exists(log_path), (
        f"feedback.log at '{log_path}' must not exist before the task runs."
    )
