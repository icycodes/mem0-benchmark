import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { Memory } from "mem0ai/oss";

const runId = process.env.ZEALT_RUN_ID;
const apiKey = process.env.OPENAI_API_KEY;

if (!runId) {
  throw new Error("ZEALT_RUN_ID environment variable is required");
}

if (!apiKey) {
  throw new Error("OPENAI_API_KEY environment variable is required");
}

const projectDir = "/home/user/mem0-node-task";
const historyDbPath = resolve(projectDir, "memory.db");

const memory = new Memory({
  embedder: {
    provider: "openai",
    model: "text-embedding-3-small",
    apiKey,
  },
  vectorStore: {
    provider: "memory",
    collectionName: "memories",
    dimension: 1536,
  },
  llm: {
    provider: "openai",
    model: "gpt-4o-mini",
    apiKey,
  },
  historyDbPath,
});

const aliceUserId = `alice-${runId}`;
const bobUserId = `bob-${runId}`;

const aliceMessages = [
  {
    role: "user",
    content: "I am vegetarian and I love sourdough bread.",
  },
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
    content: "I have a shellfish allergy and I cook a lot of Thai green curry.",
  },
  {
    role: "assistant",
    content: "Got it. Logged your shellfish allergy and Thai green curry preference.",
  },
  {
    role: "user",
    content: "I always use jasmine rice as the side.",
  },
];

const normalizeResults = (response) => {
  if (!response) {
    return [];
  }
  if (Array.isArray(response)) {
    return response;
  }
  if (Array.isArray(response.results)) {
    return response.results;
  }
  return [];
};

const pickVegetarianMemory = (memories) => {
  const match = memories.find((item) =>
    String(item.memory || "").toLowerCase().includes("vegetarian")
  );
  if (!match) {
    throw new Error("No memory containing 'vegetarian' found for Alice");
  }
  return match;
};

const run = async () => {
  await memory.add(aliceMessages, { userId: aliceUserId });
  await memory.add(bobMessages, { userId: bobUserId });

  const aliceSearchResponse = await memory.search(
    "What are this cook's dietary preferences?",
    { filters: { user_id: aliceUserId } }
  );
  const bobSearchResponse = await memory.search(
    "What are this cook's dietary preferences?",
    { filters: { user_id: bobUserId } }
  );

  const aliceResults = normalizeResults(aliceSearchResponse);
  const bobResults = normalizeResults(bobSearchResponse);

  await writeFile(
    resolve(projectDir, "alice_search.json"),
    JSON.stringify({ userId: aliceUserId, results: aliceResults }, null, 2)
  );
  await writeFile(
    resolve(projectDir, "bob_search.json"),
    JSON.stringify({ userId: bobUserId, results: bobResults }, null, 2)
  );

  const aliceMemoriesResponse = await memory.getAll({
    filters: { user_id: aliceUserId },
  });
  const aliceMemories = normalizeResults(aliceMemoriesResponse);
  const targetMemory = pickVegetarianMemory(aliceMemories);

  const updatedText = "Alice is vegan and avoids all animal products";
  await memory.update(targetMemory.id, updatedText);

  const history = await memory.history(targetMemory.id);

  await writeFile(
    resolve(projectDir, "alice_history.json"),
    JSON.stringify(
      {
        memoryId: targetMemory.id,
        updatedText,
        history,
      },
      null,
      2
    )
  );

  const logLines = [
    `RUN_ID: ${runId}`,
    `ALICE_RESULTS: ${aliceResults.length}`,
    `BOB_RESULTS: ${bobResults.length}`,
    `UPDATED_MEMORY_ID: ${targetMemory.id}`,
    `HISTORY_EVENTS: ${Array.isArray(history) ? history.length : 0}`,
  ];

  const logContent = `${logLines.join("\n")}\n`;

  await writeFile(resolve(projectDir, "output.log"), logContent);

  process.stdout.write(logContent);
};

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
