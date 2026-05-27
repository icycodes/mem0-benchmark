import os
import time
import json
from mem0 import MemoryClient

def main():
    api_key = os.environ.get("MEM0_API_KEY")
    run_id = os.environ.get("ZEALT_RUN_ID")
    
    if not api_key:
        print("Error: MEM0_API_KEY environment variable is not set.")
        return
    if not run_id:
        print("Error: ZEALT_RUN_ID environment variable is not set.")
        return

    user_id = f"feedback-user-{run_id}"
    print(f"Using user_id: {user_id}")
    
    client = MemoryClient(api_key=api_key)

    messages = [
        {"role": "user", "content": "My name is Robin and I'm planning a trip to Kyoto next April."},
        {"role": "assistant", "content": "Lovely! I'll keep that in mind for your itinerary."},
        {"role": "user", "content": "I'm vegetarian, so please remember to flag vegetarian restaurants."},
        {"role": "assistant", "content": "Got it, I'll only recommend vegetarian-friendly places."},
        {"role": "user", "content": "Also, I tend to wake up early and prefer morning activities."}
    ]

    print("Adding conversation to Mem0...")
    client.add(messages, user_id=user_id)

    # Extraction is asynchronous, wait and poll
    print("Waiting for memories to be extracted...")
    memories = []
    max_retries = 12
    for i in range(max_retries):
        try:
            # Using version="v2" as requested
            response = client.get_all(filters={"user_id": user_id}, version="v2")
            
            # The SDK might return the list directly or wrapped
            if isinstance(response, list):
                memories = response
            elif isinstance(response, dict) and "memories" in response:
                memories = response["memories"]
            elif isinstance(response, dict) and "results" in response:
                memories = response["results"]
            else:
                # Some versions might have it under another key or it's just empty
                memories = []
                
            if memories:
                break
        except Exception as e:
            print(f"Error fetching memories: {e}")
            
        print(f"Attempt {i+1}: No memories found yet. Sleeping 10s...")
        time.sleep(10)

    if not memories:
        print("Failed to retrieve memories for the user.")
        return

    print(f"Retrieved {len(memories)} memories.")

    feedback_types = ["POSITIVE", "NEGATIVE", "VERY_NEGATIVE"]
    log_file_path = "/home/user/myproject/feedback.log"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    
    with open(log_file_path, "w") as log_file:
        for i, memory in enumerate(memories):
            memory_id = memory.get("id")
            if not memory_id:
                continue
                
            feedback_type = feedback_types[i % len(feedback_types)]
            reason = f"Automated feedback {feedback_type} for run {run_id}"
            
            print(f"Submitting {feedback_type} feedback for memory {memory_id}...")
            try:
                feedback_res = client.feedback(
                    memory_id=memory_id,
                    feedback=feedback_type,
                    feedback_reason=reason
                )
                
                # feedback_res is expected to contain 'id'
                feedback_id = feedback_res.get("id", "unknown-id")
                
                log_line = f"memory_id={memory_id} feedback={feedback_type} feedback_id={feedback_id}\n"
                log_file.write(log_line)
                log_file.flush()
                print(f"Success: {log_line.strip()}")
            except Exception as e:
                print(f"Error submitting feedback for {memory_id}: {e}")

    print(f"Feedback submission complete. Log written to {log_file_path}")

if __name__ == "__main__":
    main()
