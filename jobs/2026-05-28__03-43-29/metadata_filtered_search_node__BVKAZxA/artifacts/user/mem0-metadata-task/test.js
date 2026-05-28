import MemoryClient from 'mem0ai';
const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY });
console.log("MemoryClient keys:", Object.keys(client));
