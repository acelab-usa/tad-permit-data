import Database from "better-sqlite3";
import path from "path";

// The pipeline's permits.db lives in the sibling Python project
// (tad-permit-pipeline/), written by database.py/workflow.py. This app only
// ever reads it -- ingestion, enrichment, and normalization all stay in
// Python. Override with PERMITS_DB_PATH if the two projects aren't checked
// out as siblings.
const DEFAULT_DB_PATH = path.join(
  process.cwd(),
  "..",
  "tad-permit-pipeline",
  "permits.db"
);

const DB_PATH = process.env.PERMITS_DB_PATH || DEFAULT_DB_PATH;

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (db) return db;
  // readonly + fileMustExist: this app never creates or migrates the
  // schema -- that's database.py's job. If the file's missing, the error
  // should say so clearly instead of silently creating an empty one.
  db = new Database(DB_PATH, { readonly: true, fileMustExist: true });
  return db;
}

export { DB_PATH };
