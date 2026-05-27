I have completed the research for Mem0 and compiled the findings into a structured research plan. The plan covers the Mem0 Platform, Python SDK, and Node.js SDK, including core APIs, real-world use cases, developer friction points, and evaluation ideas.

The research plan has been written to `mem0/mem0.md`.

### Summary of Research Findings

*   **Mem0 Platform**: A managed service providing persistent memory for AI agents. It features multi-level memory (User, Session, Agent), advanced retrieval (hybrid search, reranking), and a dashboard for management.
*   **Mem0 SDKs**: Available for both Python and Node.js. Both SDKs support two modes:
    *   **Platform Mode**: Uses `MemoryClient` to interact with the managed service.
    *   **Open Source (OSS) Mode**: Uses `Memory` to interact with self-hosted infrastructure (Qdrant, Neo4j, etc.).
*   **Friction Points**: Identified common challenges such as JSON parsing issues with Ollama (specifically with `<think>` blocks), Webpack resolution errors in Next.js, and token limit constraints in extraction pipelines.
*   **Evaluation Ideas**: Proposed tasks ranging from basic memory CRUD operations to complex multi-tenant isolation and webhook-triggered workflows.

The final document includes the required "Integration" section with environment variable specifications.

# Research Plan: Mem0

## 1. Library Overview

*   **Description**: Mem0 is a universal memory layer for AI agents and applications. It provides persistent, self-improving context that survives across sessions, enabling personalized AI interactions by remembering user preferences, past conversations, and evolving facts.
*   **Ecosystem Role**: It sits between the LLM and the application logic, acting as a long-term memory store that can be queried during inference to augment the LLM's prompt with relevant historical context.
*   **Project Setup**:
    *   **Platform**: Sign up at [app.mem0.ai](https://app.mem0.ai), get an API key, and install the SDK (`pip install mem0ai` or `npm install mem0ai`).
    *   **Open Source (OSS)**: Self-host using Docker Compose. Requires configuring an LLM (OpenAI, Ollama, etc.), an Embedder, and a Vector Database (Qdrant is the default).

## 2. Core Primitives & APIs

### Mem0 Platform (Managed)
Uses `MemoryClient` for low-latency, managed memory.

*   **Python SDK**:
    ```python
    from mem0 import MemoryClient
    client = MemoryClient(api_key="your-api-key")

    # Add memories from messages
    client.add([{"role": "user", "content": "I prefer dark mode."}], user_id="alice")

    # Search memories
    results = client.search("What are the user's UI preferences?", user_id="alice")
    ```
*   **Node.js SDK**:
    ```javascript
    import MemoryClient from 'mem0ai';
    const client = new MemoryClient({ apiKey: 'your-api-key' });

    // Add memories
    await client.add([{ role: 'user', content: 'I prefer dark mode.' }], { userId: 'alice' });

    // Search memories
    const results = await client.search('What are the user\'s UI preferences?', { userId: 'alice' });
    ```

### Mem0 Open Source (Self-Hosted)
Uses `Memory` for full infrastructure control.

*   **Python SDK**:
    ```python
    from mem0 import Memory
    config = {
        "vector_store": {"provider": "qdrant", "config": {"host": "localhost", "port": 6333}},
        "llm": {"provider": "openai", "config": {"model": "gpt-4o"}}
    }
    memory = Memory.from_config(config)
    memory.add("I love hiking.", user_id="alice")
    ```

### Core Operations
*   `add(messages/text, filters/metadata)`: Extracts facts and stores them. [Docs](https://docs.mem0.ai/core-concepts/memory-operations/add)
*   `search(query, filters, top_k)`: Retrieves relevant memories. [Docs](https://docs.mem0.ai/core-concepts/memory-operations/search)
*   `get_all(filters)`: Lists all memories for a specific entity. [Docs](https://docs.mem0.ai/api-reference/memory/get-memories)
*   `update(memory_id, data)`: Manually corrects or updates a memory. [Docs](https://docs.mem0.ai/core-concepts/memory-operations/update)
*   `delete(memory_id)`: Removes a specific memory. [Docs](https://docs.mem0.ai/core-concepts/memory-operations/delete)

## 3. Real-World Use Cases & Templates

*   **AI Companion**: Personal assistants that remember user hobbies, family details, and preferences over months. [Template](https://docs.mem0.ai/cookbooks/companions/quickstart-demo)
*   **Customer Support**: Bots that maintain context across multiple support tickets and sessions. [Cookbook](https://docs.mem0.ai/cookbooks/operations/support-inbox)
*   **Adaptive Learning (AI Tutor)**: Educational tools that track a student's progress and adapt explanations based on past struggles. [Cookbook](https://docs.mem0.ai/cookbooks/companions/ai-tutor)
*   **Multi-Agent Collaboration**: Shared memory layers where different agents (e.g., Researcher and Writer) contribute to and read from a common knowledge base. [LlamaIndex Example](https://docs.mem0.ai/cookbooks/frameworks/llamaindex-multiagent)

## 4. Developer Friction Points

*   **Ollama `<think>` Blocks**: When using local models like DeepSeek or Qwen with Ollama, the internal fact extraction often chokes on `<think>` blocks, leading to empty memories.
*   **Next.js Webpack Issues**: Resolving the Node.js SDK in Next.js environments sometimes requires specific Webpack configuration for dependency resolution.
*   **Silent Extraction Failures**: If the LLM extraction step fails (e.g., due to token limits or prompt formatting), `add()` may return successfully but store no memories, making debugging difficult.

## 5. Evaluation Ideas

*   **Basic Memory CRUD**: Implement a CLI tool that can add, search, and delete user preferences.
*   **Multi-Tenant Isolation**: Configure a system where `user_A` cannot retrieve memories belonging to `user_B` even with similar queries.
*   **Hybrid Search Implementation**: Set up a search task that requires both semantic similarity and metadata filtering (e.g., "Find hiking tips from last summer").
*   **Webhook Integration**: Create a service that triggers a notification whenever a specific type of memory (e.g., "User is unhappy") is added.
*   **Voice Companion Setup**: Integrate Mem0 with a real-time voice API (like LiveKit) to maintain context in spoken conversations.

## 6. Sources

1. [Mem0 Official Documentation](https://docs.mem0.ai/) - Primary source for all SDK and Platform details.
2. [Mem0 GitHub Repository](https://github.com/mem0ai/mem0) - Source for OSS implementation and issue tracking.
3. [Mem0 llms.txt](https://docs.mem0.ai/llms.txt) - Structured overview for LLM-based research.
4. [Mem0 Cookbooks](https://docs.mem0.ai/cookbooks/overview) - Practical implementation examples and use cases.

# Integration

## Envs

These environment variables will be provided:

* MEM0_API_KEY: for Mem0 Platform usage
* OPENAI_API_KEY: for Mem0 Python/Node.js SDK usage with OpenAI