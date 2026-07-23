import type { Permit } from "./types";

export interface DataPoint {
  label: string;
  value: number;
}

// Sums valuation per jurisdiction, descending -- a permit missing
// valuation contributes to the count elsewhere but not to this sum.
export function valuationByJurisdiction(permits: Permit[]): DataPoint[] {
  const totals = new Map<string, number>();

  for (const p of permits) {
    if (p.valuation === null) continue;
    totals.set(p.jurisdiction, (totals.get(p.jurisdiction) ?? 0) + p.valuation);
  }

  return Array.from(totals.entries())
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
}

// Counts permits per normalized type, descending. A permit with no
// normalized type is bucketed as "Unspecified" rather than dropped.
export function countByPermitType(permits: Permit[]): DataPoint[] {
  const counts = new Map<string, number>();

  for (const p of permits) {
    const key = p.permit_type_normalized ?? "Unspecified";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  return Array.from(counts.entries())
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
}

// Top contractors by permit count -- a leaderboard, not a full breakdown,
// so unlike countByPermitType there's no "Unspecified" bucket or full
// tail: permits with no contractor_name are simply not a contractor to
// rank, and only the top `limit` are returned.
export function topContractors(permits: Permit[], limit = 8): DataPoint[] {
  const counts = new Map<string, number>();

  for (const p of permits) {
    const name = p.contractor_name?.trim();
    if (!name) continue;
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }

  return Array.from(counts.entries())
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit);
}

export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatCompactCurrency(value: number): string {
  return `$${formatCompactNumber(value)}`;
}
