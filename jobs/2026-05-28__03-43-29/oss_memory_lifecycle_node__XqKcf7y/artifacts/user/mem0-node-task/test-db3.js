import fs from 'fs';
import path from 'path';
import os from 'os';
import { Memory } from 'mem0ai/oss';

const memory = new Memory({
  llm: { provider: 'openai', config: { model: 'gpt-4o-mini', apiKey: process.env.OPENAI_API_KEY } },
  embedder: { provider: 'openai', config: { model: 'text-embedding-3-small', apiKey: process.env.OPENAI_API_KEY } },
  vectorStore: { provider: 'memory', config: { collectionName: 'memories', dimension: 1536 } },
  historyDbPath: './memory.db'
});

async function test() {
  await memory._ensureInitialized();
  const rows = memory.vectorStore.db.prepare('SELECT * FROM vectors').all();
  console.log('rows:', rows.length);
  if (rows.length > 0) {
    console.log('first payload:', rows[0].payload);
  }
}
test();
