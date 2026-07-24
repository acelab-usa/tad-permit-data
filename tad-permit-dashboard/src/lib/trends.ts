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

// Counts permits per jurisdiction, descending -- a distinct metric from
// valuationByJurisdiction (count of permits, not sum of $), used for the
// Overview page's "top jurisdiction" highlight so it isn't just a
// single-row restatement of that chart.
export function countByJurisdiction(permits: Permit[]): DataPoint[] {
  const counts = new Map<string, number>();

  for (const p of permits) {
    counts.set(p.jurisdiction, (counts.get(p.jurisdiction) ?? 0) + 1);
  }

  return Array.from(counts.entries())
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

export interface ContractorSummary {
  name: string;
  permitCount: number;
  totalValuation: number;
  jurisdictions: string[]; // distinct, sorted
}

// Full contractor directory, descending by permit count -- the aggregation
// both the Top Contractors chart and the /contractors directory page draw
// from, so there's one place that decides what "counts" as a contractor
// (a non-empty, trimmed contractor_name).
export function summarizeContractors(permits: Permit[]): ContractorSummary[] {
  const byName = new Map<string, { count: number; valuation: number; jurisdictions: Set<string> }>();

  for (const p of permits) {
    const name = p.contractor_name?.trim();
    if (!name) continue;
    const entry = byName.get(name) ?? { count: 0, valuation: 0, jurisdictions: new Set<string>() };
    entry.count += 1;
    if (p.valuation !== null) entry.valuation += p.valuation;
    entry.jurisdictions.add(p.jurisdiction);
    byName.set(name, entry);
  }

  return Array.from(byName.entries())
    .map(([name, e]) => ({
      name,
      permitCount: e.count,
      totalValuation: e.valuation,
      jurisdictions: Array.from(e.jurisdictions).sort(),
    }))
    .sort((a, b) => b.permitCount - a.permitCount);
}

// Top contractors by permit count -- a leaderboard, not a full breakdown,
// so unlike countByPermitType there's no "Unspecified" bucket or full
// tail: permits with no contractor_name are simply not a contractor to
// rank, and only the top `limit` are returned.
export function topContractors(permits: Permit[], limit = 8): DataPoint[] {
  return summarizeContractors(permits)
    .slice(0, limit)
    .map((c) => ({ label: c.name, value: c.permitCount }));
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
