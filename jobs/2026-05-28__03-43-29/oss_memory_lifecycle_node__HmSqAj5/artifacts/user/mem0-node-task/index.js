import { Memory } from "mem0ai/oss";
import { writeFileSync } from "fs";
import { fileURLToPath } from "url";
import path from "path";

// ── Fail-fast checks ────────────────────────────────────────────────────────

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
if (!OPENAI_API_KEY) {
  console.error("ERROR: OPENAI_API_KEY environment variable is not set.");
  process.exit(1);
}

const ZEALT_RUN_ID = process.env.ZEALT_RUN_ID;
if (!ZEALT_RUN_ID) {
  console.error("ERROR: ZEALT_RUN_ID environment variable is not set.");
  process.exit(1);
}

// ── Derived identifiers ─────────────────────────────────────────────────────

const runId = ZEALT_RUN_ID;
const aliceId = `alice-${runId}`;
const bobId = `bob-${runId}`;

// ── Project directory ───────────────────────────────────────────────────────

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Collect log lines to write to output.log at the end
const logLines = [];

function log(line) {
  console.log(line);
  logLines.push(line);
}

// ── Initialize Memory ───────────────────────────────────────────────────────

log(`RUN_ID: ${ZEALT_RUN_ID}`);

const memory = new Memory({
  embedder: {
    provider: "openai",
    config: {
      apiKey: OPENAI_API_KEY,
      model: "text-embedding-3-small",
    },
  },
  vectorStore: {
    provider: "memory",
    config: {
      collectionName: "memories",
      dimension: 1536,
    },
  },
  llm: {
    provider: "openai",
    config: {
      apiKey: OPENAI_API_KEY,
      model: "gpt-4o-mini",
    },
  },
  historyDbPath: path.join(__dirname, "memory.db"),
});

// ── Conversations to ingest ─────────────────────────────────────────────────

const aliceMessages = [
  { role: "user", content: "I am vegetarian and I love sourdough bread." },
  {
    role: "assistant",
    content: "Noted. I'll save your vegetarian diet and sourdough preference.",
  },
  {
    role: "user",
    content: "I also keep a strict no-nuts kitchen for my partner.",
  },
];

const bobMessages = [
  {
    role: "user",
    content:
      "I have a shellfish allergy and I cook a lot of Thai green curry.",
  },
  {
    role: "assistant",
    content:
      "Got it. Logged your shellfish allergy and Thai green curry preference.",
  },
  { role: "user", content: "I always use jasmine rice as the side." },
];

// ── Step 1: Ingest conversations ────────────────────────────────────────────

log("Ingesting Alice's conversation...");
await memory.add(aliceMessages, { userId: aliceId });

log("Ingesting Bob's conversation...");
await memory.add(bobMessages, { userId: bobId });

// ── Step 2: Semantic search, scoped per user ────────────────────────────────

const searchQuery = "What are this cook's dietary preferences?";

log("Searching Alice's memories...");
const aliceRaw = await memory.search(searchQuery, { filters: { user_id: aliceId } });
const aliceResults = aliceRaw && aliceRaw.results ? aliceRaw.results : aliceRaw;

log("Searching Bob's memories...");
const bobRaw = await memory.search(searchQuery, { filters: { user_id: bobId } });
const bobResults = bobRaw && bobRaw.results ? bobRaw.results : bobRaw;

log(`ALICE_RESULTS: ${aliceResults.length}`);
log(`BOB_RESULTS: ${bobResults.length}`);

// Persist search artifacts
writeFileSync(
  path.join(__dirname, "alice_search.json"),
  JSON.stringify({ userId: aliceId, results: aliceResults }, null, 2)
);
writeFileSync(
  path.join(__dirname, "bob_search.json"),
  JSON.stringify({ userId: bobId, results: bobResults }, null, 2)
);

// ── Step 3: Locate the vegetarian memory for Alice ──────────────────────────

const allAliceMemories = await memory.getAll({ filters: { user_id: aliceId } });
const allAliceList =
  allAliceMemories && allAliceMemories.results
    ? allAliceMemories.results
    : allAliceMemories;

const vegetarianMemory = allAliceList.find(
  (m) => m.memory && m.memory.toLowerCase().includes("vegetarian")
);

if (!vegetarianMemory) {
  console.error(
    "ERROR: Could not find a memory containing 'vegetarian' for Alice."
  );
  console.error("All Alice memories:", JSON.stringify(allAliceList, null, 2));
  process.exit(1);
}

const targetMemoryId = vegetarianMemory.id;
log(`Found vegetarian memory: id=${targetMemoryId}, text="${vegetarianMemory.memory}"`);

// ── Step 4: Update the memory ───────────────────────────────────────────────

const updatedText = "Alice is vegan and avoids all animal products";
await memory.update(targetMemoryId, updatedText);

// ── Step 5: Fetch history ───────────────────────────────────────────────────

const historyRaw = await memory.history(targetMemoryId);
const historyList = Array.isArray(historyRaw) ? historyRaw : [historyRaw];

log(`UPDATED_MEMORY_ID: ${targetMemoryId}`);
log(`HISTORY_EVENTS: ${historyList.length}`);

// Persist history artifact
writeFileSync(
  path.join(__dirname, "alice_history.json"),
  JSON.stringify(
    {
      memoryId: targetMemoryId,
      updatedText,
      history: historyList,
    },
    null,
    2
  )
);

// ── Write output.log ────────────────────────────────────────────────────────

writeFileSync(path.join(__dirname, "output.log"), logLines.join("\n") + "\n");

log("Done. All artifacts written.");
