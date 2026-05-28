import Database from 'better-sqlite3';
import path from 'path';
import os from 'os';

const dbPath = path.join(os.homedir(), ".mem0", "vector_store.db");
const db = new Database(dbPath);
const rows = db.prepare('SELECT id, payload FROM vectors').all();
console.log(rows);
