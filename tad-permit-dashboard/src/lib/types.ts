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
  latitude: number | null;
  longitude: number | null;
  raw_scope_of_work: string | null;
  scope_summary: string | null;
  building_systems: string | null; // JSON-encoded string[], parse with parseBuildingSystems()
}

// Column set for CSV export -- the full record, not just the columns the
// table UI happens to show, since a CSV is meant for further analysis
// elsewhere. Shared between the Table page (full filtered export) and a
// contractor's detail page (export scoped to just their permits).
export const PERMIT_CSV_COLUMNS: { key: keyof Permit; label: string }[] = [
  { key: "permit_id", label: "Permit ID" },
  { key: "jurisdiction", label: "Jurisdiction" },
  { key: "filing_date", label: "Filing date" },
  { key: "permit_type_normalized", label: "Type (normalized)" },
  { key: "permit_type_raw", label: "Type (raw)" },
  { key: "address", label: "Address" },
  { key: "owner_name", label: "Owner" },
  { key: "contractor_name", label: "Contractor" },
  { key: "valuation", label: "Valuation" },
  { key: "square_footage", label: "Square footage" },
  { key: "latitude", label: "Latitude" },
  { key: "longitude", label: "Longitude" },
  { key: "scope_summary", label: "Scope summary" },
  { key: "source_format", label: "Source format" },
  { key: "source_url", label: "Source URL" },
  { key: "extracted_at", label: "Extracted at" },
];

export function parseBuildingSystems(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
