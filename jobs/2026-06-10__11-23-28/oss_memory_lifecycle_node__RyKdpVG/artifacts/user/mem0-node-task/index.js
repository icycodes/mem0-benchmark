import fs from "fs";
import path from "path";
import { Memory } from "mem0ai/oss";

// 1. Fail fast if OPENAI_API_KEY is missing
if (!process.env.OPENAI_API_KEY) {
  console.error("Error: OPENAI_API_KEY environment variable is not set.");
  process.exit(1);
}

const runId = process.env.ZEALT_RUN_ID || "test-run";
console.log(`Using RUN_ID: ${runId}`);

// 2. Monkey-patch Memory to support top-level camelCase userId in search and getAll
const originalSearch = Memory.prototype.search;
Memory.prototype.search = function(query, config) {
  if (config && config.userId) {
    config = {
      ...config,
      filters: {
        ...config.filters,
        user_id: config.userId
      }
    };
    delete config.userId;
  }
  return originalSearch.call(this, query, config);
};

const originalGetAll = Memory.prototype.getAll;
Memory.prototype.getAll = function(config) {
  if (config && config.userId) {
    config = {
      ...config,
      filters: {
        ...config.filters,
        user_id: config.userId
      }
    };
    delete config.userId;
  }
  return originalGetAll.call(this, config);
};

async function main() {
  // 3. Initialize Memory
  const memory = new Memory({
    embedder: {
      provider: "openai",
      config: {
        model: "text-embedding-3-small",
        apiKey: process.env.OPENAI_API_KEY
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
        model: "gpt-4o-mini",
        apiKey: process.env.OPENAI_API_KEY
      }
    },
    historyDbPath: "./memory.db"
  });

  const aliceUserId = `alice-${runId}`;
  const bobUserId = `bob-${runId}`;

  // 4. Ingest conversations
  console.log(`Ingesting conversation for Alice (${aliceUserId})...`);
  const aliceMessages = [
    { "role": "user", "content": "I am vegetarian and I love sourdough bread." },
    { "role": "assistant", "content": "Noted. I'll save your vegetarian diet and sourdough preference." },
    { "role": "user", "content": "I also keep a strict no-nuts kitchen for my partner." }
  ];
  await memory.add(aliceMessages, { userId: aliceUserId });

  console.log(`Ingesting conversation for Bob (${bobUserId})...`);
  const bobMessages = [
    { "role": "user", "content": "I have a shellfish allergy and I cook a lot of Thai green curry." },
    { "role": "assistant", "content": "Got it. Logged your shellfish allergy and Thai green curry preference." },
    { "role": "user", "content": "I always use jasmine rice as the side." }
  ];
  await memory.add(bobMessages, { userId: bobUserId });

  // 5. Search dietary preferences
  const searchQuery = "What are this cook's dietary preferences?";
  
  console.log(`Searching dietary preferences for Alice...`);
  const aliceSearchRaw = await memory.search(searchQuery, { userId: aliceUserId });
  const aliceResults = aliceSearchRaw.results || aliceSearchRaw;

  console.log(`Searching dietary preferences for Bob...`);
  const bobSearchRaw = await memory.search(searchQuery, { userId: bobUserId });
  const bobResults = bobSearchRaw.results || bobSearchRaw;

  // Persist search results
  const aliceSearchPath = "/home/user/mem0-node-task/alice_search.json";
  const bobSearchPath = "/home/user/mem0-node-task/bob_search.json";

  fs.writeFileSync(
    aliceSearchPath,
    JSON.stringify({ userId: aliceUserId, results: aliceResults }, null, 2)
  );
  fs.writeFileSync(
    bobSearchPath,
    JSON.stringify({ userId: bobUserId, results: bobResults }, null, 2)
  );

  console.log(`Saved search results to ${aliceSearchPath} and ${bobSearchPath}`);

  // 6. Update Alice's vegetarian memory to vegan
  console.log(`Fetching all memories for Alice to find vegetarian memory...`);
  const aliceAllMemoriesRaw = await memory.getAll({ userId: aliceUserId });
  const aliceAllMemories = aliceAllMemoriesRaw.results || aliceAllMemoriesRaw;

  const vegMemory = aliceAllMemories.find(m => 
    m.memory && m.memory.toLowerCase().includes("vegetarian")
  );

  if (!vegMemory) {
    throw new Error("Could not find a memory for Alice containing 'vegetarian'");
  }

  const memoryIdToUpdate = vegMemory.id;
  const updatedText = "Alice is vegan and avoids all animal products";
  console.log(`Updating memory ${memoryIdToUpdate} with: "${updatedText}"`);

  await memory.update(memoryIdToUpdate, updatedText);

  // Fetch history
  console.log(`Fetching history for memory ${memoryIdToUpdate}...`);
  const history = await memory.history(memoryIdToUpdate);

  // Persist history
  const aliceHistoryPath = "/home/user/mem0-node-task/alice_history.json";
  fs.writeFileSync(
    aliceHistoryPath,
    JSON.stringify({ memoryId: memoryIdToUpdate, updatedText, history }, null, 2)
  );
  console.log(`Saved history to ${aliceHistoryPath}`);

  // 7. Write stdout log file
  const logLines = [
    `RUN_ID: ${process.env.ZEALT_RUN_ID || ""}`,
    `ALICE_RESULTS: ${aliceResults.length}`,
    `BOB_RESULTS: ${bobResults.length}`,
    `UPDATED_MEMORY_ID: ${memoryIdToUpdate}`,
    `HISTORY_EVENTS: ${history.length}`
  ];

  const logContent = logLines.join("\n") + "\n";
  const logPath = "/home/user/mem0-node-task/output.log";
  fs.writeFileSync(logPath, logContent);

  console.log("\n--- STDOUT LOG OUTPUT ---");
  process.stdout.write(logContent);
  console.log("-------------------------\n");
}

main().catch(err => {
  console.error("Task execution failed:", err);
  process.exit(1);
});
