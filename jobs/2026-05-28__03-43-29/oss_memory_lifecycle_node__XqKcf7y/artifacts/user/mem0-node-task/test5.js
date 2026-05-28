import { Memory } from 'mem0ai/oss';
const memory = new Memory({
  llm: { provider: 'openai', config: { model: 'gpt-4o-mini', apiKey: process.env.OPENAI_API_KEY } },
  embedder: { provider: 'openai', config: { model: 'text-embedding-3-small', apiKey: process.env.OPENAI_API_KEY } },
  vectorStore: { provider: 'memory', config: { collectionName: 'memories', dimension: 1536 } },
  historyDbPath: './memory.db'
});
async function test() {
  try {
    let res1 = await memory.search('test', { userId: 'test-user' });
    console.log('res1 success');
  } catch (e) { console.log('res1 failed:', e.message); }
}
test();
