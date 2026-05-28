import os
import time
from typing import Any, Dict, List

from mem0 import MemoryClient


CONVERSATION = [
    {"role": "user", "content": "My name is Robin and I'm planning a trip to Kyoto next April."},
    {"role": "assistant", "content": "Lovely! I'll keep that in mind for your itinerary."},
    {"role": "user", "content": "I'm vegetarian, so please remember to flag vegetarian restaurants."},
    {"role": "assistant", "content": "Got it, I'll only recommend vegetarian-friendly places."},
    {"role": "user", "content": "Also, I tend to wake up early and prefer morning activities."},
]

FEEDBACK_TYPES = ["POSITIVE", "NEGATIVE", "VERY_NEGATIVE"]


def _extract_memories(response: Any) -> List[Dict[str, Any]]:
    if isinstance(response, dict):
        if "memories" in response and isinstance(response["memories"], list):
            return response["memories"]
        if "data" in response and isinstance(response["data"], list):
            return response["data"]
    if isinstance(response, list):
        return response
    return []


def _memory_id(memory: Dict[str, Any]) -> str:
    memory_id = memory.get("id") or memory.get("memory_id")
    if not memory_id:
        raise ValueError(f"Missing memory id in payload: {memory}")
    return memory_id


def main() -> None:
    run_id = os.getenv("ZEALT_RUN_ID")
    if not run_id:
        raise EnvironmentError("ZEALT_RUN_ID is required")

    user_id = f"feedback-user-{run_id}"
    api_key = os.getenv("MEM0_API_KEY")
    if not api_key:
        raise EnvironmentError("MEM0_API_KEY is required")

    client = MemoryClient(api_key=api_key)
    client.add(messages=CONVERSATION, user_id=user_id)

    memories: List[Dict[str, Any]] = []
    for _ in range(15):
        response = client.get_all(filters={"user_id": user_id}, version="v2")
        memories = _extract_memories(response)
        if memories:
            break
        time.sleep(2)

    if not memories:
        raise RuntimeError("No memories returned after polling")

    log_lines: List[str] = []
    for index, memory in enumerate(memories):
        memory_id = _memory_id(memory)
        feedback = FEEDBACK_TYPES[index % len(FEEDBACK_TYPES)]
        feedback_reason = f"Automated feedback cycle ({feedback.lower()})."
        feedback_response = client.feedback(
            memory_id=memory_id,
            feedback=feedback,
            feedback_reason=feedback_reason,
        )
        if not isinstance(feedback_response, dict) or "id" not in feedback_response:
            raise RuntimeError(f"Unexpected feedback response: {feedback_response}")
        feedback_id = feedback_response["id"]
        log_lines.append(
            f"memory_id={memory_id} feedback={feedback} feedback_id={feedback_id}"
        )

    log_path = "/home/user/myproject/feedback.log"
    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    main()
