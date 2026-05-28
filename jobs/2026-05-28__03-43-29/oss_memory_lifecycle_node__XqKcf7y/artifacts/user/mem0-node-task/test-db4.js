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
  for (let row of rows) {
    if (row.payload.includes('test-user')) {
      console.log('found test-user:', row.payload);
    }
  }
}
test();
