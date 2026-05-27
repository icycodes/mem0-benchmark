# Mem0 Platform — Entity-Partitioned Memory Ingest and Filtered Search (Python)

## Background

A travel concierge product needs a long-term memory layer that keeps each traveler's preferences isolated by user, agent, and session. The product uses **Mem0 Platform** (`mem0ai` Python SDK) to ingest multi-turn conversations and later retrieve memories with **v2 compound filters**.

Your job is to write a Python script that:

1. Ingests multi-turn conversations for **two different travelers** under the same shared agent and app, scoped by `user_id`, `agent_id`, `app_id`, and a `run_id` derived from `ZEALT_RUN_ID`.
2. Issues a **v2 compound filter search** to retrieve only the memories for one specific traveler within the current run, and writes the search results to a JSON artifact.
3. Demonstrates entity isolation by writing a second JSON artifact that contains the memories of the other traveler in the same run.

This covers the real-world pattern documented in the Mem0 Platform docs:
- Entity-Scoped Memory: https://docs.mem0.ai/platform/features/entity-scoped-memory
- Memory Filters (v2): https://docs.mem0.ai/platform/features/v2-memory-filters
- Search Memories: https://docs.mem0.ai/api-reference/memory/v2-search-memories

## Requirements

- Use the **Mem0 Platform Python SDK** (`from mem0 import MemoryClient`). Do NOT use the open-source `Memory` class.
- Read `MEM0_API_KEY` and `ZEALT_RUN_ID` from the environment.
- Build a per-run identifier suffix from `ZEALT_RUN_ID` and use it to scope every write and read so concurrent runs do not collide.
- Add the following two multi-turn conversations using `client.add(...)`. The exact `messages` list for each traveler is supplied below; you MUST send them verbatim.
  - Traveler A — `user_id = "alice-${run-id}"`:
    - `{"role": "user", "content": "I am vegetarian and I love boutique hotels in Lisbon."}`
    - `{"role": "assistant", "content": "Noted. I'll save your dietary preference and Lisbon hotel taste."}`
    - `{"role": "user", "content": "Also, I always book aisle seats on flights."}`
  - Traveler B — `user_id = "bob-${run-id}"`:
    - `{"role": "user", "content": "I'm allergic to shellfish and I prefer ski resorts in Hokkaido."}`
    - `{"role": "assistant", "content": "Got it. Logged your shellfish allergy and Hokkaido ski preference."}`
    - `{"role": "user", "content": "I always want a window seat on flights."}`
- Every `add` call MUST also pass:
  - `agent_id = "travel-agent-${run-id}"`
  - `app_id   = "concierge-${run-id}"`
  - `run_id   = "trip-${run-id}"`
- After ingesting, perform a v2 filter search (the SDK call is `client.search(query, version="v2", filters=..., top_k=20)`) for each traveler that:
  - Uses the natural-language query string `"What are this traveler's flight, food, and lodging preferences?"`.
  - Restricts results with an `AND` compound filter on `user_id`, `agent_id`, `app_id`, and `run_id` so that only the targeted traveler's memories under the current run are returned.
- Write the search results for Traveler A to `/home/user/mem0-task/alice_memories.json` and for Traveler B to `/home/user/mem0-task/bob_memories.json`. Each file MUST be a JSON object with the following shape (preserving the entire list returned from `client.search`):

  ```json
  {
    "user_id": "alice-${run-id}",
    "agent_id": "travel-agent-${run-id}",
    "app_id": "concierge-${run-id}",
    "run_id": "trip-${run-id}",
    "results": [ /* the list from client.search(...)["results"] (or the raw list if the SDK returns a list) */ ]
  }
  ```

- Print a final log line to stdout in the exact format:
  - `RUN_ID: <ZEALT_RUN_ID>`
  - `TRAVELER_A_MEMORIES: <N>`
  - `TRAVELER_B_MEMORIES: <N>`
  where `<N>` is the integer count of memories returned for each traveler.

## Implementation Hints

- The Mem0 Platform v2 `search` endpoint requires entity IDs to be passed inside `filters` (top-level entity kwargs are rejected). Wrap them in an `AND` clause.
- `client.search(...)` may return either a list or a dict containing `results`. Normalize to a list of dicts before writing the JSON artifact.
- Memory extraction is asynchronous on the platform side; you may need a short retry/wait loop after `client.add` before `search` returns the extracted memories.
- Use `client.delete_all(user_id="alice-${run-id}", agent_id="travel-agent-${run-id}", app_id="concierge-${run-id}", run_id="trip-${run-id}")` (and the same for Bob) only if you want to make the script idempotent — it is not strictly required.
- The `run-id` value comes from the `ZEALT_RUN_ID` environment variable. Apply it to every shared identifier (user_id, agent_id, app_id, run_id) so concurrent test runs are isolated.

## Acceptance Criteria

- Project path: `/home/user/mem0-task`
- Ensure the script is executed end-to-end against the live Mem0 Platform and the output artifacts exist.
- Log file: `/home/user/mem0-task/output.log` — stdout from the script MUST be captured/redirected to this file and contain:
  - `RUN_ID: <ZEALT_RUN_ID>`
  - `TRAVELER_A_MEMORIES: <integer >= 1>`
  - `TRAVELER_B_MEMORIES: <integer >= 1>`
- Output artifacts:
  - `/home/user/mem0-task/alice_memories.json`
  - `/home/user/mem0-task/bob_memories.json`
  - Each file is a valid JSON object with keys `user_id`, `agent_id`, `app_id`, `run_id`, `results`.
  - `results` is a non-empty list of memory objects, each containing at least the fields `id` and `memory`.
- Server-side effects:
  - At least one memory containing the keyword `vegetarian` (case-insensitive) is retrievable under `user_id=alice-${run-id}`, `agent_id=travel-agent-${run-id}`, `app_id=concierge-${run-id}`, `run_id=trip-${run-id}`.
  - At least one memory containing the keyword `shellfish` (case-insensitive) is retrievable under `user_id=bob-${run-id}` with the same agent/app/run scope.
  - A v2 filtered search for Alice's scope does NOT return any memory containing the keyword `shellfish`, and Bob's scope does NOT return any memory containing the keyword `vegetarian`.
- Use `${run-id}` from the `ZEALT_RUN_ID` environment variable. No identifiers may be hard-coded without the suffix.

