import fs from "node:fs/promises";
import path from "node:path";
import MemoryClient from "mem0ai";

const PROJECT_DIR = "/home/user/mem0-metadata-task";
const UPDATED_FINANCE_TEXT = "Files quarterly tax estimates in March and September with the accountant";
const SEARCH_QUERY = "Which of my notes are urgent and high priority?";

function requireEnv(name) {
  const value = process.env[name];
  if (!value || !value.trim()) {
    throw new Error(`Missing required environment variable ${name}. Set ${name} before running this script.`);
  }
  return value.trim();
}

const MEM0_API_KEY = requireEnv("MEM0_API_KEY");
const ZEALT_RUN_ID = requireEnv("ZEALT_RUN_ID");
const userId = `planner-${ZEALT_RUN_ID}`;

const client = new MemoryClient({ apiKey: MEM0_API_KEY });

const notes = [
  {
    messages: [{ role: "user", content: "I file my quarterly tax estimates with my accountant every March." }],
    metadata: { category: "finance", priority: "high" },
  },
  {
    messages: [{ role: "user", content: "I max out my 401(k) contributions early each year." }],
    metadata: { category: "finance", priority: "low" },
  },
  {
    messages: [{ role: "user", content: "I prefer aisle seats on long-haul flights and direct routes to Tokyo." }],
    metadata: { category: "travel", priority: "high" },
  },
  {
    messages: [{ role: "user", content: "I run intervals on the treadmill three times a week." }],
    metadata: { category: "health", priority: "high" },
  },
  {
    messages: [{ role: "user", content: "I take a daily multivitamin in the morning." }],
    metadata: { category: "health", priority: "low" },
  },
];

function normalizeResults(response) {
  if (Array.isArray(response)) {
    return response;
  }
  if (response && Array.isArray(response.results)) {
    return response.results;
  }
  return [];
}

function normalizeHistory(response) {
  if (Array.isArray(response)) {
    return response;
  }
  if (response && Array.isArray(response.results)) {
    return response.results;
  }
  if (response && Array.isArray(response.history)) {
    return response.history;
  }
  return [];
}

function memoryText(memory) {
  const parts = [];
  const push = (value) => {
    if (typeof value === "string") {
      parts.push(value);
    }
  };

  push(memory?.memory);
  push(memory?.text);
  push(memory?.content);
  push(memory?.data?.memory);
  push(memory?.data?.text);
  push(memory?.data?.content);
  push(memory?.newMemory);
  push(memory?.oldMemory);

  if (Array.isArray(memory?.messages)) {
    for (const message of memory.messages) {
      push(message?.content);
    }
  }

  return parts.join("\n");
}

function findByText(memories, substring) {
  const needle = substring.toLowerCase();
  return memories.find((memory) => memoryText(memory).toLowerCase().includes(needle));
}

function hasUpdateEvent(history) {
  return history.some((entry) => {
    const event = String(entry?.event ?? entry?.type ?? entry?.action ?? "");
    return event.toUpperCase() === "UPDATE";
  });
}

function financeFilter() {
  return {
    AND: [
      { user_id: userId },
      { metadata: { category: "finance" } },
    ],
  };
}

function highPriorityFilter() {
  return {
    AND: [
      { user_id: userId },
      { metadata: { priority: "high" } },
    ],
  };
}

function healthFilter() {
  return {
    AND: [
      { user_id: userId },
      { metadata: { category: "health" } },
    ],
  };
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function retryUntil(description, fn, predicate, { attempts = 24, delayMs = 5000 } = {}) {
  let lastValue;
  let lastError;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      lastValue = await fn();
      if (predicate(lastValue)) {
        return lastValue;
      }
    } catch (error) {
      lastError = error;
    }

    if (attempt < attempts) {
      await sleep(delayMs);
    }
  }

  if (lastError) {
    throw new Error(`${description} failed after ${attempts} attempts: ${lastError.message}`, { cause: lastError });
  }
  throw new Error(`${description} did not satisfy the expected condition after ${attempts} attempts. Last value: ${JSON.stringify(lastValue)}`);
}

async function writeJson(filename, data) {
  await fs.writeFile(path.join(PROJECT_DIR, filename), `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

async function main() {
  await fs.mkdir(PROJECT_DIR, { recursive: true });

  for (const note of notes) {
    await client.add(note.messages, { userId, metadata: note.metadata });
  }

  const financeMemories = await retryUntil(
    "Finance metadata retrieval",
    async () => normalizeResults(await client.getAll({ filters: financeFilter() })),
    (results) => results.length >= 2 && findByText(results, "tax") && results.every((memory) => memory?.id),
  );

  const financeArtifact = {
    user_id: userId,
    filter_category: "finance",
    results: financeMemories,
  };
  await writeJson("finance_memories.json", financeArtifact);

  const highPriorityMemories = await retryUntil(
    "High-priority semantic search",
    async () => normalizeResults(await client.search(SEARCH_QUERY, { filters: highPriorityFilter(), topK: 20 })),
    (results) => results.length >= 3 && results.every((memory) => memory?.id),
  );

  const highPriorityArtifact = {
    user_id: userId,
    filter_priority: "high",
    results: highPriorityMemories,
  };
  await writeJson("high_priority_search.json", highPriorityArtifact);

  const financeMemory = findByText(financeMemories, "tax");
  if (!financeMemory?.id) {
    throw new Error("Unable to find a finance memory containing the substring 'tax'.");
  }
  const FINANCE_ID = financeMemory.id;

  await client.update(FINANCE_ID, { text: UPDATED_FINANCE_TEXT });

  const history = await retryUntil(
    "Finance memory history retrieval",
    async () => normalizeHistory(await client.history(FINANCE_ID)),
    (entries) => entries.length >= 2 && hasUpdateEvent(entries),
  );

  const historyArtifact = {
    memory_id: FINANCE_ID,
    updated_text: UPDATED_FINANCE_TEXT,
    history,
  };
  await writeJson("finance_history.json", historyArtifact);

  const healthMemories = await retryUntil(
    "Health metadata retrieval",
    async () => normalizeResults(await client.getAll({ filters: healthFilter() })),
    (results) => findByText(results, "multivitamin")?.id,
  );

  const multivitaminMemory = findByText(healthMemories, "multivitamin");
  if (!multivitaminMemory?.id) {
    throw new Error("Unable to find a low-priority health memory containing the substring 'multivitamin'.");
  }
  const MULTIVITAMIN_ID = multivitaminMemory.id;
  await client.delete(MULTIVITAMIN_ID);

  const logLines = [
    `RUN_ID: ${ZEALT_RUN_ID}`,
    `USER_ID: ${userId}`,
    `FINANCE_COUNT: ${financeMemories.length}`,
    `HIGH_PRIORITY_COUNT: ${highPriorityMemories.length}`,
    `FINANCE_ID: ${FINANCE_ID}`,
    `MULTIVITAMIN_ID: ${MULTIVITAMIN_ID}`,
    `HISTORY_EVENTS: ${history.length}`,
  ];

  for (const line of logLines) {
    console.log(line);
  }
}

main().catch((error) => {
  console.error(error?.stack || error?.message || String(error));
  process.exitCode = 1;
});
