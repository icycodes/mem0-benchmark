import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/bulk-import"


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_log_file_not_yet_created():
    log_path = os.path.join(PROJECT_DIR, "output.log")
    assert not os.path.exists(log_path), (
        f"Log file {log_path} must not exist before the task runs."
    )


def test_mem0_api_key_set():
    api_key = os.environ.get("MEM0_API_KEY", "")
    assert api_key.strip(), (
        "MEM0_API_KEY environment variable must be set for the Mem0 Platform CLI."
    )


def test_zealt_run_id_set():
    run_id = os.environ.get("ZEALT_RUN_ID", "")
    assert run_id.strip(), (
        "ZEALT_RUN_ID environment variable must be set so user ids can be "
        "scoped per parallel task run."
    )


def test_jq_binary_available():
    assert shutil.which("jq") is not None, (
        "The 'jq' binary is expected to be available on PATH so the executor "
        "can parse the Mem0 CLI's JSON output."
    )


def test_mem0_python_sdk_importable():
    # The verifier will use the `mem0` Python SDK to talk to the Platform.
    # Make sure it is installed in the base image before the task starts.
    import mem0  # noqa: F401


def test_curl_binary_available():
    # curl is a common dependency and is also used by some CLI installers.
    assert shutil.which("curl") is not None, (
        "The 'curl' binary is expected to be available on PATH."
    )


def test_node_or_python_available_for_cli_install():
    # The executor MAY install either the @mem0/cli npm package
    # or the mem0-cli Python package, so at least one of npm/pip must exist.
    has_npm = shutil.which("npm") is not None
    has_pip = shutil.which("pip") is not None or shutil.which("pip3") is not None
    assert has_npm or has_pip, (
        "Neither 'npm' nor 'pip' is available on PATH; the executor needs at "
        "least one package manager to install the official Mem0 CLI."
    )
