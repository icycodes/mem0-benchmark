import fs from "fs/promises";
import MemoryClient from "mem0ai";

const { MEM0_API_KEY, ZEALT_RUN_ID } = process.env;

if (!MEM0_API_KEY) {
  throw new Error("Missing required environment variable MEM0_API_KEY");
}

if (!ZEALT_RUN_ID) {
  throw new Error("Missing required environment variable ZEALT_RUN_ID");
}

const runId = ZEALT_RUN_ID;
const userId = `planner-${runId}`;

const client = new MemoryClient({ apiKey: MEM0_API_KEY });

const notes = [
  {
    messages: [
      {
        role: "user",
        content: "I file my quarterly tax estimates with my accountant every March.",
      },
    ],
    metadata: { category: "finance", priority: "high" },
  },
  {
    messages: [
      {
        role: "user",
        content: "I max out my 401(k) contributions early each year.",
      },
    ],
    metadata: { category: "finance", priority: "low" },
  },
  {
    messages: [
      {
        role: "user",
        content:
          "I prefer aisle seats on long-haul flights and direct routes to Tokyo.",
      },
    ],
    metadata: { category: "travel", priority: "high" },
  },
  {
    messages: [
      {
        role: "user",
        content: "I run intervals on the treadmill three times a week.",
      },
    ],
    metadata: { category: "health", priority: "high" },
  },
  {
    messages: [
      {
        role: "user",
        content: "I take a daily multivitamin in the morning.",
      },
    ],
    metadata: { category: "health", priority: "low" },
  },
];

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const normalizeResults = (response) => {
  if (Array.isArray(response)) {
    return response;
  }
  if (response && Array.isArray(response.results)) {
    return response.results;
  }
  return [];
};

const getMemoryText = (memory) => {
  if (!memory) return "";
  return (
    memory.text ||
    memory.memory ||
    memory.content ||
    memory.message ||
    ""
  );
};

const retry = async (fn, { retries = 5, waitMs = 1200 } = {}) => {
  let lastResult;
  for (let attempt = 0; attempt < retries; attempt += 1) {
    lastResult = await fn();
    if (lastResult) {
      return lastResult;
    }
    await delay(waitMs);
  }
  return lastResult;
};

const writeJson = (path, data) =>
  fs.writeFile(path, `${JSON.stringify(data, null, 2)}\n`);

const run = async () => {
  for (const note of notes) {
    await client.add(note.messages, { userId, metadata: note.metadata });
  }

  const financeFilter = {
    AND: [{ user_id: userId }, { metadata: { category: "finance" } }],
  };

  const financeResults = await retry(async () => {
    const response = await client.getAll({ filters: financeFilter });
    const results = normalizeResults(response);
    return results.length >= 2 ? results : null;
  });

  const financeMemories = financeResults ?? [];

  const financeArtifact = {
    user_id: userId,
    filter_category: "finance",
    results: financeMemories,
  };

  await writeJson(
    "/home/user/mem0-metadata-task/finance_memories.json",
    financeArtifact
  );

  const highPriorityFilter = {
    AND: [{ user_id: userId }, { metadata: { priority: "high" } }],
  };

  const highPriorityResults = await retry(async () => {
    const response = await client.search(
      "Which of my notes are urgent and high priority?",
      {
        filters: highPriorityFilter,
        topK: 20,
      }
    );
    const results = normalizeResults(response);
    return results.length >= 3 ? results : null;
  });

  const highPriorityMemories = highPriorityResults ?? [];

  const highPriorityArtifact = {
    user_id: userId,
    filter_priority: "high",
    results: highPriorityMemories,
  };

  await writeJson(
    "/home/user/mem0-metadata-task/high_priority_search.json",
    highPriorityArtifact
  );

  const financeMemory = financeMemories.find((memory) =>
    getMemoryText(memory).toLowerCase().includes("tax")
  );

  if (!financeMemory || !financeMemory.id) {
    throw new Error("Unable to locate finance memory containing 'tax'.");
  }

  const financeId = financeMemory.id;
  const updatedText =
    "Files quarterly tax estimates in March and September with the accountant";

  await client.update(financeId, { text: updatedText });

  const historyResponse = await retry(async () => {
    const response = await client.history(financeId);
    const results = normalizeResults(response);
    return results.length >= 2 ? results : null;
  });

  const history = historyResponse ?? [];

  const historyArtifact = {
    memory_id: financeId,
    updated_text: updatedText,
    history,
  };

  await writeJson(
    "/home/user/mem0-metadata-task/finance_history.json",
    historyArtifact
  );

  const healthLowFilter = {
    AND: [
      { user_id: userId },
      { metadata: { category: "health", priority: "low" } },
    ],
  };

  const healthLowResults = await retry(async () => {
    const response = await client.getAll({ filters: healthLowFilter });
    const results = normalizeResults(response);
    return results.length >= 1 ? results : null;
  });

  const healthLowMemories = healthLowResults ?? [];

  const multivitaminMemory = healthLowMemories.find((memory) =>
    getMemoryText(memory).toLowerCase().includes("multivitamin")
  );

  if (!multivitaminMemory || !multivitaminMemory.id) {
    throw new Error("Unable to locate multivitamin memory for deletion.");
  }

  const multivitaminId = multivitaminMemory.id;
  await client.delete(multivitaminId);

  const logLines = [
    `RUN_ID: ${runId}`,
    `USER_ID: ${userId}`,
    `FINANCE_COUNT: ${financeMemories.length}`,
    `HIGH_PRIORITY_COUNT: ${highPriorityMemories.length}`,
    `FINANCE_ID: ${financeId}`,
    `MULTIVITAMIN_ID: ${multivitaminId}`,
    `HISTORY_EVENTS: ${history.length}`,
  ];

  for (const line of logLines) {
    console.log(line);
  }

  await fs.writeFile(
    "/home/user/mem0-metadata-task/output.log",
    `${logLines.join("\n")}\n`
  );
};

await run();
