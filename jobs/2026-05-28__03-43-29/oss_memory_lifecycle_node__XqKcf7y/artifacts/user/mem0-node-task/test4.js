import { Memory } from 'mem0ai/oss';
const memory = new Memory({
  llm: { provider: 'openai', config: { model: 'gpt-4o-mini', apiKey: process.env.OPENAI_API_KEY } },
  embedder: { provider: 'openai', config: { model: 'text-embedding-3-small', apiKey: process.env.OPENAI_API_KEY } },
  vectorStore: { provider: 'memory', config: { collectionName: 'memories', dimension: 1536 } },
  historyDbPath: './memory.db'
});
async function test() {
  await memory.add([{ role: 'user', content: 'test' }], { userId: 'test-user' });
  let res = await memory.getAll({});
  console.log('getAll all:', JSON.stringify(res, null, 2));
}
test();
