import os
import json
import logging
from mem0 import Memory

def setup_logging(log_file):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def main():
    # Environment variables
    run_id = os.getenv("ZEALT_RUN_ID", "default_run_id")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    project_dir = "/home/user/myproject"
    chroma_db_path = os.path.join(project_dir, "chroma_db")
    log_file = os.path.join(project_dir, "output.log")
    result_file = os.path.join(project_dir, "result.json")
    
    setup_logging(log_file)
    logger = logging.getLogger(__name__)
    
    collection_name = f"mem0_demo_{run_id}"
    user_id = "alex"
    
    logger.info(f"Starting Mem0 demo with run_id: {run_id}")
    logger.info(f"Collection name: {collection_name}")
    
    # Mem0 Configuration
    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
            }
        },
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": collection_name,
                "path": chroma_db_path,
            }
        }
    }
    
    # Initialize Memory
    memory = Memory.from_config(config)
    
    # 1. Add conversation
    messages = [
        {"role": "user", "content": "Hi, I'm Alex. I'm a vegan and I really enjoy hiking on weekends."},
        {"role": "assistant", "content": "Hello Alex! It's nice to meet you. I've noted that you're a vegan and love hiking."}
    ]
    
    logger.info("Adding conversation to memory...")
    add_response = memory.add(messages, user_id=user_id, metadata={"category": "preferences"})
    logger.info(f"Add response: {json.dumps(add_response)}")
    
    # Try to extract IDs from different possible response formats
    if isinstance(add_response, dict) and "results" in add_response:
        added_memory_ids = [res["id"] for res in add_response["results"]]
    elif isinstance(add_response, list):
        added_memory_ids = [res["id"] for res in add_response if isinstance(res, dict) and "id" in res]
    else:
        added_memory_ids = []
    
    if not added_memory_ids:
        logger.warning("Could not extract IDs from add_response. Fetching all memories for user.")
        all_mems_resp = memory.get_all(filters={"user_id": user_id})
        if isinstance(all_mems_resp, dict) and "results" in all_mems_resp:
             all_mems = all_mems_resp["results"]
        else:
             all_mems = all_mems_resp
        logger.info(f"All memories for user: {all_mems}")
        added_memory_ids = [m["id"] for m in all_mems if isinstance(m, dict) and "id" in m]
    
    logger.info(f"Added memory IDs: {added_memory_ids}")
    
    if len(added_memory_ids) < 2:
        # If still less than 2, maybe they were merged. Let's try to add more distinct facts.
        logger.info("Adding more distinct facts to ensure at least 2 memories...")
        memory.add("Alex lives in Seattle.", user_id=user_id, metadata={"category": "preferences"})
        all_mems_resp = memory.get_all(filters={"user_id": user_id})
        if isinstance(all_mems_resp, dict) and "results" in all_mems_resp:
             all_mems = all_mems_resp["results"]
        else:
             all_mems = all_mems_resp
        logger.info(f"Updated all memories for user: {all_mems}")
        added_memory_ids = [m["id"] for m in all_mems if isinstance(m, dict) and "id" in m]
        logger.info(f"Updated memory IDs: {added_memory_ids}")

    # 2. Semantic Search
    search_query = "What does Alex like to do on weekends?"
    logger.info(f"Performing semantic search for: '{search_query}'")
    search_results_resp = memory.search(search_query, filters={"user_id": user_id})
    if isinstance(search_results_resp, dict) and "results" in search_results_resp:
        search_results = search_results_resp["results"]
    else:
        search_results = search_results_resp
    logger.info(f"Search results: {json.dumps(search_results)}")
    
    # 3. Update a memory
    # We'll update the first memory found
    updated_memory_id = added_memory_ids[0]
    updated_memory_text = "Alex now prefers vegetarian food and tracks calories."
    logger.info(f"Updating memory {updated_memory_id}...")
    memory.update(memory_id=updated_memory_id, data=updated_memory_text)
    
    # 4. Delete a memory
    # We'll delete the second memory found
    deleted_memory_id = added_memory_ids[1]
    logger.info(f"Deleting memory {deleted_memory_id}...")
    memory.delete(memory_id=deleted_memory_id)
    
    # 5. Final inventory
    final_memories_resp = memory.get_all(filters={"user_id": user_id})
    if isinstance(final_memories_resp, dict) and "results" in final_memories_resp:
        final_memories = final_memories_resp["results"]
    else:
        final_memories = final_memories_resp
    final_memory_count = len([m for m in final_memories if isinstance(m, dict)])
    logger.info(f"Final memory count: {final_memory_count}")
    
    # 6. Final search for report
    report_search_query = "What are Alex's food preferences?"
    report_search_results_resp = memory.search(report_search_query, filters={"user_id": user_id})
    if isinstance(report_search_results_resp, dict) and "results" in report_search_results_resp:
        report_search_results = report_search_results_resp["results"]
    else:
        report_search_results = report_search_results_resp
    
    # Prepare result.json
    result = {
        "run_id": run_id,
        "collection_name": collection_name,
        "user_id": user_id,
        "added_memory_ids": added_memory_ids,
        "updated_memory_id": updated_memory_id,
        "updated_memory_text": updated_memory_text,
        "deleted_memory_id": deleted_memory_id,
        "search_query": report_search_query,
        "search_result_count": len([r for r in report_search_results if isinstance(r, dict)]),
        "final_memory_count": final_memory_count
    }
    
    with open(result_file, "w") as f:
        json.dump(result, f, indent=4)
        
    logger.info("Demo completed successfully. Result written to result.json")

if __name__ == "__main__":
    main()
