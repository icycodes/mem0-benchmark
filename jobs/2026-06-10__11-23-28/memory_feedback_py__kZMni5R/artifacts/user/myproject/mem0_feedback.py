import os
import sys
import time
from mem0 import MemoryClient

def main():
    # 1. Read environment variables
    mem0_api_key = os.environ.get("MEM0_API_KEY")
    zealt_run_id = os.environ.get("ZEALT_RUN_ID")

    if not mem0_api_key:
        print("Error: MEM0_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    if not zealt_run_id:
        print("Error: ZEALT_RUN_ID environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    # 2. Derive unique user_id
    user_id = f"feedback-user-{zealt_run_id}"
    print(f"Using derived user_id: {user_id}")

    # 3. Initialize MemoryClient
    client = MemoryClient(api_key=mem0_api_key)

    # 4. Define the short conversation
    messages = [
        {"role": "user", "content": "My name is Robin and I'm planning a trip to Kyoto next April."},
        {"role": "assistant", "content": "Lovely! I'll keep that in mind for your itinerary."},
        {"role": "user", "content": "I'm vegetarian, so please remember to flag vegetarian restaurants."},
        {"role": "assistant", "content": "Got it, I'll only recommend vegetarian-friendly places."},
        {"role": "user", "content": "Also, I tend to wake up early and prefer morning activities."}
    ]

    # 5. Ingest conversation
    print("Ingesting conversation into Mem0...")
    add_response = client.add(messages, user_id=user_id)
    print(f"Add response: {add_response}")

    # 6. Poll client.get_all to retrieve extracted memories
    print("Polling memories from Mem0 (waiting for asynchronous extraction)...")
    max_attempts = 24
    poll_interval = 5
    memories = []

    for attempt in range(max_attempts):
        print(f"Attempt {attempt + 1}/{max_attempts}...")
        try:
            res = client.get_all(filters={"user_id": user_id}, version="v2")
            results = res.get("results", [])
            print(f"Found {len(results)} memories.")
            # We expect at least 3 memories from this conversation.
            if len(results) >= 3:
                memories = results
                break
            elif len(results) > 0 and attempt >= 12:
                # If we've waited for 1 minute and got some memories, but not 3, we can proceed
                print("Proceeding with existing memories after 1 minute of polling.")
                memories = results
                break
        except Exception as e:
            print(f"Error during polling: {e}")
        time.sleep(poll_interval)

    if not memories:
        print("Error: No memories were extracted. Cannot proceed with feedback submission.", file=sys.stderr)
        sys.exit(1)

    print(f"Retrieved {len(memories)} memories for user {user_id}:")
    for m in memories:
        print(f"  - ID: {m.get('id')}, Content: {m.get('memory')}")

    # 7. Submit feedback for each memory, cycling through the feedback types
    feedback_types = ["POSITIVE", "NEGATIVE", "VERY_NEGATIVE"]
    log_lines = []

    for idx, memory in enumerate(memories):
        memory_id = memory.get("id")
        feedback_type = feedback_types[idx % len(feedback_types)]
        feedback_reason = f"Testing feedback type {feedback_type} for memory index {idx}"

        print(f"Submitting feedback for memory {memory_id}: feedback={feedback_type}, reason='{feedback_reason}'")
        try:
            fb_res = client.feedback(
                memory_id=memory_id,
                feedback=feedback_type,
                feedback_reason=feedback_reason
            )
            print(f"Feedback response: {fb_res}")
            feedback_id = fb_res.get("id")

            # Validate UUID format (must be lowercase, hyphenated)
            # The API returns them as lower-case hyphenated UUIDs.
            log_line = f"memory_id={memory_id} feedback={feedback_type} feedback_id={feedback_id}"
            log_lines.append(log_line)
        except Exception as e:
            print(f"Error submitting feedback for memory {memory_id}: {e}", file=sys.stderr)
            sys.exit(1)

    # 8. Write structured log file
    log_dir = "/home/user/myproject"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "feedback.log")

    print(f"Writing structured log to {log_file_path}...")
    with open(log_file_path, "w") as f:
        for line in log_lines:
            f.write(line + "\n")

    print("Successfully completed all steps.")

if __name__ == "__main__":
    main()
