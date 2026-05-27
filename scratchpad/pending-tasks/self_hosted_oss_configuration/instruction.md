You need to configure the open-source Mem0 `Memory` class in Python to use custom self-hosted infrastructure. Write a script that uses `Memory.from_config()` with a configuration dictionary specifying OpenAI as the LLM provider (using the `gpt-4o` model) and Qdrant as the vector store provider (pointing to `localhost` on port `6333`). Initialize the memory and add the string "Self-hosted memory initialized" for `user_id="admin"`.

**Constraints:**
- Use the `Memory` class from the OSS mode, NOT `MemoryClient`.
- The script must correctly construct the nested `config` dictionary exactly as required by the Mem0 OSS specification.
- Ensure the `OPENAI_API_KEY` environment variable is used for the LLM provider.