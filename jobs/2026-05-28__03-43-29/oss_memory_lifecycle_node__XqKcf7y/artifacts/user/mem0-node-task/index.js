import fs from 'fs';
import { Memory } from 'mem0ai/oss';

const runId = process.env.ZEALT_RUN_ID || 'default-run-id';
const apiKey = process.env.OPENAI_API_KEY;

if (!apiKey) {
  console.error("OPENAI_API_KEY is missing");
  process.exit(1);
}

const memory = new Memory({
  llm: {
    provider: 'openai',
    config: {
      model: 'gpt-4o-mini',
      apiKey: apiKey,
    }
  },
  embedder: {
    provider: 'openai',
    config: {
      model: 'text-embedding-3-small',
      apiKey: apiKey,
    }
  },
  vectorStore: {
    provider: 'memory',
    config: {
      collectionName: 'memories',
      dimension: 1536,
    }
  },
  historyDbPath: './memory.db'
});

async function run() {
  const aliceUserId = `alice-${runId}`;
  const bobUserId = `bob-${runId}`;

  // Ingest Alice
  const aliceMessages = [
    { role: 'user', content: 'I am vegetarian and I love sourdough bread.' },
    { role: 'assistant', content: "Noted. I'll save your vegetarian diet and sourdough preference." },
    { role: 'user', content: 'I also keep a strict no-nuts kitchen for my partner.' }
  ];
  await memory.add(aliceMessages, { userId: aliceUserId });

  // Ingest Bob
  const bobMessages = [
    { role: 'user', content: 'I have a shellfish allergy and I cook a lot of Thai green curry.' },
    { role: 'assistant', content: 'Got it. Logged your shellfish allergy and Thai green curry preference.' },
    { role: 'user', content: 'I always use jasmine rice as the side.' }
  ];
  await memory.add(bobMessages, { userId: bobUserId });

  // Search
  const query = "What are this cook's dietary preferences?";
  
  let aliceSearch = await memory.search(query, { filters: { user_id: aliceUserId } });
  let aliceResults = Array.isArray(aliceSearch) ? aliceSearch : (aliceSearch.results || []);
  fs.writeFileSync('alice_search.json', JSON.stringify({
    userId: aliceUserId,
    results: aliceResults
  }, null, 2));

  let bobSearch = await memory.search(query, { filters: { user_id: bobUserId } });
  let bobResults = Array.isArray(bobSearch) ? bobSearch : (bobSearch.results || []);
  fs.writeFileSync('bob_search.json', JSON.stringify({
    userId: bobUserId,
    results: bobResults
  }, null, 2));

  // Update Alice
  let aliceMemories = await memory.getAll({ filters: { user_id: aliceUserId } });
  let aliceAllResults = Array.isArray(aliceMemories) ? aliceMemories : (aliceMemories.results || []);
  
  let memoryToUpdate = aliceAllResults.find(m => m.memory && m.memory.toLowerCase().includes('vegetarian'));
  
  if (!memoryToUpdate) {
    throw new Error("No vegetarian memory found for Alice");
  }

  const updatedText = "Alice is vegan and avoids all animal products";
  await memory.update(memoryToUpdate.id, updatedText);

  // History
  let history = await memory.history(memoryToUpdate.id);
  
  fs.writeFileSync('alice_history.json', JSON.stringify({
    memoryId: memoryToUpdate.id,
    updatedText: updatedText,
    history: history
  }, null, 2));

  const logOutput = [
    `RUN_ID: ${runId}`,
    `ALICE_RESULTS: ${aliceResults.length}`,
    `BOB_RESULTS: ${bobResults.length}`,
    `UPDATED_MEMORY_ID: ${memoryToUpdate.id}`,
    `HISTORY_EVENTS: ${history.length}`
  ].join('\n');

  console.log(logOutput);
  fs.writeFileSync('output.log', logOutput + '\n');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
