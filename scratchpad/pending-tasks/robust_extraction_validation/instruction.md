Mem0 can sometimes experience silent extraction failures where the LLM extraction step fails (e.g., due to local model `<think>` blocks or token limits), returning a success code but storing no actual memories. You need to write a robust Python wrapper function `safe_add_memory(client, messages, user_id)` that wraps the `client.add()` method. The function must inspect the return value from the API and explicitly raise a custom `EmptyExtractionError` if the resulting memory array is empty.

**Constraints:**
- The function must accept an initialized `MemoryClient` instance, a message list/string, and a `user_id`.
- Do NOT modify the underlying `mem0ai` SDK code; implement the logic entirely within the wrapper function.
- Include a test call that demonstrates the custom error being raised or bypassed appropriately.