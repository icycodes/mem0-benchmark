# Mem0 Research Plan

This research plan provides a comprehensive blueprint for studying **Mem0**, a memory layer for LLM agents that delivers persistent, self-improving context across sessions. The plan covers the **Mem0 Platform** (managed), **Mem0 Python SDK** (`mem0ai`), and **Mem0 Node.js SDK** (`mem0ai`) — both their hosted (`MemoryClient`) and open-source (`Memory`) variants — and is suitable for building evaluation datasets that benchmark AI coding agents on real-world memory-management tasks.

---

## 1. Library Overview

### Description
Mem0 ("mem-zero") is a **drop-in memory infrastructure for AI agents and apps**. It automatically extracts facts from conversations, resolves conflicts with prior memories, and provides fast semantic retrieval — letting LLMs remember user preferences, history, and entities across sessions without re-sending the entire transcript on every call.

Key capabilities:
- Persistent, self-improving memory across sessions.
- Memory operations: `add`, `search`, `get`, `get_all`, `update`, `delete`, `delete_all`, `history`, `batch_*`.
- Memory types: working, factual, episodic, and semantic.
- Sub-50ms retrieval, reduced token usage vs. naive history replay.
- Benchmarked on LoCoMo, LongMemEval, and BEAM.

### Ecosystem Role
Mem0 sits **between the LLM and the application** as a memory layer. It is provider-agnostic on the managed Platform (providers are server-side) and fully pluggable on OSS (LLM, embedder, vector store, graph store, reranker). It integrates with all major agent frameworks (LangChain, LangGraph, LlamaIndex, CrewAI, AutoGen, OpenAI Agents SDK, Vercel AI SDK, Mastra, Google ADK), AI coding tools (Claude Code, Cursor, Codex) via an **MCP server** at `https://mcp.mem0.ai`, and voice stacks (LiveKit, Pipecat, ElevenLabs).

There are **two products with one mental model**:
- **Mem0 Platform** — managed, recommended 4-line integration (`MemoryClient`).
- **Mem0 Open Source** — self-hosted (`Memory`), for users with custom infra or air-gapped requirements.

### Project Setup

#### Mem0 Platform (Managed)
1. Sign up at <https://app.mem0.ai> and get an API key from Dashboard → Settings → API Keys.
2. Install SDK:
   - Python: `pip install mem0ai` (Python 3.10+).
   - Node: `npm install mem0ai` (Node 18+; published as TypeScript 3.x).
3. Export the key: `export MEM0_API_KEY="..."`.
4. Optional: install the CLI — `pip install mem0-cli` or `npm install -g @mem0/cli` — and run `mem0 init --agent --agent-caller <agent>` to mint a key from the terminal in seconds (no email/OTP required; ownership can be claimed later with `mem0 init --email <email>`).

Minimal Platform program (Python):
```python
from mem0 import MemoryClient
client = MemoryClient(api_key="...")  # or reads MEM0_API_KEY
client.add(
    [{"role": "user", "content": "I love hiking on weekends"}],
    user_id="alice",
)
print(client.search("What does Alice like?", user_id="alice"))
```

#### Mem0 OSS (Self-Hosted)
1. Install: `pip install mem0ai` or `npm install mem0ai` (uses `mem0ai/oss` import path for Node).
2. Provide an LLM/embedder key (default OpenAI): `export OPENAI_API_KEY=...`.
3. Defaults: OpenAI `gpt-5-mini` for extraction + `text-embedding-3-small` embeddings, Qdrant at `/tmp/qdrant`, SQLite history at `~/.mem0/history.db`.
4. Optional bundled REST server + dashboard via Docker Compose: see *Self-Hosted Setup* (`open-source/setup`).

---

## 2. Core Primitives & APIs

### 2.1 Mem0 Platform — `MemoryClient` (Python) / `MemoryClient` (TS)

Reference: <https://docs.mem0.ai/platform/quickstart>, <https://docs.mem0.ai/api-reference>

**Python:**
```python
from mem0 import MemoryClient
client = MemoryClient(api_key="...")  # also: AsyncMemoryClient

# Create
client.add(
    [{"role": "user", "content": "I'm vegetarian and allergic to nuts."}],
    user_id="user123",
    metadata={"category": "diet"},
)

# Read
client.search("What are my dietary restrictions?", filters={"user_id": "user123"}, version="v2")
client.get_all(user_id="user123")
client.get(memory_id="<id>")

# Update / Delete
client.update(memory_id="<id>", data="Vegetarian, severe nut allergy")
client.delete(memory_id="<id>")
client.delete_all(user_id="user123")

# History & batch
client.history(memory_id="<id>")
client.batch_update([...])
client.batch_delete([...])
```

**TypeScript / JavaScript:**
```ts
import MemoryClient from "mem0ai";
const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });

await client.add(
  [{ role: "user", content: "I love hiking on weekends" }],
  { user_id: "alice" }
);
await client.search("What does Alice like?", { user_id: "alice" });
await client.getAll({ user_id: "alice" });
await client.update("<id>", { text: "Alice loves mountain hiking" });
await client.delete("<id>");
```

### 2.2 Mem0 Platform REST API

Endpoints (require `Authorization: Token <MEM0_API_KEY>`). OpenAPI spec at <https://docs.mem0.ai/openapi.json>.

- `POST /v1/memories/` — Add memories ([docs](https://docs.mem0.ai/api-reference/memory/add-memories))
- `GET /v1/memories/` — Get all memories
- `GET /v1/memories/{id}/` — Get one
- `POST /v2/memories/search/` — Semantic search with v2 filters
- `PUT /v1/memories/{id}/` — Update
- `DELETE /v1/memories/{id}/` — Delete
- `GET /v1/memories/{id}/history/` — History
- `POST /v1/memories/feedback/` — Feedback
- `POST /v1/exports/` and `GET /v1/exports/{id}/` — Memory export
- Org/Project/Webhook/Events endpoints under `/api-reference/`.

### 2.3 Mem0 OSS — `Memory` (Python) / `Memory` (Node `mem0ai/oss`)

Reference: <https://docs.mem0.ai/open-source/python-quickstart>, <https://docs.mem0.ai/open-source/node-quickstart>

**Python (defaults to OpenAI; requires `OPENAI_API_KEY`):**
```python
from mem0 import Memory, AsyncMemory
m = Memory()  # or Memory.from_config({...})

m.add("I love hiking on weekends", user_id="alice")
m.search("What does Alice like?", user_id="alice")
m.get_all(user_id="alice")
m.update(memory_id="<id>", data="Alice prefers alpine hiking")
m.history(memory_id="<id>")
m.delete(memory_id="<id>")
m.reset()
```

Custom configuration:
```python
config = {
    "llm": {"provider": "openai", "config": {"model": "gpt-4o-mini", "api_key": "..."}},
    "embedder": {"provider": "openai", "config": {"model": "text-embedding-3-small"}},
    "vector_store": {"provider": "qdrant", "config": {"host": "localhost", "port": 6333}},
    "graph_store": {"provider": "neo4j", "config": {...}},  # optional graph memory
}
m = Memory.from_config(config)
```

**Node.js (`mem0ai/oss`):**
```ts
import { Memory } from "mem0ai/oss";

const memory = new Memory({
  embedder: { provider: "openai", config: { apiKey: process.env.OPENAI_API_KEY!, model: "text-embedding-3-small" } },
  vectorStore: { provider: "memory", config: { collectionName: "memories", dimension: 1536 } },
  llm: { provider: "openai", config: { apiKey: process.env.OPENAI_API_KEY!, model: "gpt-4-turbo-preview" } },
  historyDbPath: "memory.db",
});

await memory.add("I love hiking on weekends", { userId: "alice" });
await memory.search("What does Alice like?", { userId: "alice" });
await memory.getAll({ userId: "alice" });
await memory.update("<id>", "Alice loves mountain hiking");
await memory.history("<id>");
await memory.delete("<id>");
await memory.reset();
```

### 2.4 Platform-Only Advanced Features
- **Entity-Scoped Memory** — `user_id`, `agent_id`, `app_id`, `run_id` partitioning. ([docs](https://docs.mem0.ai/platform/features/entity-scoped-memory))
- **V2 Memory Filters** — Compound AND/OR filters on metadata, entities, timestamps. ([docs](https://docs.mem0.ai/platform/features/v2-memory-filters))
- **Async Client** — `AsyncMemoryClient` for non-blocking IO. ([docs](https://docs.mem0.ai/platform/features/async-client))
- **Advanced Retrieval** — Keyword + semantic + reranking. ([docs](https://docs.mem0.ai/platform/features/advanced-retrieval))
- **Criteria-Based Retrieval** — Pull memories by custom criteria, not just similarity. ([docs](https://docs.mem0.ai/platform/features/criteria-retrieval))
- **Temporal Reasoning** — Time-aware ordering ("last week", "upcoming"). ([docs](https://docs.mem0.ai/platform/features/temporal-reasoning))
- **Contextual Add** — `add()` considers the surrounding conversation. ([docs](https://docs.mem0.ai/platform/features/contextual-add))
- **Memory Decay** — Boost recently-reinforced memories, dampen stale ones (opt-in). ([docs](https://docs.mem0.ai/platform/features/memory-decay))
- **Custom Categories / Custom Instructions** — Tailor extraction to your domain. ([docs](https://docs.mem0.ai/platform/features/custom-categories))
- **Multimodal Support** — Store images and PDFs as memory input. ([docs](https://docs.mem0.ai/platform/features/multimodal-support))
- **Group Chat Support** — Multi-participant conversations. ([docs](https://docs.mem0.ai/platform/features/group-chat))
- **Webhooks**, **Direct Import**, **Memory Export**, **Feedback Mechanism**. ([docs](https://docs.mem0.ai/platform/features/platform-overview))

### 2.5 OSS-Only Configuration Surface
- **LLM providers**: OpenAI, Anthropic, Azure OpenAI, AWS Bedrock, Google Gemini, Groq, DeepSeek, Mistral, Ollama, LM Studio, LiteLLM, vLLM, xAI, Together. ([docs](https://docs.mem0.ai/components/llms/overview))
- **Embedders**: OpenAI, Azure, Bedrock, Gemini, Vertex AI, Hugging Face, Ollama, LM Studio, Together. ([docs](https://docs.mem0.ai/components/embedders/overview))
- **Vector DBs**: Qdrant (default), Chroma, PGVector, Milvus, Pinecone, MongoDB Atlas, Azure AI Search, Redis, Elasticsearch, OpenSearch, Supabase, Upstash, Weaviate, FAISS, Vectorize (Cloudflare), Vertex AI, Databricks, Turbopuffer, Cassandra, S3 Vectors. ([docs](https://docs.mem0.ai/components/vectordbs/overview))
- **Rerankers**: Cohere, Sentence Transformers, Hugging Face, LLM-as-reranker, Zero Entropy. ([docs](https://docs.mem0.ai/components/rerankers/overview))

### 2.6 CLI & MCP
- CLIs: `pip install mem0-cli` or `npm install -g @mem0/cli`. Commands: `mem0 init`, `mem0 identify`, `mem0 --version`, plus memory CRUD. ([docs](https://docs.mem0.ai/platform/cli))
- Hosted MCP server: `https://mcp.mem0.ai` exposes 9 tools — `add_memory`, `search_memories`, `get_memories`, `get_memory`, `update_memory`, `delete_memory`, `delete_all_memories`, `delete_entities`, `list_entities`. ([docs](https://docs.mem0.ai/platform/mem0-mcp))

---

## 3. Real-World Use Cases & Templates

### Cookbooks (official, runnable examples)
- **AI Companion** — Full-stack companion with persistent memory. <https://docs.mem0.ai/cookbooks/essentials/building-ai-companion>
- **Node.js Companion** — TS/JS companion app. <https://docs.mem0.ai/cookbooks/companions/nodejs-companion>
- **AI Tutor**, **Travel Assistant**, **YouTube Research Assistant**, **Voice Companion (OpenAI Realtime)**, **Local Companion (Ollama)**. <https://docs.mem0.ai/cookbooks/overview>
- **Support Inbox**, **Email Automation**, **Content Writer**, **Deep Research Agent**, **Team Task Agent**.
- **OpenAI Tool Calls**, **OpenAI Agents SDK Tool**, **Mastra Agent**, **Healthcare with Google ADK**, **AWS Bedrock**, **Tavily Search + memory**.
- **LlamaIndex React UI**, **LlamaIndex Multi-agent**, **Multimodal Retrieval**, **Eliza OS Character**, **Gemini 3 over Mem0 MCP**.

### Integration patterns
- **LangChain / LangGraph** — Stateful multi-actor flows with shared memory. <https://docs.mem0.ai/integrations/langchain>
- **CrewAI / AutoGen / OpenAI Agents SDK / Agno / Camel / Mastra** — Memory injected as tool or context.
- **Vercel AI SDK** — Drop-in via `@mem0/vercel-ai-provider` and `createMem0(...)`. <https://docs.mem0.ai/integrations/vercel-ai-sdk>
- **Voice agents** — LiveKit, Pipecat, ElevenLabs ingesting transcripts into Mem0.
- **AI Coding Tools** — Claude Code / Cursor / Codex via MCP + skill bundles (`skills/mem0`, `skills/mem0-cli`, `skills/mem0-vercel-ai-sdk`).

### Source & infra
- Monorepo: <https://github.com/mem0ai/mem0> (Python SDK, Node SDK, CLI, plugin, skills).
- Bundled REST server + dashboard (`openmemory/api`) — FastAPI service for self-hosted deployments.

---

## 4. Developer Friction Points

1. **`v1` vs `v2` search / `output_format` migration**
   - Search responses differ between Platform v1 (`{ memory, ... }`) and v2 (`{ results: [...] }`), and `filters` is required for v2 compound queries. Many tutorials still show v1. See <https://docs.mem0.ai/migration/platform-v2-to-v3> and <https://docs.mem0.ai/migration/api-changes>. Failing to pass `version="v2"` or `output_format="v1.1"` results in surprising response shapes and broken downstream parsing.

2. **OSS provider configuration / vector store mismatch**
   - `Memory()` defaults to Qdrant at `/tmp/qdrant` and OpenAI; switching to PGVector, Pinecone, or Ollama requires the right `from_config()` schema. Common errors: dimension mismatch between embedder and vector store (e.g., `text-embedding-3-small`=1536 vs. collection created at 768), missing `collection_name`, or forgetting `OPENAI_API_KEY` when using OpenAI defaults. See <https://docs.mem0.ai/open-source/configuration> and <https://docs.mem0.ai/components/vectordbs/config>.

3. **Entity scoping and multi-tenant leakage**
   - Forgetting to pass `user_id` / `agent_id` / `app_id` / `run_id` causes memories to land in the project's "global" bucket and bleed across tenants. The entity-partitioning playbook addresses this: <https://docs.mem0.ai/cookbooks/essentials/entity-partitioning-playbook>. Related: deleting a user with `delete_user` purges all child memories — easy footgun if used without confirmation.

4. **Node SDK split: managed vs OSS imports**
   - `import MemoryClient from "mem0ai"` (Platform, default export) and `import { Memory } from "mem0ai/oss"` (self-hosted) are both shipped by the same npm package. Mixing them or using camelCase vs snake_case option keys (`userId` vs `user_id`) is a frequent source of runtime errors.

5. **Async vs sync clients**
   - Both Platform (`AsyncMemoryClient`) and OSS (`AsyncMemory`) ship async variants, but mixing sync and async in the same code path (e.g., calling `client.add(...)` without `await`) silently drops writes. See <https://docs.mem0.ai/platform/features/async-client> and <https://docs.mem0.ai/open-source/features/async-memory>.

---

## 5. Evaluation Ideas

1. **(Easy)** Wire `MemoryClient` into a CLI chatbot that persists user preferences across runs using `MEM0_API_KEY`.
2. **(Easy)** Implement a Node.js script that ingests a multi-turn conversation and prints search results scoped to a `user_id`.
3. **(Medium)** Build a self-hosted `Memory()` setup with a non-default vector store (e.g., Chroma or PGVector) plus OpenAI embeddings.
4. **(Medium)** Add entity-partitioned memory to a multi-tenant assistant so memories are isolated per `user_id` + `agent_id`.
5. **(Medium)** Use v2 compound filters and metadata to retrieve only memories tagged with a custom category within a time window.
6. **(Hard)** Migrate a v1 Platform integration (output_format) to v3, updating both `search()` consumers and any cached schemas.
7. **(Hard)** Integrate Mem0 as a tool inside an OpenAI Agents SDK / LangGraph workflow that decides when to call `add` vs `search`.
8. **(Hard)** Implement an MCP-driven memory workflow against `https://mcp.mem0.ai`, including `add_memory`, `search_memories`, and `delete_entities` tool calls from a custom agent.

---

## 6. Sources

1. <https://mem0.ai/> — Marketing site, positioning, headline metrics, target verticals.
2. <https://docs.mem0.ai/llms.txt> — Master index of all docs with `[Platform]`/`[OSS]`/`[Both]` tags; primary source for this plan.
3. <https://docs.mem0.ai/platform/quickstart> — Platform 4-step quickstart (install, key, add, search).
4. <https://docs.mem0.ai/open-source/python-quickstart> — OSS Python SDK quickstart with `Memory()` defaults.
5. <https://docs.mem0.ai/open-source/node-quickstart> — OSS Node SDK quickstart, full config schema (vector/LLM/embedder/history).
6. <https://docs.mem0.ai/platform/overview> — Platform overview and value proposition.
7. <https://docs.mem0.ai/api-reference> — REST API surface and auth model.
8. <https://docs.mem0.ai/openapi.json> — Machine-readable OpenAPI spec.
9. <https://docs.mem0.ai/platform/features/platform-overview> — Catalog of managed-only features.
10. <https://docs.mem0.ai/open-source/configuration> — OSS `Memory.from_config()` schema (LLM, embedder, vector store, graph store).
11. <https://docs.mem0.ai/platform/mem0-mcp> — Hosted MCP server and its 9 tools.
12. <https://docs.mem0.ai/migration/platform-v2-to-v3> + <https://docs.mem0.ai/migration/api-changes> — Breaking-change reference for evaluation realism.
13. <https://docs.mem0.ai/cookbooks/overview> — Full list of runnable cookbook examples.
14. <https://github.com/mem0ai/mem0> — Source repo, plugin, skills (`skills/mem0`, `skills/mem0-cli`, `skills/mem0-vercel-ai-sdk`).

---

# Integration

## Envs

These environment variables will be provided:

* MEM0_API_KEY: for Mem0 Platform usage
* OPENAI_API_KEY: for Mem0 Python/Node.js SDK usage with OpenAI
