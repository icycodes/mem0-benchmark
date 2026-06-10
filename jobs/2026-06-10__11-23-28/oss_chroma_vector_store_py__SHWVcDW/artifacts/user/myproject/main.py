import os
import json
import logging
import shutil
from mem0 import Memory

def setup_logging():
    log_file = "/home/user/myproject/output.log"
    # Ensure directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Configure logging to both file and console
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="w"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("mem0_chroma_demo")

def main():
    logger = setup_logging()
    logger.info("Starting Mem0 Chroma Demo execution")

    # 1. Read ZEALT_RUN_ID from environment
    run_id = os.environ.get("ZEALT_RUN_ID")
    if not run_id:
        logger.error("ZEALT_RUN_ID environment variable is not set!")
        raise ValueError("ZEALT_RUN_ID environment variable is required")
    
    collection_name = f"mem0_demo_{run_id}"
    logger.info(f"Using ZEALT_RUN_ID: {run_id}")
    logger.info(f"Chroma Collection Name: {collection_name}")

    # Ensure a clean slate by removing existing chroma_db directory
    chroma_db_dir = "/home/user/myproject/chroma_db"
    if os.path.exists(chroma_db_dir):
        logger.info(f"Cleaning up existing Chroma DB directory at {chroma_db_dir} for a clean, reproducible run...")
        shutil.rmtree(chroma_db_dir, ignore_errors=True)

    # 2. Configure Mem0 with Chroma Vector Store and OpenAI LLM (using gpt-4o-mini to avoid max_tokens issues)
    config = {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": collection_name,
                "path": chroma_db_dir
            }
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini"
            }
        }
    }

    logger.info("Initializing Memory instance from config...")
    m = Memory.from_config(config)
    logger.info("Memory instance successfully initialized.")

    # 3. Ingest conversation to establish Alex is vegan and enjoys hiking on weekends
    # We also add a distinct fact (favorite color is blue) to ensure we get >= 2 memories
    messages = [
        {"role": "user", "content": "I am Alex. I am a vegan."},
        {"role": "assistant", "content": "Got it, you are vegan."},
        {"role": "user", "content": "I also love hiking on weekends."},
        {"role": "assistant", "content": "Nice! Hiking is fun."},
        {"role": "user", "content": "My favorite color is blue."},
        {"role": "assistant", "content": "Blue is a great color."}
    ]

    logger.info("Ingesting conversation into Mem0...")
    add_response = m.add(
        messages=messages,
        user_id="alex",
        metadata={"category": "preferences"}
    )
    logger.info(f"Ingestion complete. Response: {json.dumps(add_response, indent=2)}")

    results = add_response.get("results", [])
    added_memory_ids = [item["id"] for item in results]
    logger.info(f"Added memory IDs: {added_memory_ids}")

    if len(added_memory_ids) < 2:
        logger.error(f"Expected at least 2 memories, but got {len(added_memory_ids)}")
        raise ValueError("Failed to extract at least 2 memories from the initial conversation.")

    # 4. Identify which memory is the vegan/hiking preference and which is the other one (to delete)
    updated_memory_id = None
    deleted_memory_id = None

    for item in results:
        text = item["memory"].lower()
        if "vegan" in text or "hiking" in text:
            updated_memory_id = item["id"]
        else:
            deleted_memory_id = item["id"]

    # Fallbacks in case the LLM returns unexpected structure
    if not updated_memory_id:
        updated_memory_id = added_memory_ids[0]
    if not deleted_memory_id:
        deleted_memory_id = added_memory_ids[1] if len(added_memory_ids) > 1 else None

    # Ensure they are distinct
    if updated_memory_id == deleted_memory_id:
        # Force them to be different
        for mid in added_memory_ids:
            if mid != updated_memory_id:
                deleted_memory_id = mid
                break

    logger.info(f"Selected updated_memory_id: {updated_memory_id}")
    logger.info(f"Selected deleted_memory_id: {deleted_memory_id}")

    # 5. Update the selected memory
    updated_memory_text = "Alex now prefers vegetarian food and tracks calories."
    logger.info(f"Updating memory ID {updated_memory_id} to: '{updated_memory_text}'")
    update_response = m.update(
        memory_id=updated_memory_id,
        data=updated_memory_text
    )
    logger.info(f"Update response: {update_response}")

    # 6. Delete the other memory
    logger.info(f"Deleting memory ID {deleted_memory_id}")
    delete_response = m.delete(memory_id=deleted_memory_id)
    logger.info(f"Delete response: {delete_response}")

    # 7. Call get_all to obtain the final memory inventory
    logger.info("Retrieving final memory inventory...")
    get_all_response = m.get_all(filters={"user_id": "alex"})
    logger.info(f"Final memory inventory: {json.dumps(get_all_response, indent=2)}")
    
    final_memories = get_all_response.get("results", [])
    final_memory_count = len(final_memories)
    logger.info(f"Final memory count: {final_memory_count}")

    # 8. Call search with a query about Alex's food preference to populate the search section of the report
    search_query = "What are Alex's food preferences?"
    logger.info(f"Performing semantic search with query: '{search_query}'")
    search_response = m.search(query=search_query, filters={"user_id": "alex"})
    logger.info(f"Search results: {json.dumps(search_response, indent=2)}")
    
    search_results = search_response.get("results", [])
    search_result_count = len(search_results)
    logger.info(f"Search result count: {search_result_count}")

    # 9. Build structured JSON report
    report = {
        "run_id": run_id,
        "collection_name": collection_name,
        "user_id": "alex",
        "added_memory_ids": added_memory_ids,
        "updated_memory_id": updated_memory_id,
        "updated_memory_text": updated_memory_text,
        "deleted_memory_id": deleted_memory_id,
        "search_query": search_query,
        "search_result_count": search_result_count,
        "final_memory_count": final_memory_count
    }

    report_path = "/home/user/myproject/result.json"
    logger.info(f"Writing structured JSON report to {report_path}")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("JSON report written successfully.")

    # 10. Verify functional outcomes before finishing
    logger.info("Performing self-verification of functional outcomes...")
    # Retrieve updated memory
    retrieved_updated = m.get(memory_id=updated_memory_id)
    logger.info(f"Retrieved updated memory: {retrieved_updated}")
    assert retrieved_updated is not None, "Updated memory could not be retrieved!"
    assert retrieved_updated.get("memory") == updated_memory_text, f"Memory text mismatch! Expected: '{updated_memory_text}', Got: '{retrieved_updated.get('memory')}'"
    
    # Check that deleted memory is not in get_all
    all_ids = [item["id"] for item in final_memories]
    assert deleted_memory_id not in all_ids, f"Deleted memory {deleted_memory_id} is still present in final memories!"
    assert final_memory_count == len(added_memory_ids) - 1, f"Expected final memory count to be {len(added_memory_ids) - 1}, but got {final_memory_count}"
    
    logger.info("Self-verification PASSED successfully!")
    logger.info("Execution finished successfully.")

if __name__ == "__main__":
    main()
