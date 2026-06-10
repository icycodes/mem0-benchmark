import { Memory } from "mem0ai/oss";
import { writeFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_DIR = __dirname;

// ---- helpers ----
function writeJson(filename, data) {
  const filePath = resolve(PROJECT_DIR, filename);
  writeFileSync(filePath, JSON.stringify(data, null, 2), "utf-8");
  console.log(`[artifact] wrote ${filePath}`);
}

// ---- main ----
async function main() {
  // 1. Read env
  const ZEALT_RUN_ID = process.env.ZEALT_RUN_ID;
  const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

  if (!OPENAI_API_KEY) {
    console.error("FATAL: OPENAI_API_KEY is not set in the environment");
    process.exit(1);
  }
  if (!ZEALT_RUN_ID) {
    console.error("FATAL: ZEALT_RUN_ID is not set in the environment");
    process.exit(1);
  }

  const runId = ZEALT_RUN_ID;
  const aliceId = `alice-${runId}`;
  const bobId = `bob-${runId}`;

  console.log(`RUN_ID: ${runId}`);

  // 2. Initialize Memory instance
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
    historyDbPath: resolve(PROJECT_DIR, "memory.db"),
  });

  // 3. Ingest Alice's conversation
  console.error("[ingest] alice...");
  await memory.add(
    [
      { role: "user", content: "I am vegetarian and I love sourdough bread." },
      { role: "assistant", content: "Noted. I'll save your vegetarian diet and sourdough preference." },
      { role: "user", content: "I also keep a strict no-nuts kitchen for my partner." },
    ],
    { userId: aliceId }
  );

  // 4. Ingest Bob's conversation
  console.error("[ingest] bob...");
  await memory.add(
    [
      { role: "user", content: "I have a shellfish allergy and I cook a lot of Thai green curry." },
      { role: "assistant", content: "Got it. Logged your shellfish allergy and Thai green curry preference." },
      { role: "user", content: "I always use jasmine rice as the side." },
    ],
    { userId: bobId }
  );

  // 5. User-scoped semantic search
  const query = "What are this cook's dietary preferences?";

  console.error("[search] alice...");
  const aliceSearchRaw = await memory.search(query, {
    filters: { user_id: aliceId },
  });
  const aliceResults = aliceSearchRaw.results ?? aliceSearchRaw;
  writeJson("alice_search.json", {
    userId: aliceId,
    results: aliceResults,
  });
  console.log(`ALICE_RESULTS: ${aliceResults.length}`);

  console.error("[search] bob...");
  const bobSearchRaw = await memory.search(query, {
    filters: { user_id: bobId },
  });
  const bobResults = bobSearchRaw.results ?? bobSearchRaw;
  writeJson("bob_search.json", {
    userId: bobId,
    results: bobResults,
  });
  console.log(`BOB_RESULTS: ${bobResults.length}`);

  // 6. Get all of Alice's memories, find one containing "vegetarian", update it
  console.error("[getAll] alice...");
  const aliceAllRaw = await memory.getAll({
    filters: { user_id: aliceId },
  });
  const aliceAll = aliceAllRaw.results ?? aliceAllRaw;

  const vegetarianMemory = aliceAll.find(
    (m) => m.memory && m.memory.toLowerCase().includes("vegetarian")
  );
  if (!vegetarianMemory) {
    console.error("FATAL: No memory containing 'vegetarian' found for Alice");
    process.exit(1);
  }

  const memoryId = vegetarianMemory.id;
  const newText = "Alice is vegan and avoids all animal products";

  console.error(`[update] memory ${memoryId}...`);
  await memory.update(memoryId, newText);
  console.log(`UPDATED_MEMORY_ID: ${memoryId}`);

  // 7. History audit
  console.error(`[history] memory ${memoryId}...`);
  const history = await memory.history(memoryId);
  console.log(`HISTORY_EVENTS: ${history.length}`);
  writeJson("alice_history.json", {
    memoryId,
    updatedText: newText,
    history,
  });

  console.error("[done]");
}

main().catch((err) => {
  console.error("FATAL:", err);
  process.exit(1);
});
