import os
import time
from mem0 import MemoryClient

def main():
    run_id = os.environ.get("ZEALT_RUN_ID", "default_run_id")
    user_id = f"feedback-user-{run_id}"

    client = MemoryClient() # Uses MEM0_API_KEY from env

    messages = [
        {"role": "user", "content": "My name is Robin and I'm planning a trip to Kyoto next April."},
        {"role": "assistant", "content": "Lovely! I'll keep that in mind for your itinerary."},
        {"role": "user", "content": "I'm vegetarian, so please remember to flag vegetarian restaurants."},
        {"role": "assistant", "content": "Got it, I'll only recommend vegetarian-friendly places."},
        {"role": "user", "content": "Also, I tend to wake up early and prefer morning activities."}
    ]

    print(f"Adding memories for user: {user_id}")
    client.add(messages, user_id=user_id)

    print("Polling for memories...")
    memories = []
    
    # We poll because extraction is async
    for _ in range(15):
        try:
            # Using v2 as requested
            response = client.get_all(filters={"user_id": user_id}, version="v2")
            print("Response:", response)
            
            # The structure of v2 usually has a list of memories or dict with 'data'
            if isinstance(response, list):
                memories = response
            elif isinstance(response, dict):
                if "data" in response:
                    memories = response["data"]
                elif "results" in response:
                    memories = response["results"]
                elif "memories" in response:
                    memories = response["memories"]
                else:
                    memories = response
            
            if memories and len(memories) >= 1:
                # We expect around 3 memories
                if len(memories) >= 3:
                    break
                # If we have less than 3, maybe it's still extracting, wait a bit
        except Exception as e:
            print(f"Error getting memories: {e}")
            
        time.sleep(2)

    print(f"Found {len(memories)} memories.")

    feedback_types = ["POSITIVE", "NEGATIVE", "VERY_NEGATIVE"]
    log_lines = []

    for i, mem in enumerate(memories):
        mem_id = mem.get("id")
        if not mem_id:
            continue
        
        f_type = feedback_types[i % len(feedback_types)]
        
        try:
            print(f"Submitting feedback {f_type} for {mem_id}...")
            f_res = client.feedback(memory_id=mem_id, feedback=f_type, feedback_reason="Testing feedback")
            print(f"Feedback response: {f_res}")
            
            # Extract feedback ID
            f_id = None
            if isinstance(f_res, dict):
                f_id = f_res.get("id")
            elif hasattr(f_res, "id"):
                f_id = f_res.id
            elif isinstance(f_res, str):
                f_id = f_res
                
            if not f_id and isinstance(f_res, dict) and "data" in f_res:
                f_id = f_res["data"].get("id")
                
            log_line = f"memory_id={mem_id} feedback={f_type} feedback_id={f_id}"
            log_lines.append(log_line)
        except Exception as e:
            print(f"Failed to submit feedback for {mem_id}: {e}")

    log_path = "/home/user/myproject/feedback.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w") as f:
        for line in log_lines:
            f.write(line + "\n")
            
    print("Done. Wrote log to", log_path)

if __name__ == "__main__":
    main()
