"use client";

import { useEffect, useMemo, useState } from "react";
import Filters from "@/components/Filters";
import MetricsRow from "@/components/MetricsRow";
import PermitsTable from "@/components/PermitsTable";
import PermitDetail from "@/components/PermitDetail";
import { applyFilters, type FiltersState } from "@/lib/filters";
import { REGISTERED_JURISDICTIONS } from "@/lib/jurisdictions";
import { PERMIT_TYPE_TAXONOMY } from "@/lib/permit-types";
import type { Permit } from "@/lib/types";

function optionsFor(permits: Permit[]) {
  const jurisdictions = Array.from(
    new Set<string>([...REGISTERED_JURISDICTIONS, ...permits.map((p) => p.jurisdiction)])
  ).sort();
  const permitTypes = Array.from(
    new Set<string>([
      ...PERMIT_TYPE_TAXONOMY,
      ...permits.map((p) => p.permit_type_normalized).filter((t): t is string => t !== null),
    ])
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

export default function Home() {
  const [permits, setPermits] = useState<Permit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Permit | null>(null);
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

  // Union the *registered* jurisdictions/permit-type taxonomy with whatever's
  // actually in the data, so a jurisdiction/type with an adapter but no
  // ingested rows yet still shows up as a selectable filter with zero
  // results, instead of silently disappearing.
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

  return (
    <div className="min-h-screen p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          🏗️ Permit Lookup
        </h1>
        <button
          type="button"
          onClick={() => setRefreshKey((k) => k + 1)}
          className="rounded border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
        >
          🔄 Refresh data
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 dark:bg-red-950 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300">
          Failed to load permits: {error}
        </div>
      )}

      {permits === null ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : permits.length === 0 && !error ? (
        <p className="text-sm text-gray-500">
          No permits found in the database yet. Registered jurisdictions:{" "}
          {REGISTERED_JURISDICTIONS.join(", ")}. Run{" "}
          <code className="text-xs bg-gray-100 dark:bg-gray-800 rounded px-1">
            uv run python dataloader.py &lt;jurisdiction&gt;
          </code>{" "}
          in tad-permit-pipeline, then refresh.
        </p>
      ) : (
        filters && (
          <div className="flex flex-col lg:flex-row gap-6">
            <Filters
              jurisdictionOptions={jurisdictionOptions}
              permitTypeOptions={permitTypeOptions}
              valuationBounds={valuationBounds}
              filters={filters}
              onChange={setFilters}
            />

            <main className="flex-1 min-w-0 space-y-6">
              <MetricsRow permits={filtered} />
              <PermitsTable
                permits={filtered}
                selectedId={selected?.id ?? null}
                onSelect={setSelected}
              />
              <section>
                <h2 className="text-lg font-semibold mb-2 text-gray-900 dark:text-gray-100">
                  Permit detail
                </h2>
                <PermitDetail permit={selected} />
              </section>
            </main>
          </div>
        )
      )}
    </div>
  );
}
