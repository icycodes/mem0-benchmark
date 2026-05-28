import MemoryClient from "mem0ai";
import { writeFileSync } from "fs";

// ── 1. Environment validation ────────────────────────────────────────────────
const MEM0_API_KEY = process.env.MEM0_API_KEY;
const ZEALT_RUN_ID = process.env.ZEALT_RUN_ID;

if (!MEM0_API_KEY) {
  console.error("ERROR: MEM0_API_KEY environment variable is not set.");
  process.exit(1);
}
if (!ZEALT_RUN_ID) {
  console.error("ERROR: ZEALT_RUN_ID environment variable is not set.");
  process.exit(1);
}

// ── 2. Client & identifiers ──────────────────────────────────────────────────
const client = new MemoryClient({ apiKey: MEM0_API_KEY });
const runId = ZEALT_RUN_ID;
const userId = `planner-${runId}`;

console.log(`RUN_ID: ${runId}`);
console.log(`USER_ID: ${userId}`);

// ── 3. Helper: sleep ─────────────────────────────────────────────────────────
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ── 4. Helper: normalize SDK response to array ───────────────────────────────
function normalizeToList(response) {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
}

// ── 5. Ingest five notes ─────────────────────────────────────────────────────
console.log("\n[STEP 1] Ingesting five notes...");

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

const addResults = [];
for (const note of notes) {
  const result = await client.add(note.messages, {
    userId,
    metadata: note.metadata,
  });
  addResults.push(result);
  console.log(`  Added note [${note.metadata.category}/${note.metadata.priority}]`);
}

// ── 6. Wait for async memory extraction ──────────────────────────────────────
console.log("\n[STEP 2] Waiting for Mem0 platform to process memories...");

// Retry loop: wait until we have at least 2 finance memories
let financeMemories = [];
let attempt = 0;
const maxAttempts = 20;
const retryDelay = 5000; // 5 seconds

while (attempt < maxAttempts) {
  attempt++;
  console.log(`  Polling attempt ${attempt}/${maxAttempts}...`);

  const getAllResponse = await client.getAll({
    filters: {
      AND: [
        { user_id: userId },
        { metadata: { category: "finance" } },
      ],
    },
  });

  financeMemories = normalizeToList(getAllResponse);
  console.log(`  Finance memories found: ${financeMemories.length}`);

  if (financeMemories.length >= 2) {
    console.log("  ✓ Got at least 2 finance memories — proceeding.");
    break;
  }

  if (attempt < maxAttempts) {
    console.log(`  Waiting ${retryDelay / 1000}s before retry...`);
    await sleep(retryDelay);
  }
}

if (financeMemories.length < 2) {
  console.warn(`WARNING: Only ${financeMemories.length} finance memories found after ${maxAttempts} attempts.`);
}

// ── 7. Persist finance_memories.json ─────────────────────────────────────────
console.log("\n[STEP 3] Persisting finance_memories.json...");

const financeArtifact = {
  user_id: userId,
  filter_category: "finance",
  results: financeMemories,
};

writeFileSync(
  "/home/user/mem0-metadata-task/finance_memories.json",
  JSON.stringify(financeArtifact, null, 2)
);

console.log(`FINANCE_COUNT: ${financeMemories.length}`);

// ── 8. Semantic search: high-priority notes ───────────────────────────────────
console.log("\n[STEP 4] Searching for high-priority notes...");

// Retry loop for high priority search to get >= 3 results
let highPriorityMemories = [];
let searchAttempt = 0;
const maxSearchAttempts = 20;

while (searchAttempt < maxSearchAttempts) {
  searchAttempt++;
  console.log(`  Search attempt ${searchAttempt}/${maxSearchAttempts}...`);

  const searchResponse = await client.search(
    "Which of my notes are urgent and high priority?",
    {
      filters: {
        AND: [
          { user_id: userId },
          { metadata: { priority: "high" } },
        ],
      },
      topK: 20,
    }
  );

  highPriorityMemories = normalizeToList(searchResponse);
  console.log(`  High-priority memories found: ${highPriorityMemories.length}`);

  if (highPriorityMemories.length >= 3) {
    console.log("  ✓ Got at least 3 high-priority memories — proceeding.");
    break;
  }

  if (searchAttempt < maxSearchAttempts) {
    console.log(`  Waiting ${retryDelay / 1000}s before retry...`);
    await sleep(retryDelay);
  }
}

if (highPriorityMemories.length < 3) {
  console.warn(`WARNING: Only ${highPriorityMemories.length} high-priority memories found after ${maxSearchAttempts} attempts.`);
}

// Persist high_priority_search.json
console.log("\n[STEP 5] Persisting high_priority_search.json...");

const highPriorityArtifact = {
  user_id: userId,
  filter_priority: "high",
  results: highPriorityMemories,
};

writeFileSync(
  "/home/user/mem0-metadata-task/high_priority_search.json",
  JSON.stringify(highPriorityArtifact, null, 2)
);

console.log(`HIGH_PRIORITY_COUNT: ${highPriorityMemories.length}`);

// ── 9. Identify FINANCE_ID (tax memory) ──────────────────────────────────────
console.log("\n[STEP 6] Identifying finance tax memory...");

let taxMemory = financeMemories.find((m) => {
  const text = m.memory || m.text || m.content || "";
  return text.toLowerCase().includes("tax");
});

if (!taxMemory) {
  // Fallback: re-fetch and search broader
  console.log("  Tax memory not found in cached results, re-fetching all finance memories...");
  const reRefetch = await client.getAll({
    filters: {
      AND: [
        { user_id: userId },
        { metadata: { category: "finance" } },
      ],
    },
  });
  const reList = normalizeToList(reRefetch);
  taxMemory = reList.find((m) => {
    const text = m.memory || m.text || m.content || "";
    return text.toLowerCase().includes("tax");
  });
}

if (!taxMemory) {
  console.error("ERROR: Could not find finance memory containing 'tax'. Available memories:");
  financeMemories.forEach((m) => console.error("  -", JSON.stringify(m)));
  process.exit(1);
}

const FINANCE_ID = taxMemory.id;
console.log(`  Found tax memory with id: ${FINANCE_ID}`);

// ── 10. Update the finance tax memory ────────────────────────────────────────
console.log("\n[STEP 7] Updating finance tax memory...");

const updatedText = "Files quarterly tax estimates in March and September with the accountant";
await client.update(FINANCE_ID, { text: updatedText });
console.log(`  Updated memory ${FINANCE_ID}`);

// ── 11. Retrieve history ──────────────────────────────────────────────────────
console.log("\n[STEP 8] Fetching memory history...");

// Small wait to let update propagate
await sleep(3000);

let historyList = [];
let histAttempt = 0;
const maxHistAttempts = 10;

while (histAttempt < maxHistAttempts) {
  histAttempt++;
  const historyResponse = await client.history(FINANCE_ID);
  historyList = Array.isArray(historyResponse) ? historyResponse : [];
  console.log(`  History events found: ${historyList.length}`);

  const hasUpdate = historyList.some((e) => {
    const eventType = e.event || e.type || e.action || "";
    return eventType.toLowerCase().includes("update");
  });

  if (historyList.length >= 2 && hasUpdate) {
    console.log("  ✓ History has >= 2 entries and includes UPDATE event.");
    break;
  }

  if (histAttempt < maxHistAttempts) {
    console.log(`  Waiting 3s for history to reflect update...`);
    await sleep(3000);
  }
}

// Persist finance_history.json
const historyArtifact = {
  memory_id: FINANCE_ID,
  updated_text: updatedText,
  history: historyList,
};

writeFileSync(
  "/home/user/mem0-metadata-task/finance_history.json",
  JSON.stringify(historyArtifact, null, 2)
);

console.log(`FINANCE_ID: ${FINANCE_ID}`);
console.log(`HISTORY_EVENTS: ${historyList.length}`);

// ── 12. Identify and delete multivitamin (low-priority health) memory ─────────
console.log("\n[STEP 9] Identifying and deleting low-priority health memory (multivitamin)...");

// Fetch all health memories for this user
const healthResponse = await client.getAll({
  filters: {
    AND: [
      { user_id: userId },
      { metadata: { category: "health" } },
    ],
  },
});
const healthMemories = normalizeToList(healthResponse);

let multivitaminMemory = healthMemories.find((m) => {
  const text = m.memory || m.text || m.content || "";
  return text.toLowerCase().includes("multivitamin");
});

if (!multivitaminMemory) {
  // Fallback: scan all memories for user
  console.log("  Multivitamin memory not found in health filter, scanning all user memories...");
  const allResponse = await client.getAll({ userId });
  const allList = normalizeToList(allResponse);
  multivitaminMemory = allList.find((m) => {
    const text = m.memory || m.text || m.content || "";
    return text.toLowerCase().includes("multivitamin");
  });
}

if (!multivitaminMemory) {
  console.error("ERROR: Could not find multivitamin memory. Available health memories:");
  healthMemories.forEach((m) => console.error("  -", JSON.stringify(m)));
  process.exit(1);
}

const MULTIVITAMIN_ID = multivitaminMemory.id;
console.log(`  Found multivitamin memory with id: ${MULTIVITAMIN_ID}`);

await client.delete(MULTIVITAMIN_ID);
console.log(`  Deleted memory ${MULTIVITAMIN_ID}`);

console.log(`MULTIVITAMIN_ID: ${MULTIVITAMIN_ID}`);

// ── 13. Summary ───────────────────────────────────────────────────────────────
console.log("\n[DONE] All steps completed successfully.");
console.log(`  finance_memories.json  → ${financeMemories.length} results`);
console.log(`  high_priority_search.json → ${highPriorityMemories.length} results`);
console.log(`  finance_history.json   → ${historyList.length} history events`);
