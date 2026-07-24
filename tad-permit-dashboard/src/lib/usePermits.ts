"use client";

import { useEffect, useMemo, useState } from "react";
import { applyFilters, type FiltersState } from "./filters";
import type { Permit } from "./types";

// Options come only from what's actually in the data -- a registered
// jurisdiction/type with an adapter but zero ingested rows won't show up
// as a filter until it has at least one permit. (Previously unioned in the
// full registered set so unpopulated ones showed as empty-result filters,
// but that read as "these options don't exist" rather than "no data yet.")
export function optionsFor(permits: Permit[]) {
  const jurisdictions = Array.from(new Set(permits.map((p) => p.jurisdiction))).sort();
  const permitTypes = Array.from(
    new Set(permits.map((p) => p.permit_type_normalized).filter((t): t is string => t !== null))
  ).sort();
  return { jurisdictions, permitTypes };
}

function defaultFilters(jurisdictions: string[], permitTypes: string[]): FiltersState {
  return {
    jurisdictions: new Set(jurisdictions),
    permitTypes: new Set(permitTypes),
    searchText: "",
    dateFrom: "",
    dateTo: "",
    valuationMin: null,
    valuationMax: null,
  };
}

/**
 * Shared data/filter state for both the table view and the map view --
 * fetches /api/permits once, derives filter options, and applies the
 * active filters. Both pages get the same data and the same filtering
 * semantics for free.
 */
export function usePermits() {
  const [permits, setPermits] = useState<Permit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FiltersState | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setPermits(null);
      setError(null);
      setFilters(null);

      try {
        const res = await fetch("/api/permits");
        const data: { permits: Permit[]; error?: string } = await res.json();
        if (cancelled) return;

        if (data.error) {
          setError(data.error);
          setPermits([]);
          return;
        }

        const { jurisdictions, permitTypes } = optionsFor(data.permits);
        setPermits(data.permits);
        setFilters(defaultFilters(jurisdictions, permitTypes));
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setPermits([]);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const { jurisdictions: jurisdictionOptions, permitTypes: permitTypeOptions } = useMemo(
    () => optionsFor(permits ?? []),
    [permits]
  );

  const valuationBounds = useMemo(() => {
    const values = (permits ?? [])
      .map((p) => p.valuation)
      .filter((v): v is number => v !== null);
    if (values.length === 0) return null;
    return { min: Math.min(...values), max: Math.max(...values) };
  }, [permits]);

  const filtered = useMemo(() => {
    if (!permits || !filters) return [];
    return applyFilters(permits, filters);
  }, [permits, filters]);

  return {
    permits,
    error,
    filters,
    setFilters,
    jurisdictionOptions,
    permitTypeOptions,
    valuationBounds,
    filtered,
    refresh: () => setRefreshKey((k) => k + 1),
  };
}
