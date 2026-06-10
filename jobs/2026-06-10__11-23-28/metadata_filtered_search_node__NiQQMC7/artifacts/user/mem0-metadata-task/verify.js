import fs from "node:fs/promises";
import MemoryClient from "mem0ai";

const projectDir = "/home/user/mem0-metadata-task";
const runId = process.env.ZEALT_RUN_ID;
const apiKey = process.env.MEM0_API_KEY;
if (!runId || !apiKey) {
  throw new Error("MEM0_API_KEY and ZEALT_RUN_ID must be set for verification.");
}
const userId = `planner-${runId}`;
const client = new MemoryClient({ apiKey });

function normalize(response) {
  if (Array.isArray(response)) return response;
  if (response && Array.isArray(response.results)) return response.results;
  if (response && Array.isArray(response.history)) return response.history;
  return [];
}

function textOf(memory) {
  return [
    memory?.memory,
    memory?.text,
    memory?.content,
    memory?.data?.memory,
    memory?.newMemory,
    memory?.oldMemory,
    ...(Array.isArray(memory?.messages) ? memory.messages.map((message) => message?.content) : []),
  ]
    .filter((value) => typeof value === "string")
    .join("\n");
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function readJson(name) {
  return JSON.parse(await fs.readFile(`${projectDir}/${name}`, "utf8"));
}

const log = await fs.readFile(`${projectDir}/output.log`, "utf8");
const expectedLogPrefixes = [
  `RUN_ID: ${runId}`,
  `USER_ID: ${userId}`,
  "FINANCE_COUNT: ",
  "HIGH_PRIORITY_COUNT: ",
  "FINANCE_ID: ",
  "MULTIVITAMIN_ID: ",
  "HISTORY_EVENTS: ",
];
const logLines = log.trim().split(/\r?\n/);
assert(logLines.length >= expectedLogPrefixes.length, "output.log does not contain all required lines");
expectedLogPrefixes.forEach((prefix, index) => assert(logLines[index].startsWith(prefix), `output.log line ${index + 1} missing prefix ${prefix}`));

const finance = await readJson("finance_memories.json");
assert(finance.user_id === userId, "finance_memories.json has wrong user_id");
assert(finance.filter_category === "finance", "finance_memories.json has wrong filter_category");
assert(Array.isArray(finance.results) && finance.results.length >= 2, "finance_memories.json has too few results");
assert(finance.results.every((memory) => memory.id && textOf(memory)), "finance memories need id and text");

const highPriority = await readJson("high_priority_search.json");
assert(highPriority.user_id === userId, "high_priority_search.json has wrong user_id");
assert(highPriority.filter_priority === "high", "high_priority_search.json has wrong filter_priority");
assert(Array.isArray(highPriority.results) && highPriority.results.length >= 3, "high_priority_search.json has too few results");
assert(highPriority.results.every((memory) => memory.id && textOf(memory)), "high-priority memories need id and text");

const history = await readJson("finance_history.json");
assert(history.memory_id, "finance_history.json missing memory_id");
assert(history.updated_text === "Files quarterly tax estimates in March and September with the accountant", "finance_history.json has wrong updated_text");
assert(Array.isArray(history.history) && history.history.length >= 2, "finance_history.json history too short");
assert(history.history.some((entry) => String(entry.event ?? entry.type ?? "").toUpperCase() === "UPDATE"), "finance_history.json missing UPDATE event");

const byCategory = (category) => ({ AND: [{ user_id: userId }, { metadata: { category } }] });
const liveFinance = normalize(await client.getAll({ filters: byCategory("finance") }));
assert(liveFinance.some((memory) => /September/i.test(textOf(memory))), "live finance memories do not include September update");

const liveHealth = normalize(await client.getAll({ filters: byCategory("health") }));
assert(!liveHealth.some((memory) => /multivitamin/i.test(textOf(memory))), "live health memories still include multivitamin");

const liveTravel = normalize(await client.getAll({ filters: byCategory("travel") }));
assert(liveTravel.some((memory) => /Tokyo/i.test(textOf(memory))), "live travel memories do not include Tokyo");

console.log("Verification passed");
