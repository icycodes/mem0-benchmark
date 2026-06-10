import { Memory } from "mem0ai/oss";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const projectDir = path.dirname(__filename);
const outputLogPath = path.join(projectDir, "output.log");
const updatedText = "Alice is vegan and avoids all animal products";

await fs.writeFile(outputLogPath, "", "utf8");

function logLine(line) {
  console.log(line);
  return fs.appendFile(outputLogPath, `${line}\n`, "utf8");
}

function requireEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function normalizeList(response) {
  if (Array.isArray(response)) {
    return response;
  }
  if (response && Array.isArray(response.results)) {
    return response.results;
  }
  if (response && Array.isArray(response.memories)) {
    return response.memories;
  }
  return [];
}

function normalizeMemoryRecord(record) {
  const id = record?.id ?? record?.memory_id ?? record?.memoryId;
  const memory = record?.memory ?? record?.text ?? record?.content;
  return {
    ...record,
    id,
    memory
  };
}

function containsMemory(records, keyword) {
  const lower = keyword.toLowerCase();
  return records.some((record) => String(record?.memory ?? "").toLowerCase().includes(lower));
}

const apiKey = requireEnv("OPENAI_API_KEY");
const runId = process.env.ZEALT_RUN_ID || "local";
const aliceUserId = `alice-${runId}`;
const bobUserId = `bob-${runId}`;

const memory = new Memory({
  embedder: {
    provider: "openai",
    config: {
      apiKey,
      model: "text-embedding-3-small"
    }
  },
  vectorStore: {
    provider: "memory",
    config: {
      collectionName: "memories",
      dimension: 1536
    }
  },
  llm: {
    provider: "openai",
    config: {
      apiKey,
      model: "gpt-4o-mini"
    }
  },
  historyDbPath: path.join(projectDir, "memory.db")
});

const aliceMessages = [
  { "role": "user", "content": "I am vegetarian and I love sourdough bread." },
  { "role": "assistant", "content": "Noted. I'll save your vegetarian diet and sourdough preference." },
  { "role": "user", "content": "I also keep a strict no-nuts kitchen for my partner." }
];

const bobMessages = [
  { "role": "user", "content": "I have a shellfish allergy and I cook a lot of Thai green curry." },
  { "role": "assistant", "content": "Got it. Logged your shellfish allergy and Thai green curry preference." },
  { "role": "user", "content": "I always use jasmine rice as the side." }
];

await logLine(`RUN_ID: ${runId}`);

await memory.add(aliceMessages, { userId: aliceUserId });
await memory.add(bobMessages, { userId: bobUserId });

const searchQuery = "What are this cook's dietary preferences?";
const aliceSearchRaw = await memory.search(searchQuery, { userId: aliceUserId });
const bobSearchRaw = await memory.search(searchQuery, { userId: bobUserId });
const aliceResults = normalizeList(aliceSearchRaw).map(normalizeMemoryRecord);
const bobResults = normalizeList(bobSearchRaw).map(normalizeMemoryRecord);

await fs.writeFile(
  path.join(projectDir, "alice_search.json"),
  `${JSON.stringify({ userId: aliceUserId, results: aliceResults }, null, 2)}\n`,
  "utf8"
);
await fs.writeFile(
  path.join(projectDir, "bob_search.json"),
  `${JSON.stringify({ userId: bobUserId, results: bobResults }, null, 2)}\n`,
  "utf8"
);

const allAliceRaw = await memory.getAll({ userId: aliceUserId });
const allAliceMemories = normalizeList(allAliceRaw).map(normalizeMemoryRecord);
const memoryToUpdate = allAliceMemories.find((record) =>
  String(record?.memory ?? "").toLowerCase().includes("vegetarian")
);

if (!memoryToUpdate?.id) {
  throw new Error("Could not find an Alice memory containing 'vegetarian' to update");
}

await memory.update(memoryToUpdate.id, updatedText);
const historyRaw = await memory.history(memoryToUpdate.id);
const history = normalizeList(historyRaw);

await fs.writeFile(
  path.join(projectDir, "alice_history.json"),
  `${JSON.stringify({ memoryId: memoryToUpdate.id, updatedText, history }, null, 2)}\n`,
  "utf8"
);

if (aliceResults.length < 1) {
  throw new Error("Alice search returned no results");
}
if (bobResults.length < 1) {
  throw new Error("Bob search returned no results");
}
if (!containsMemory(aliceResults, "vegetarian")) {
  throw new Error("Alice search results do not contain vegetarian");
}
if (!containsMemory(bobResults, "shellfish")) {
  throw new Error("Bob search results do not contain shellfish");
}
if (containsMemory(aliceResults, "shellfish")) {
  throw new Error("Alice search results leaked Bob's shellfish memory");
}
if (containsMemory(bobResults, "vegetarian")) {
  throw new Error("Bob search results leaked Alice's vegetarian memory");
}
if (history.length < 2) {
  throw new Error(`Expected at least 2 history events, received ${history.length}`);
}

await logLine(`ALICE_RESULTS: ${aliceResults.length}`);
await logLine(`BOB_RESULTS: ${bobResults.length}`);
await logLine(`UPDATED_MEMORY_ID: ${memoryToUpdate.id}`);
await logLine(`HISTORY_EVENTS: ${history.length}`);
