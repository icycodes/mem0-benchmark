You need to build a simple multi-agent shared memory workflow in Node.js. Agent A (Researcher) discovers a fact and stores it. Use `MemoryClient` to add the memory "The project deadline is December 1st" under a shared `agentId: 'project_x_team'`. Then, simulate Agent B (Writer) by searching for "deadline" using the same `agentId: 'project_x_team'` to retrieve the shared context. Log the retrieved deadline memory to the console.

**Constraints:**
- Use the Node.js `mem0ai` SDK in platform mode.
- Context sharing must strictly be achieved using the `agentId` parameter, NOT `userId`.
- The script must successfully simulate the handoff by logging the stored context.