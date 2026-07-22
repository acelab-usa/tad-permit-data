// Mirrors the registered adapters in tad-permit-pipeline/sources/registry.py
// (SOURCES / list_sources()). That registry is the actual source of truth
// for "which jurisdictions this pipeline knows how to ingest" -- this app
// can't import Python code, so if a new adapter is registered there, add it
// here too so it shows up in the filter even before it has any ingested
// rows (matching the "registry-driven, not data-driven" fix made in
// dashboard.py's Streamlit predecessor).
export const REGISTERED_JURISDICTIONS = ["allen", "austin", "chicago", "la", "naperville", "nyc", "seattle"] as const;
