import fs from "fs";
import path from "path";
import initSqlJs, { type Database as SqlJsDatabase } from "sql.js";

// The pipeline's permits.db lives in the sibling Python project
// (tad-permit-pipeline/), written by database.py/workflow.py. This app only
// ever reads it -- ingestion, enrichment, and normalization all stay in
// Python. Override with PERMITS_DB_PATH if the two projects aren't checked
// out as siblings.
const DEFAULT_DB_PATH = path.join(
  /*turbopackIgnore: true*/ process.cwd(),
  "..",
  "tad-permit-pipeline",
  "permits.db"
);

const DB_PATH = process.env.PERMITS_DB_PATH || DEFAULT_DB_PATH;

// sql.js is a pure-WASM build of SQLite (Emscripten-compiled) -- unlike
// better-sqlite3, it needs no native compilation for the host machine, so
// there's no node-gyp/prebuilt-binary mismatch to break on someone's local
// toolchain. The tradeoff: it loads the whole file into memory rather than
// holding an open file handle, so getDb() re-reads permits.db from disk on
// every call. That's fine at this table's size (a few hundred KB) and
// actually matches the "always reflect the current file" behavior the API
// route wants (no stale cache to invalidate after a re-ingestion run).
let sqlJsPromise: ReturnType<typeof initSqlJs> | null = null;

function getSqlJs() {
  if (!sqlJsPromise) {
    sqlJsPromise = initSqlJs({
      locateFile: (file: string) =>
        path.join(/*turbopackIgnore: true*/ process.cwd(), "node_modules", "sql.js", "dist", file),
    });
  }
  return sqlJsPromise;
}

export async function withDb<T>(fn: (db: SqlJsDatabase) => T): Promise<T> {
  if (!fs.existsSync(DB_PATH)) {
    throw new Error(`permits.db not found at ${DB_PATH}`);
  }

  const SQL = await getSqlJs();
  const fileBuffer = fs.readFileSync(DB_PATH);
  const db = new SQL.Database(fileBuffer);
  try {
    return fn(db);
  } finally {
    db.close();
  }
}

export { DB_PATH };
