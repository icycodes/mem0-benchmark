import { Memory } from 'mem0ai/oss';
const memory = new Memory({
  llm: { provider: 'openai', config: { model: 'gpt-4o-mini', apiKey: process.env.OPENAI_API_KEY } },
  embedder: { provider: 'openai', config: { model: 'text-embedding-3-small', apiKey: process.env.OPENAI_API_KEY } },
  vectorStore: { provider: 'memory', config: { collectionName: 'memories', dimension: 1536 } },
  historyDbPath: './memory.db'
});
async function test() {
  await memory.add([{ role: 'user', content: 'test' }], { userId: 'test-user' });
  let res2 = await memory.search('test', { filters: { user_id: 'test-user' } });
  console.log('res2 length:', res2.results ? res2.results.length : res2.length);
}
test();
