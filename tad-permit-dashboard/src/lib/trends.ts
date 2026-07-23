import type { Permit } from "./types";

export interface DataPoint {
  label: string;
  value: number;
}

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

// Buckets by calendar month (YYYY-MM) and returns points in chronological
// order. Permits with no filing_date are excluded -- there's no time axis
// position for them.
export function permitsByMonth(permits: Permit[]): DataPoint[] {
  const counts = new Map<string, number>();

  for (const p of permits) {
    if (!p.filing_date) continue;
    const key = p.filing_date.slice(0, 7); // "YYYY-MM"
    if (key.length !== 7) continue;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  return Array.from(counts.keys())
    .sort()
    .map((key) => {
      const [year, month] = key.split("-");
      const monthIndex = Number(month) - 1;
      const label = `${MONTH_LABELS[monthIndex] ?? month} ${year}`;
      return { label, value: counts.get(key)! };
    });
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

export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatCompactCurrency(value: number): string {
  return `$${formatCompactNumber(value)}`;
}
