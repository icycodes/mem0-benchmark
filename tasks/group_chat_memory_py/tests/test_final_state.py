import os
import re
import time

import pytest

LOG_FILE = "/home/user/group_chat/output.log"

USER_LINE_RE = re.compile(r"^User memory:\s+(?P<uid>\S+)\s+::\s+(?P<text>.+)$")
AGENT_LINE_RE = re.compile(r"^Agent memory:\s+(?P<aid>\S+)\s+::\s+(?P<text>.+)$")
SESSION_LINE_RE = re.compile(r"^Session:\s+(?P<sid>\S+)\s*$")


def _run_id() -> str:
    run_id = os.environ.get("ZEALT_RUN_ID", "")
    assert run_id, "ZEALT_RUN_ID env var must be set when running the verifier."
    return run_id


def _read_log_lines():
    assert os.path.isfile(LOG_FILE), f"Expected log file {LOG_FILE} to exist."
    with open(LOG_FILE, "r", encoding="utf-8") as fh:
        content = fh.read()
    assert content.strip(), f"Log file {LOG_FILE} is empty."
    return [line.rstrip() for line in content.splitlines() if line.strip()]


def _parse_log():
    lines = _read_log_lines()
    session_lines = [SESSION_LINE_RE.match(line) for line in lines]
    session_lines = [m for m in session_lines if m]

    user_matches = [USER_LINE_RE.match(line) for line in lines]
    user_matches = [m for m in user_matches if m]

    agent_matches = [AGENT_LINE_RE.match(line) for line in lines]
    agent_matches = [m for m in agent_matches if m]

    return session_lines, user_matches, agent_matches


def test_log_file_session_line():
    run_id = _run_id()
    session_lines, _, _ = _parse_log()
    assert len(session_lines) == 1, (
        f"Expected exactly one 'Session: ...' line in {LOG_FILE}, found {len(session_lines)}."
    )
    expected_session = f"planning-{run_id}"
    actual_session = session_lines[0].group("sid")
    assert actual_session == expected_session, (
        f"Expected session line value '{expected_session}', got '{actual_session}'."
    )


def test_log_file_user_memory_lines():
    run_id = _run_id()
    _, user_matches, _ = _parse_log()
    assert len(user_matches) >= 3, (
        f"Expected at least 3 'User memory:' lines (one per participant), got {len(user_matches)}."
    )
    user_ids = {m.group("uid") for m in user_matches}
    assert len(user_ids) >= 3, (
        f"Expected at least 3 distinct user_ids across 'User memory:' lines, got {sorted(user_ids)}."
    )
    suffix = f"-{run_id}"
    bad = [uid for uid in user_ids if not uid.endswith(suffix)]
    assert not bad, (
        f"Every user_id in 'User memory:' lines must be suffixed with '-{run_id}'. "
        f"These do not match: {bad}"
    )
    for m in user_matches:
        assert m.group("text").strip(), (
            f"User memory text for {m.group('uid')} must be non-empty."
        )


def test_log_file_agent_memory_line():
    run_id = _run_id()
    _, _, agent_matches = _parse_log()
    assert len(agent_matches) >= 1, (
        f"Expected at least 1 'Agent memory:' line in {LOG_FILE}, found {len(agent_matches)}."
    )
    suffix = f"-{run_id}"
    bad = [m.group("aid") for m in agent_matches if not m.group("aid").endswith(suffix)]
    assert not bad, (
        f"Every agent_id in 'Agent memory:' lines must be suffixed with '-{run_id}'. "
        f"These do not match: {bad}"
    )
    for m in agent_matches:
        assert m.group("text").strip(), (
            f"Agent memory text for {m.group('aid')} must be non-empty."
        )


def _wait_for_memories(client, filters, timeout=60, interval=3):
    """Poll get_all until memories appear or timeout elapses."""
    deadline = time.time() + timeout
    last = []
    while time.time() < deadline:
        try:
            resp = client.get_all(filters=filters, version="v2")
        except TypeError:
            # Older SDK without `version` kwarg
            resp = client.get_all(filters=filters)
        if isinstance(resp, dict) and "results" in resp:
            results = resp["results"]
        else:
            results = resp
        last = results or []
        if last:
            return last
        time.sleep(interval)
    return last


def test_memories_attributed_to_each_user_on_platform():
    pytest.importorskip("mem0")
    from mem0 import MemoryClient

    api_key = os.environ.get("MEM0_API_KEY")
    assert api_key, "MEM0_API_KEY env var must be set for verification."

    _, user_matches, _ = _parse_log()
    user_ids = sorted({m.group("uid") for m in user_matches})
    assert user_ids, "No user_ids parsed from log file."

    client = MemoryClient(api_key=api_key)

    discovered_memories = {}
    for uid in user_ids:
        memories = _wait_for_memories(client, {"user_id": uid})
        assert memories, (
            f"Expected at least one memory attributed to user_id={uid!r} on the Mem0 Platform, "
            "but none were returned by client.get_all(...)."
        )
        discovered_memories[uid] = memories

    # Cleanup is best-effort; verification verdict must not depend on it.
    for uid in user_ids:
        try:
            client.delete_all(user_id=uid)
        except Exception:
            pass


def test_memory_attributed_to_assistant_on_platform():
    pytest.importorskip("mem0")
    from mem0 import MemoryClient

    api_key = os.environ.get("MEM0_API_KEY")
    assert api_key, "MEM0_API_KEY env var must be set for verification."

    _, _, agent_matches = _parse_log()
    agent_ids = sorted({m.group("aid") for m in agent_matches})
    assert agent_ids, "No agent_ids parsed from log file."

    client = MemoryClient(api_key=api_key)

    for aid in agent_ids:
        memories = _wait_for_memories(client, {"agent_id": aid})
        assert memories, (
            f"Expected at least one memory attributed to agent_id={aid!r} on the Mem0 Platform, "
            "but none were returned by client.get_all(...)."
        )
        for mem in memories:
            text = mem.get("memory") if isinstance(mem, dict) else None
            assert text and str(text).strip(), (
                f"Memory record attributed to agent_id={aid!r} must have non-empty 'memory' text."
            )

    for aid in agent_ids:
        try:
            client.delete_all(agent_id=aid)
        except Exception:
            pass
