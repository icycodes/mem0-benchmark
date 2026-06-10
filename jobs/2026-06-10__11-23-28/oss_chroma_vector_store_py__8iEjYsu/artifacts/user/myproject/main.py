#!/usr/bin/env python3
"""Exercise Mem0 OSS with a local persistent Chroma vector store.

The script is intentionally non-interactive. It reads ZEALT_RUN_ID from the
environment, creates a run-scoped Chroma collection, performs the requested Mem0
memory lifecycle operations for user_id="alex", and writes both machine-readable
and human-readable artifacts for verification.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

from mem0 import Memory


PROJECT_DIR = Path("/home/user/myproject")
CHROMA_DIR = PROJECT_DIR / "chroma_db"
RESULT_PATH = PROJECT_DIR / "result.json"
LOG_PATH = PROJECT_DIR / "output.log"
USER_ID = "alex"
UPDATED_MEMORY_TEXT = "Alex now prefers vegetarian food and tracks calories."
METADATA = {"category": "preferences"}


def configure_logging() -> logging.Logger:
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("mem0_chroma_demo")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def normalize_results(response: Any) -> List[Dict[str, Any]]:
    """Return a list of result dictionaries from Mem0's version-dependent shapes."""
    if response is None:
        return []
    if isinstance(response, dict):
        results = response.get("results", [])
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]
        return []
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    return []


def extract_ids(items: Iterable[Dict[str, Any]]) -> List[str]:
    ids: List[str] = []
    for item in items:
        memory_id = item.get("id") or item.get("memory_id")
        if memory_id is not None:
            ids.append(str(memory_id))
    return ids


def reset_existing_collection(collection_name: str, logger: logging.Logger) -> None:
    """Delete only this run's collection if it already exists, preserving others."""
    try:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        try:
            client.delete_collection(collection_name)
            logger.info("Deleted pre-existing Chroma collection %s", collection_name)
        except Exception as exc:  # Chroma raises if the collection does not exist.
            logger.info("No existing Chroma collection to delete for %s: %s", collection_name, exc)
        finally:
            # Mem0's Chroma wrapper may create a client with a different Settings
            # object. Clear Chroma's process-local shared-system cache so the
            # subsequent Mem0 client can open the same path cleanly.
            try:
                client.clear_system_cache()
            except Exception:
                from chromadb.api.shared_system_client import SharedSystemClient

                SharedSystemClient.clear_system_cache()
    except Exception as exc:
        logger.warning("Unable to pre-clean Chroma collection %s: %s", collection_name, exc)


def build_memory(collection_name: str) -> Memory:
    config = {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": collection_name,
                "path": str(CHROMA_DIR),
            },
        },
        # Keep Mem0's history DB local to this project rather than the default
        # user-level location. LLM/embedder are intentionally left unspecified so
        # Mem0 uses its OpenAI defaults via OPENAI_API_KEY.
        "history_db_path": str(PROJECT_DIR / "history.db"),
    }
    return Memory.from_config(config)


def add_conversation(memory: Memory, logger: logging.Logger) -> Dict[str, Any]:
    conversation = [
        {
            "role": "user",
            "content": "My name is Alex. I am vegan and I prefer plant-based meals.",
        },
        {
            "role": "user",
            "content": "I enjoy hiking on weekends with friends.",
        },
        {
            "role": "user",
            "content": "I like planning meals carefully before long trail days.",
        },
    ]

    add_kwargs: Dict[str, Any] = {
        "user_id": USER_ID,
        "metadata": METADATA,
        # infer=False stores each supplied conversation message as a separate
        # memory. This keeps the lifecycle deterministic while still using Mem0's
        # OpenAI embedder default for vectorization.
        "infer": False,
    }

    # Some Mem0 releases expose an output_format argument. The installed OSS
    # release returns the v1.1 {"results": [...]} shape without accepting that
    # argument, so pass it only when the runtime supports it.
    if "output_format" in inspect.signature(memory.add).parameters:
        add_kwargs["output_format"] = "v1.1"

    logger.info("Adding conversation for user_id=%s with metadata=%s", USER_ID, METADATA)
    response = memory.add(conversation, **add_kwargs)
    logger.info("Add response: %s", json.dumps(response, default=str))
    return response


def get_all_memories(memory: Memory) -> List[Dict[str, Any]]:
    try:
        return normalize_results(memory.get_all(user_id=USER_ID))
    except TypeError:
        return normalize_results(memory.get_all(filters={"user_id": USER_ID}))


def search_memories(memory: Memory, query: str) -> List[Dict[str, Any]]:
    try:
        return normalize_results(memory.search(query, user_id=USER_ID))
    except TypeError:
        return normalize_results(memory.search(query, filters={"user_id": USER_ID}))


def main() -> None:
    logger = configure_logging()
    run_id = os.environ.get("ZEALT_RUN_ID", "local-run")
    collection_name = f"mem0_demo_{run_id}"

    logger.info("Starting Mem0 Chroma lifecycle demo")
    logger.info("run_id=%s collection_name=%s", run_id, collection_name)
    logger.info("Chroma persistence path=%s", CHROMA_DIR)

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY must be set for Mem0's default OpenAI embedder/LLM")

    reset_existing_collection(collection_name, logger)
    memory = build_memory(collection_name)

    add_response = add_conversation(memory, logger)
    added_results = normalize_results(add_response)
    added_memory_ids = extract_ids(added_results)
    logger.info("Added memory IDs: %s", added_memory_ids)

    if len(added_memory_ids) < 2:
        raise RuntimeError(f"Expected at least two added memories, got {len(added_memory_ids)}")

    initial_search_query = "What outdoor activity does Alex enjoy on weekends?"
    initial_search_results = search_memories(memory, initial_search_query)
    logger.info(
        "Initial semantic search query=%r count=%d results=%s",
        initial_search_query,
        len(initial_search_results),
        json.dumps(initial_search_results, default=str),
    )

    updated_memory_id = added_memory_ids[0]
    deleted_memory_id = added_memory_ids[-1]
    if deleted_memory_id == updated_memory_id:
        deleted_memory_id = added_memory_ids[1]

    logger.info("Updating memory_id=%s to %r", updated_memory_id, UPDATED_MEMORY_TEXT)
    update_kwargs: Dict[str, Any] = {
        "memory_id": updated_memory_id,
        "data": UPDATED_MEMORY_TEXT,
    }
    if "metadata" in inspect.signature(memory.update).parameters:
        update_kwargs["metadata"] = METADATA
    update_response = memory.update(**update_kwargs)
    logger.info("Update response: %s", json.dumps(update_response, default=str))

    logger.info("Deleting memory_id=%s", deleted_memory_id)
    delete_response = memory.delete(memory_id=deleted_memory_id)
    logger.info("Delete response: %s", json.dumps(delete_response, default=str))

    final_memories = get_all_memories(memory)
    logger.info("Final memory inventory count=%d: %s", len(final_memories), json.dumps(final_memories, default=str))

    search_query = "What is Alex's current food preference?"
    search_results = search_memories(memory, search_query)
    logger.info(
        "Final semantic search query=%r count=%d results=%s",
        search_query,
        len(search_results),
        json.dumps(search_results, default=str),
    )

    updated_memory = memory.get(memory_id=updated_memory_id)
    deleted_still_present = any(item.get("id") == deleted_memory_id for item in final_memories)
    logger.info("Updated memory readback: %s", json.dumps(updated_memory, default=str))
    logger.info("Deleted memory still present in final inventory: %s", deleted_still_present)

    report = {
        "run_id": run_id,
        "collection_name": collection_name,
        "user_id": USER_ID,
        "added_memory_ids": added_memory_ids,
        "updated_memory_id": updated_memory_id,
        "updated_memory_text": UPDATED_MEMORY_TEXT,
        "deleted_memory_id": deleted_memory_id,
        "search_query": search_query,
        "search_result_count": len(search_results),
        "final_memory_count": len(final_memories),
        "initial_search_query": initial_search_query,
        "initial_search_result_count": len(initial_search_results),
        "final_memory_ids": extract_ids(final_memories),
        "updated_memory_readback": updated_memory,
        "deleted_memory_present_after_delete": deleted_still_present,
        "chroma_path": str(CHROMA_DIR),
    }

    RESULT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    logger.info("Wrote structured result report to %s", RESULT_PATH)
    logger.info("Completed Mem0 Chroma lifecycle demo successfully")


if __name__ == "__main__":
    main()
