import os
import json
import logging
import inspect
from mem0 import Memory

# Setup logging
log_file = '/home/user/myproject/output.log'
logging.basicConfig(filename=log_file, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    run_id = os.environ.get('ZEALT_RUN_ID', 'default_run_id')
    collection_name = f"mem0_demo_{run_id}"
    db_path = "/home/user/myproject/chroma_db"
    
    logger.info(f"Starting run with ID: {run_id}")
    logger.info(f"Collection name: {collection_name}")
    logger.info(f"DB path: {db_path}")
    
    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini"
            }
        },
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": collection_name,
                "path": db_path
            }
        }
    }

    logger.info("Initializing Memory")
    m = Memory.from_config(config)
    
    conversation = [
        {"role": "user", "content": "Hi, I'm Alex. I'm a vegan."},
        {"role": "user", "content": "I also really enjoy hiking on weekends."}
    ]

    logger.info("Adding conversation to memory")
    try:
        add_result = m.add(conversation, user_id="alex", metadata={"category": "preferences"}, output_format="v1.1")
    except TypeError:
        # In mem0ai v2.0.3+, output_format is removed and v1.1 is the default
        add_result = m.add(conversation, user_id="alex", metadata={"category": "preferences"})
        
    logger.info(f"Add result: {add_result}")

    # Depending on mem0 version, add_result might be a list or a dict
    if isinstance(add_result, dict) and 'results' in add_result:
        added_memory_ids = [res['id'] for res in add_result['results'] if res.get('event') == 'ADD' or 'id' in res]
    elif isinstance(add_result, list):
        # Fallback for very old versions
        added_memory_ids = [res['id'] for res in add_result if 'id' in res]
    else:
        added_memory_ids = []
        
    logger.info(f"Added memory IDs: {added_memory_ids}")

    if len(added_memory_ids) < 2:
        logger.error(f"Failed to add at least 2 memories. Got {len(added_memory_ids)}")

    # search
    search_query = "What is Alex's food preference?"
    logger.info(f"Searching for: {search_query}")
    try:
        search_result = m.search(search_query, user_id="alex")
    except ValueError:
        # In mem0ai v2+, top-level entity params are rejected
        search_result = m.search(search_query, filters={"user_id": "alex"})
        
    logger.info(f"Search result: {search_result}")
    
    if isinstance(search_result, dict) and 'results' in search_result:
        search_result_count = len(search_result['results'])
    elif isinstance(search_result, list):
        search_result_count = len(search_result)
    else:
        search_result_count = 0

    # update
    updated_memory_id = added_memory_ids[0]
    updated_memory_text = "Alex now prefers vegetarian food and tracks calories."
    logger.info(f"Updating memory {updated_memory_id}")
    m.update(memory_id=updated_memory_id, data=updated_memory_text)

    # delete
    deleted_memory_id = added_memory_ids[1]
    logger.info(f"Deleting memory {deleted_memory_id}")
    m.delete(memory_id=deleted_memory_id)

    # get_all
    logger.info("Getting all memories for alex")
    try:
        final_memories = m.get_all(user_id="alex")
    except ValueError:
        final_memories = m.get_all(filters={"user_id": "alex"})
        
    logger.info(f"Final memories: {final_memories}")
    
    if isinstance(final_memories, dict) and 'results' in final_memories:
        final_memory_count = len(final_memories['results'])
    elif isinstance(final_memories, list):
        final_memory_count = len(final_memories)
    else:
        final_memory_count = 0

    # write result.json
    result = {
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

    with open('/home/user/myproject/result.json', 'w') as f:
        json.dump(result, f, indent=4)
    
    logger.info("Finished successfully")

if __name__ == "__main__":
    main()
