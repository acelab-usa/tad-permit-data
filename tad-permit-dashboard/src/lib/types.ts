// Mirrors the `permits` table schema (see tad-permit-pipeline/database.py).
// This app is read-only, so these are the row shapes as SQLite returns
// them -- no validation/parsing beyond what's needed for filtering/display.
export interface Permit {
  id: number;
  permit_id: string;
  jurisdiction: string;
  source_url: string | null;
  source_format: string;
  extracted_at: string;
  filing_date: string | null;
  permit_type_raw: string | null;
  permit_type_normalized: string | null;
  address: string | null;
  owner_name: string | null;
  contractor_name: string | null;
  valuation: number | null;
  square_footage: number | null;
  raw_scope_of_work: string | null;
  scope_summary: string | null;
  building_systems: string | null; // JSON-encoded string[], parse with parseBuildingSystems()
}

export function parseBuildingSystems(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
