import type { Permit } from "./types";

export interface FiltersState {
  jurisdictions: Set<string>;
  permitTypes: Set<string>;
  searchText: string;
  dateFrom: string; // "YYYY-MM-DD" or ""
  dateTo: string;
  valuationMin: number | null;
  valuationMax: number | null;
}

const SEARCH_FIELDS: (keyof Permit)[] = [
  "address",
  "owner_name",
  "contractor_name",
  "permit_id",
];

// Mirrors dashboard.py's filtering exactly: a permit with a missing
// permit_type_normalized/filing_date/valuation still passes the
// jurisdiction/type/date/valuation filters rather than being silently
// excluded -- only an active search term excludes on missing fields.
export function applyFilters(permits: Permit[], filters: FiltersState): Permit[] {
  const needle = filters.searchText.trim().toLowerCase();

  return permits.filter((p) => {
    if (filters.jurisdictions.size > 0 && !filters.jurisdictions.has(p.jurisdiction)) {
      return false;
    }

    if (
      filters.permitTypes.size > 0 &&
      p.permit_type_normalized !== null &&
      !filters.permitTypes.has(p.permit_type_normalized)
    ) {
      return false;
    }

    if (needle) {
      const matches = SEARCH_FIELDS.some((field) =>
        String(p[field] ?? "").toLowerCase().includes(needle)
      );
      if (!matches) return false;
    }

    if ((filters.dateFrom || filters.dateTo) && p.filing_date) {
      const filingDate = p.filing_date.slice(0, 10);
      if (filters.dateFrom && filingDate < filters.dateFrom) return false;
      if (filters.dateTo && filingDate > filters.dateTo) return false;
    }

    if (p.valuation !== null) {
      if (filters.valuationMin !== null && p.valuation < filters.valuationMin) return false;
      if (filters.valuationMax !== null && p.valuation > filters.valuationMax) return false;
    }

    return true;
  });
}
