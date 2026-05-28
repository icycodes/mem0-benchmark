import json
import logging
import os
import shutil
import sys
from datetime import datetime

from mem0 import Memory


def setup_logger(log_path: str) -> logging.Logger:
    logger = logging.getLogger("mem0_chroma_demo")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def main() -> None:
    run_id = os.getenv("ZEALT_RUN_ID")
    if not run_id:
        raise RuntimeError("ZEALT_RUN_ID is not set")

    user_id = "alex"
    collection_name = f"mem0_demo_{run_id}"
    base_dir = "/home/user/myproject"
    chroma_path = os.path.join(base_dir, "chroma_db")
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)
    os.makedirs(chroma_path, exist_ok=True)

    log_path = os.path.join(base_dir, "output.log")
    logger = setup_logger(log_path)
    logger.info("Starting Mem0 Chroma demo")
    logger.info("Run ID: %s", run_id)
    logger.info("Collection: %s", collection_name)

    config = {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": collection_name,
                "path": chroma_path,
            },
        }
    }

    memory = Memory.from_config(config)

    conversation = [
        {"role": "user", "content": "Hi, I'm Alex. I keep a vegan diet."},
        {
            "role": "assistant",
            "content": "Thanks, Alex. I'll remember that you prefer vegan food.",
        },
        {
            "role": "user",
            "content": "On weekends I enjoy hiking trails and nature walks.",
        },
        {
            "role": "assistant",
            "content": "Great, I will note that you enjoy hiking on weekends.",
        },
        {
            "role": "user",
            "content": "I also like trying new plant-based recipes during the week.",
        },
    ]

    logger.info("Adding memories")
    add_kwargs = {
        "user_id": user_id,
        "metadata": {"category": "preferences"},
        "infer": False,
    }
    if "output_format" in Memory.add.__code__.co_varnames:
        add_kwargs["output_format"] = "v1.1"
    else:
        logger.info("output_format not supported; using default add() response")

    add_response = memory.add(conversation, **add_kwargs)

    if isinstance(add_response, dict):
        results = add_response.get("results") or add_response.get("memories") or []
    elif isinstance(add_response, list):
        results = add_response
    else:
        results = []

    added_memory_ids = []
    for item in results:
        if isinstance(item, dict) and item.get("id"):
            added_memory_ids.append(item["id"])
        elif isinstance(item, str):
            added_memory_ids.append(item)

    logger.info("Added memories: %s", added_memory_ids)

    if len(added_memory_ids) < 2:
        raise RuntimeError("Expected at least two memories to be created")

    updated_memory_id = added_memory_ids[0]
    updated_memory_text = "Alex now prefers vegetarian food and tracks calories."

    logger.info("Updating memory %s", updated_memory_id)
    memory.update(updated_memory_id, updated_memory_text)

    deleted_memory_id = added_memory_ids[1]
    logger.info("Deleting memory %s", deleted_memory_id)
    memory.delete(deleted_memory_id)

    search_query = "What does Alex prefer to eat now?"
    logger.info("Searching memories with query: %s", search_query)
    search_results = memory.search(search_query, user_id=user_id)
    if isinstance(search_results, dict):
        search_result_items = search_results.get("results") or []
    else:
        search_result_items = search_results
    search_result_count = len(search_result_items)
    logger.info("Search returned %d results", search_result_count)

    logger.info("Fetching final memory inventory")
    final_memories = memory.get_all(user_id=user_id)
    if isinstance(final_memories, dict):
        final_memory_items = final_memories.get("results") or []
    else:
        final_memory_items = final_memories
    final_memory_count = len(final_memory_items)
    logger.info("Final memory count: %d", final_memory_count)

    report = {
        "run_id": run_id,
        "collection_name": collection_name,
        "user_id": user_id,
        "added_memory_ids": added_memory_ids,
        "updated_memory_id": updated_memory_id,
        "updated_memory_text": updated_memory_text,
        "deleted_memory_id": deleted_memory_id,
        "search_query": search_query,
        "search_result_count": search_result_count,
        "final_memory_count": final_memory_count,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    result_path = os.path.join(base_dir, "result.json")
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    logger.info("Wrote report to %s", result_path)


if __name__ == "__main__":
    main()
