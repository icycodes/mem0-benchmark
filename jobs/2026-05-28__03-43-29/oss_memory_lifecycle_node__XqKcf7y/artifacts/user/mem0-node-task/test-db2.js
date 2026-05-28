import Database from 'better-sqlite3';
import path from 'path';
import os from 'os';

const dbPath = path.join(os.homedir(), ".mem0", "vector_store.db");
const db = new Database(dbPath);
const count = db.prepare('SELECT count(*) as c FROM vectors').get();
console.log('count:', count.c);
