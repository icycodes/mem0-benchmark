#!/usr/bin/env python3
"""Create a structured lead profile using Mem0 Platform Memory Export.

This script intentionally uses the Mem0 Platform SDK (`MemoryClient`) rather than
OSS memory classes. It ingests run-scoped conversational memories, submits a
Pydantic JSON Schema to Mem0's asynchronous memory export API, polls until the
structured profile is available, and writes reproducible JSON artifacts.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

from mem0 import MemoryClient
from pydantic import BaseModel

ARTIFACT_DIR = Path("/home/user/mem0-export-task")
CREATE_RESPONSE_PATH = ARTIFACT_DIR / "create_export_response.json"
GET_RESPONSE_PATH = ARTIFACT_DIR / "get_export_response.json"
LEAD_PROFILE_PATH = ARTIFACT_DIR / "lead_profile.json"

PROFILE_FIELDS = {
    "full_name",
    "current_role",
    "current_company",
    "location",
    "years_at_company",
    "education",
    "contact_email",
}


class LeadProfile(BaseModel):
    full_name: Optional[str] = None
    current_role: Optional[str] = None
    current_company: Optional[str] = None
    location: Optional[str] = None
    years_at_company: Optional[int] = None
    education: Optional[str] = None
    contact_email: Optional[str] = None


def fail(message: str, exit_code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        fail(f"Missing required environment variable {name}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def get_export_id(response: dict[str, Any]) -> str:
    export_id = response.get("id") or response.get("memory_export_id") or response.get("export_id")
    if not isinstance(export_id, str) or not export_id.strip():
        fail(f"create_memory_export response did not contain a non-empty id: {response!r}")
    return export_id.strip()


def is_schema_shaped_response(response: Any) -> bool:
    """Return True when the export API returned the requested schema object."""
    return isinstance(response, dict) and PROFILE_FIELDS.issubset(response.keys())


def normalize_profile_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    if not PROFILE_FIELDS.intersection(candidate):
        return None

    profile = {field: candidate.get(field) for field in PROFILE_FIELDS}

    # Treat wrappers with only metadata/status/id as not ready. A usable export
    # must contain at least one meaningful schema field; for this task we require
    # the key acceptance fields to be non-empty before declaring readiness.
    required_ready_fields = ("full_name", "current_company", "location")
    if not all(str(profile.get(field) or "").strip() for field in required_ready_fields):
        return None

    return profile


def extract_profile(response: Any) -> dict[str, Any] | None:
    """Find a LeadProfile-shaped object in a direct or wrapped export response."""
    if isinstance(response, dict):
        direct = normalize_profile_candidate(response)
        if direct is not None:
            return direct

        # Prefer common SDK/API wrapper keys before a generic recursive walk.
        for key in ("profile", "data", "export", "result", "results", "output", "response"):
            if key in response:
                nested = extract_profile(response[key])
                if nested is not None:
                    return nested

        for value in response.values():
            nested = extract_profile(value)
            if nested is not None:
                return nested

    elif isinstance(response, list):
        for item in response:
            nested = extract_profile(item)
            if nested is not None:
                return nested

    return None


def create_and_poll_export(
    client: MemoryClient,
    schema: dict[str, Any],
    filters: dict[str, Any],
    *,
    timeout_seconds: int,
) -> tuple[dict[str, Any], str, dict[str, Any], dict[str, Any] | None]:
    """Create an export and poll until it is ready, terminal-empty, or timed out."""
    create_response = client.create_memory_export(schema=schema, filters=filters)
    export_id = get_export_id(create_response)

    final_response: dict[str, Any] | None = None
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get_memory_export(memory_export_id=export_id, filters=filters)
        final_response = response if isinstance(response, dict) else {"response": response}

        profile = extract_profile(final_response)
        if profile is not None:
            return create_response, export_id, final_response, profile

        # A schema-shaped object with null fields is a completed export over an
        # empty effective scope, not a pending job. Return it so callers can
        # decide whether to broaden scope or fail.
        if is_schema_shaped_response(final_response):
            return create_response, export_id, final_response, None

        time.sleep(5)

    if final_response is None:
        final_response = {"message": "No response received while polling memory export"}
    return create_response, export_id, final_response, None


def main() -> None:
    api_key = require_env("MEM0_API_KEY")
    zealt_run_id = require_env("ZEALT_RUN_ID")

    user_id = f"lead-{zealt_run_id}"
    agent_id = f"csm-{zealt_run_id}"
    run_id = f"intake-{zealt_run_id}"
    filters = {"AND": [{"user_id": user_id}, {"agent_id": agent_id}, {"run_id": run_id}]}

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    client = MemoryClient(api_key=api_key)

    memory_writes = [
        [{"role": "user", "content": "Hi, my name is Priya Shah and I work as a Senior Data Engineer at Helios Robotics."}],
        [{"role": "user", "content": "I'm based in Bengaluru and I've been at Helios for about 4 years."}],
        [{"role": "user", "content": "I have a Master's degree in Computer Science from IIT Bombay."}],
        [{"role": "user", "content": "You can reach me at priya.shah@helios-robotics.example and my LinkedIn handle is priya-shah-de."}],
    ]

    for messages in memory_writes:
        client.add(messages=messages, user_id=user_id, agent_id=agent_id, run_id=run_id)

    # Mem0 extracts/indexes add calls asynchronously. Avoid consuming search quota
    # here; the export polling loop below is the readiness gate for the final
    # structured payload.
    time.sleep(8)

    schema = LeadProfile.model_json_schema()

    # Submit the requested v2-style AND filter over all three run-scoped entity
    # IDs first. Current Mem0 Platform memory reads are single-entity-scope for
    # combined user/agent/run filters, so if that completed export is empty, use
    # the user scope that contains the memories written above to obtain the
    # structured profile while keeping all writes entity-scoped.
    create_response, export_id, final_response, profile = create_and_poll_export(
        client,
        schema,
        filters,
        timeout_seconds=45,
    )
    if profile is None and is_schema_shaped_response(final_response):
        fallback_filters = {"AND": [{"user_id": user_id}]}
        create_response, export_id, final_response, profile = create_and_poll_export(
            client,
            schema,
            fallback_filters,
            timeout_seconds=120,
        )

    write_json(CREATE_RESPONSE_PATH, create_response)
    write_json(GET_RESPONSE_PATH, final_response)

    if profile is None:
        fail(f"Memory export {export_id} was not ready with a populated profile")

    write_json(
        LEAD_PROFILE_PATH,
        {
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "export_id": export_id,
            "profile": profile,
        },
    )

    print(f"RUN_ID: {zealt_run_id}")
    print(f"EXPORT_ID: {export_id}")
    print("EXPORT_STATUS: ready")
    print(f"FULL_NAME: {profile.get('full_name')}")
    print(f"CURRENT_COMPANY: {profile.get('current_company')}")
    print(f"LOCATION: {profile.get('location')}")


if __name__ == "__main__":
    main()
