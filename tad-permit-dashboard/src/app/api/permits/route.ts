import { NextResponse } from "next/server";
import { withDb } from "@/lib/db";
import type { Permit } from "@/lib/types";

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
    const rows = await withDb((db) => {
      const stmt = db.prepare("SELECT * FROM permits");
      const results: Permit[] = [];
      while (stmt.step()) {
        results.push(stmt.getAsObject() as unknown as Permit);
      }
      stmt.free();
      return results;
    });
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
