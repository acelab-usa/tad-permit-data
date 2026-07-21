// Deterministic color-by-jurisdiction assignment, not a hardcoded
// name-to-color map -- a jurisdiction gets a color by its position in the
// sorted list of jurisdictions actually present, so a newly-registered
// adapter just gets the next color in the palette automatically.
const PALETTE = [
  "#2563eb", // blue
  "#dc2626", // red
  "#16a34a", // green
  "#d97706", // amber
  "#7c3aed", // violet
  "#0891b2", // cyan
  "#db2777", // pink
  "#65a30d", // lime
];

export function colorForJurisdiction(jurisdiction: string, allJurisdictions: string[]): string {
  const sorted = [...allJurisdictions].sort();
  const index = sorted.indexOf(jurisdiction);
  return PALETTE[index === -1 ? 0 : index % PALETTE.length];
}

export { PALETTE };
