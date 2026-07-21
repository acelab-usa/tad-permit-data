import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import type { Permit } from "@/lib/types";

// better-sqlite3 is a native addon -- requires the Node.js runtime, not edge.
export const runtime = "nodejs";
// Always read the current state of permits.db; never cache this response.
export const dynamic = "force-dynamic";

// Loads the whole table in one shot and lets the client filter in memory --
// same approach as the Streamlit predecessor (pandas dataframe loaded once,
// filtered with boolean masks). The permits table is a few hundred rows;
// this is simpler than building a query-param-driven filtered endpoint and
// keeps client-side filtering instant with no round-trip per filter change.
export async function GET() {
  try {
    const db = getDb();
    const rows = db.prepare("SELECT * FROM permits").all() as Permit[];
    return NextResponse.json({ permits: rows });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("Failed to read permits:", message);
    return NextResponse.json(
      { permits: [], error: message },
      { status: 500 }
    );
  }
}
