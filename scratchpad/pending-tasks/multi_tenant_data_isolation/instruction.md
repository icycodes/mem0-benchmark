You need to create a Node.js script that demonstrates strict data isolation between multiple users. Using `MemoryClient`, add the memory "My secret passcode is 1234" for `userId: 'agent_alpha'` and "My secret passcode is 5678" for `userId: 'agent_beta'`. Execute a search query for "secret passcode" specifically bound to `agent_alpha` and log the output to verify that `agent_beta`'s data is completely isolated and excluded from the results.

**Constraints:**
- Use the Node.js `mem0ai` SDK.
- Retrieve the API key from the `MEM0_API_KEY` environment variable.
- The script must output only the memory belonging to `agent_alpha`.