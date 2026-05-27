You need to write a Python script that uses the Mem0 `MemoryClient` to perform basic Create, Read, Update, and Delete operations for a user's memory. Initialize the client, add a memory stating "I am allergic to peanuts" for `user_id="test_user_01"`. Next, search for allergy information for this user, retrieve the generated memory ID, update the memory to "I am allergic to peanuts and shellfish", and finally delete the memory using its ID. 

**Constraints:**
- Use the Python `mem0ai` SDK in Platform mode (`MemoryClient`).
- Do NOT hardcode the API key; retrieve it dynamically from the `MEM0_API_KEY` environment variable.
- The script must successfully execute all four operations sequentially and exit with code 0.