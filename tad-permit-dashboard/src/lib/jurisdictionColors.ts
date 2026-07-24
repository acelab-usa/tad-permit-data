// Deterministic color-by-jurisdiction assignment, not a hardcoded
// name-to-color map -- a jurisdiction gets a color by its position in the
// sorted list of jurisdictions actually present, so a newly-registered
// adapter just gets the next color in the palette automatically.
// Vivid "400"-tier hues rather than the more common "500/600" tier --
// lighter/more saturated shades read with much better contrast against a
// near-black map/card surface. Deliberately avoids green: that hue is
// reserved for the brand accent (selection state, CTAs), so a jurisdiction
// dot never gets confused for "this one is selected."
const PALETTE = [
  "#38bdf8", // sky
  "#fb7185", // rose
  "#fbbf24", // amber
  "#a78bfa", // violet
  "#2dd4bf", // teal
  "#f472b6", // pink
  "#fb923c", // orange
  "#818cf8", // indigo
];

export function colorForJurisdiction(jurisdiction: string, allJurisdictions: string[]): string {
  const sorted = [...allJurisdictions].sort();
  const index = sorted.indexOf(jurisdiction);
  return PALETTE[index === -1 ? 0 : index % PALETTE.length];
}

export { PALETTE };
