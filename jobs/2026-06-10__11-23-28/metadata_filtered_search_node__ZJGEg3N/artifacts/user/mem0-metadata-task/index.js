import MemoryClient from "mem0ai";
import { writeFileSync } from "fs";
import { resolve } from "path";

// --- Configuration ---
const OUTPUT_DIR = "/home/user/mem0-metadata-task";
const LOG_PATH = resolve(OUTPUT_DIR, "output.log");

// Collect log lines and also write to stdout
const logLines = [];
function log(line) {
  logLines.push(line);
  process.stdout.write(line + "\n");
}

// --- Validate environment ---
const MEM0_API_KEY = process.env.MEM0_API_KEY;
const ZEALT_RUN_ID = process.env.ZEALT_RUN_ID;

if (!MEM0_API_KEY) {
  log("ERROR: MEM0_API_KEY environment variable is not set.");
  process.exit(1);
}
if (!ZEALT_RUN_ID) {
  log("ERROR: ZEALT_RUN_ID environment variable is not set.");
  process.exit(1);
}

const RUN_ID = ZEALT_RUN_ID;
const USER_ID = `planner-${RUN_ID}`;

log(`RUN_ID: ${RUN_ID}`);
log(`USER_ID: ${USER_ID}`);

// --- Helper: normalize SDK list responses ---
function normalizeList(result) {
  if (result && Array.isArray(result.results)) {
    return result.results;
  }
  if (Array.isArray(result)) {
    return result;
  }
  return [];
}

// --- Helper: wait/retry loop for async memory extraction ---
async function waitForMemories(checkFn, label, minCount = 1, maxRetries = 20, delayMs = 4000) {
  let lastResults = [];
  for (let i = 0; i < maxRetries; i++) {
    const results = await checkFn();
    lastResults = results;
    if (results && results.length >= minCount) {
      return results;
    }
    if (i < maxRetries - 1) {
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  return lastResults; // one last attempt
}

async function main() {
  const client = new MemoryClient({ apiKey: MEM0_API_KEY });

  // ============================================================
  // Step 1: Ingest five notes
  // ============================================================
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

  for (const note of notes) {
    await client.add(note.messages, { user_id: USER_ID, metadata: note.metadata });
  }

  // ============================================================
  // Step 2: getAll with v2 AND filter for category=finance
  // ============================================================
  const financeFilter = {
    AND: [
      { user_id: USER_ID },
      { metadata: { category: "finance" } },
    ],
  };

  const financeResults = await waitForMemories(
    async () => {
      const res = await client.getAll({ filters: financeFilter, api_version: "v2" });
      return normalizeList(res);
    },
    "finance",
    2
  );

  const financeCount = financeResults.length;
  log(`FINANCE_COUNT: ${financeCount}`);

  const financeArtifact = {
    user_id: USER_ID,
    filter_category: "finance",
    results: financeResults,
  };
  writeFileSync(
    resolve(OUTPUT_DIR, "finance_memories.json"),
    JSON.stringify(financeArtifact, null, 2)
  );

  // ============================================================
  // Step 3: search with v2 AND filter for priority=high
  // ============================================================
  const highPriorityFilter = {
    AND: [
      { user_id: USER_ID },
      { metadata: { priority: "high" } },
    ],
  };

  const highPriorityResults = await waitForMemories(
    async () => {
      const res = await client.search("Which of my notes are urgent and high priority?", {
        filters: highPriorityFilter,
        topK: 20,
        api_version: "v2",
      });
      return normalizeList(res);
    },
    "high-priority",
    3
  );

  const highPriorityCount = highPriorityResults.length;
  log(`HIGH_PRIORITY_COUNT: ${highPriorityCount}`);

  const searchArtifact = {
    user_id: USER_ID,
    filter_priority: "high",
    results: highPriorityResults,
  };
  writeFileSync(
    resolve(OUTPUT_DIR, "high_priority_search.json"),
    JSON.stringify(searchArtifact, null, 2)
  );

  // ============================================================
  // Step 4: Update the finance memory containing "tax" + get history
  // ============================================================
  const taxMemory = financeResults.find(
    (m) => {
      const text = m.memory || m.text || "";
      return text.toLowerCase().includes("tax");
    }
  );
  if (!taxMemory) {
    log("ERROR: Could not find finance memory containing 'tax'");
    process.exit(1);
  }

  const FINANCE_ID = taxMemory.id;
  log(`FINANCE_ID: ${FINANCE_ID}`);

  const updatedText = "Files quarterly tax estimates in March and September with the accountant";
  await client.update(FINANCE_ID, { text: updatedText });

  // Wait a moment for the update to propagate
  await new Promise((r) => setTimeout(r, 3000));

  const history = await client.history(FINANCE_ID);
  const historyList = normalizeList(history);
  const historyEvents = historyList.length;
  log(`HISTORY_EVENTS: ${historyEvents}`);

  const historyArtifact = {
    memory_id: FINANCE_ID,
    updated_text: updatedText,
    history: historyList,
  };
  writeFileSync(
    resolve(OUTPUT_DIR, "finance_history.json"),
    JSON.stringify(historyArtifact, null, 2)
  );

  // ============================================================
  // Step 5: Delete the low-priority health memory (multivitamin)
  // ============================================================
  const healthFilter = {
    AND: [
      { user_id: USER_ID },
      { metadata: { category: "health" } },
    ],
  };

  const healthResults = await waitForMemories(
    async () => {
      const res = await client.getAll({ filters: healthFilter, api_version: "v2" });
      return normalizeList(res);
    },
    "health",
    2
  );

  const multivitaminMemory = healthResults.find(
    (m) => {
      const text = m.memory || m.text || "";
      return text.toLowerCase().includes("multivitamin");
    }
  );
  if (!multivitaminMemory) {
    log("ERROR: Could not find health memory containing 'multivitamin'");
    process.exit(1);
  }

  const MULTIVITAMIN_ID = multivitaminMemory.id;
  log(`MULTIVITAMIN_ID: ${MULTIVITAMIN_ID}`);

  await client.delete(MULTIVITAMIN_ID);

  // ============================================================
  // Step 6: Write output.log
  // ============================================================
  writeFileSync(LOG_PATH, logLines.join("\n") + "\n");

  log("Script completed successfully.");
}

main().catch((err) => {
  log(`FATAL ERROR: ${err.message}`);
  log(err.stack || "");
  process.exit(1);
});
