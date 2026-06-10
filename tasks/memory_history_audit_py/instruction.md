# Audit Memory Updates with Mem0 Platform History

## Background
[Mem0](https://mem0.ai/) is a managed memory layer for LLM agents. The hosted Platform exposes a `MemoryClient` Python SDK (`pip install mem0ai`) plus a REST API for adding, updating, and inspecting memories. Every change to a memory is captured in a per-memory **history log** accessible through `client.history(memory_id)` (`GET /v1/memories/{id}/history/`), which records the `event` (`ADD`, `UPDATE`, `DELETE`), the `old_memory`, and the `new_memory` for each change.

A customer-support assistant needs to mutate a user profile across a session and then produce an auditable trail of how that profile changed. Your job is to build a small Python script that performs the mutations against the real Mem0 Platform and emits a log that the auditor can verify.

## Requirements
- Connect to the Mem0 Platform with the `mem0ai` Python SDK using the API key from the `MEM0_API_KEY` environment variable.
- Scope every memory you create to a `user_id` derived from the `ZEALT_RUN_ID` environment variable so that concurrent task runs do not collide.
- Seed the user profile with a multi-turn conversation that establishes the user's current job role (e.g. a junior engineer at a fictitious company) so that Mem0 extracts at least one memory.
- Pick exactly one of the extracted memories and update its text **and** metadata using the SDK's update call so the audit trail contains a clear before/after pair.
- Retrieve the full change history for that memory via `client.history(...)` and persist a structured audit log to disk.

## Implementation Hints
- The Platform `add()` call returns a results list; each entry has an `id` plus an `event` describing whether the memory was created, updated, or deleted. Pick a result whose `event` is `ADD` for the subsequent update step.
- `client.update(memory_id=..., text=..., metadata=...)` is the canonical way to change an existing memory. The new text should make the change observable (for example, promoting the user's seniority).
- The history response is an ordered list of events; serialise it (for example with `json.dumps`) so the log can be machine-checked.
- Be defensive when picking the target memory: prefer one whose extracted `memory` text mentions the user's role rather than relying on list index alone.

## Acceptance Criteria
- Project path: /home/user/myproject
- Ensure the script is executed against the real Mem0 Platform and the resulting memories and history actually exist on the server.
- Log file: /home/user/myproject/output.log
- The script entrypoint that performs the work is `python3 /home/user/myproject/run.py` (no CLI arguments).
- The script must read `ZEALT_RUN_ID` from the environment and use the user identifier `harbor-history-${ZEALT_RUN_ID}` for every Mem0 call.
- The log file must contain, on separate lines, the following key/value pairs (in this exact format):
  - `User ID: harbor-history-<run_id>`
  - `Memory ID: <uuid>` (the memory that was updated)
  - `Events JSON: <json-array>` where the value is a JSON array obtained from `client.history(memory_id)` and includes at least one entry with `event` equal to `ADD` and at least one entry with `event` equal to `UPDATE`.
- The updated memory must remain on the Mem0 Platform after the script finishes (do not delete it) so the verifier can inspect it via the SDK.
- The latest stored text for the updated memory must mention the word `senior` (case-insensitive) so that the audit trail reflects an observable change.

