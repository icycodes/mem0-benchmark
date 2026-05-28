import fs from 'fs';
process.env.MEM0_TELEMETRY = "false";
import MemoryClient from 'mem0ai';

const RUN_ID = process.env.ZEALT_RUN_ID;
const API_KEY = process.env.MEM0_API_KEY;

if (!RUN_ID || !API_KEY) {
  console.error("Missing ZEALT_RUN_ID or MEM0_API_KEY");
  process.exit(1);
}

const userId = `planner-${RUN_ID}`;
// The managed Platform SDK expects just apiKey, but if we need it we can pass it.
// By default it might pick up MEM0_API_KEY from process.env, but it's safer to pass explicitly.
const client = new MemoryClient({ apiKey: API_KEY });

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  const logStream = fs.createWriteStream('/home/user/mem0-metadata-task/output.log', { flags: 'w' });
  function log(msg) {
    console.log(msg);
    logStream.write(msg + '\n');
  }

  log(`RUN_ID: ${RUN_ID}`);
  log(`USER_ID: ${userId}`);

  const notes = [
    { messages: [{"role": "user", "content": "I file my quarterly tax estimates with my accountant every March."}], metadata: {"category": "finance", "priority": "high"} },
    { messages: [{"role": "user", "content": "I max out my 401(k) contributions early each year."}], metadata: {"category": "finance", "priority": "low"} },
    { messages: [{"role": "user", "content": "I prefer aisle seats on long-haul flights and direct routes to Tokyo."}], metadata: {"category": "travel", "priority": "high"} },
    { messages: [{"role": "user", "content": "I run intervals on the treadmill three times a week."}], metadata: {"category": "health", "priority": "high"} },
    { messages: [{"role": "user", "content": "I take a daily multivitamin in the morning."}], metadata: {"category": "health", "priority": "low"} }
  ];

  for (const note of notes) {
    await client.add(note.messages, { userId, metadata: note.metadata });
  }

  // Wait for processing
  await sleep(6000);

  // Get finance memories
  let financeMemories = [];
  for (let i = 0; i < 6; i++) {
    const res = await client.getAll({
      filters: { AND: [{ user_id: userId }, { metadata: { category: "finance" } }] }
    });
    financeMemories = Array.isArray(res) ? res : (res.results || []);
    if (financeMemories.length >= 2) break;
    await sleep(3000);
  }

  fs.writeFileSync('/home/user/mem0-metadata-task/finance_memories.json', JSON.stringify({
    user_id: userId,
    filter_category: "finance",
    results: financeMemories
  }, null, 2));

  log(`FINANCE_COUNT: ${financeMemories.length}`);

  // Search high priority
  let highPriorityMemories = [];
  for (let i = 0; i < 6; i++) {
    const res = await client.search("Which of my notes are urgent and high priority?", {
      filters: { AND: [{ user_id: userId }, { metadata: { priority: "high" } }] },
      topK: 20
    });
    highPriorityMemories = Array.isArray(res) ? res : (res.results || []);
    if (highPriorityMemories.length >= 3) break;
    await sleep(3000);
  }

  fs.writeFileSync('/home/user/mem0-metadata-task/high_priority_search.json', JSON.stringify({
    user_id: userId,
    filter_priority: "high",
    results: highPriorityMemories
  }, null, 2));

  log(`HIGH_PRIORITY_COUNT: ${highPriorityMemories.length}`);

  const financeMemory = financeMemories.find(m => m.memory.toLowerCase().includes('tax'));
  const financeId = financeMemory ? financeMemory.id : financeMemories[0].id;
  log(`FINANCE_ID: ${financeId}`);

  await client.update(financeId, { text: "Files quarterly tax estimates in March and September with the accountant" });
  
  await sleep(3000);

  let history = [];
  for (let i = 0; i < 6; i++) {
    const historyRes = await client.history(financeId);
    history = Array.isArray(historyRes) ? historyRes : (historyRes.results || []);
    if (history.length >= 2) break;
    await sleep(2000);
  }

  fs.writeFileSync('/home/user/mem0-metadata-task/finance_history.json', JSON.stringify({
    memory_id: financeId,
    updated_text: "Files quarterly tax estimates in March and September with the accountant",
    history
  }, null, 2));

  log(`HISTORY_EVENTS: ${history.length}`);

  // Need to get all to find the multivitamin memory
  let allMemories = [];
  for (let i = 0; i < 6; i++) {
    const allRes = await client.getAll({ filters: { AND: [{ user_id: userId }] } });
    allMemories = Array.isArray(allRes) ? allRes : (allRes.results || []);
    if (allMemories.length >= 5) break;
    await sleep(2000);
  }
  
  const multivitaminMemory = allMemories.find(m => m.memory.toLowerCase().includes('multivitamin'));
  const multivitaminId = multivitaminMemory ? multivitaminMemory.id : allMemories[0].id;
  
  log(`MULTIVITAMIN_ID: ${multivitaminId}`);

  await client.delete(multivitaminId);
  logStream.end();
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
