import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/mem0-node-task"


def test_node_binary_available():
    assert shutil.which("node") is not None, "node binary not found in PATH."


def test_npm_binary_available():
    assert shutil.which("npm") is not None, "npm binary not found in PATH."


def test_node_major_version_at_least_18():
    result = subprocess.run(
        ["node", "--version"], check=True, capture_output=True, text=True
    )
    version_str = result.stdout.strip().lstrip("v")
    major = int(version_str.split(".")[0])
    assert (
        major >= 18
    ), f"Node.js 18 or higher is required by the Mem0 Node SDK, found {result.stdout.strip()}."


def test_project_directory_exists():
    assert os.path.isdir(
        PROJECT_DIR
    ), f"Project directory {PROJECT_DIR} does not exist."


def test_openai_api_key_env_var_present():
    assert os.environ.get(
        "OPENAI_API_KEY"
    ), "OPENAI_API_KEY environment variable is required by Mem0 OSS for both the LLM and embedder."


def test_zealt_run_id_env_var_present():
    run_id = os.environ.get("ZEALT_RUN_ID")
    assert (
        run_id
    ), "ZEALT_RUN_ID environment variable is required to scope per-run identifiers."
