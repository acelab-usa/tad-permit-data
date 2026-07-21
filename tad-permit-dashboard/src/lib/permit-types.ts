// Mirrors the fixed taxonomy in tad-permit-pipeline/permit_types.py
// (PERMIT_TYPE_TAXONOMY). That module is the actual source of truth --
// this file exists only because this app can't import Python code, so if
// the taxonomy there ever changes, update this list to match.
export const PERMIT_TYPE_TAXONOMY = [
  "New Construction",
  "Alteration",
  "Demolition",
  "Electrical",
  "Plumbing",
  "Mechanical",
  "Roofing",
  "Certificate of Occupancy",
  "Sign",
  "Fire/Life Safety",
  "Other",
] as const;
