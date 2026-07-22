"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import Filters from "@/components/Filters";
import NavTabs from "@/components/NavTabs";
import PermitDetail from "@/components/PermitDetail";
import { usePermits } from "@/lib/usePermits";
import { REGISTERED_JURISDICTIONS } from "@/lib/jurisdictions";
import type { Permit } from "@/lib/types";

// Leaflet touches `window` at module-eval time -- must never run during SSR.
const PermitsMap = dynamic(() => import("@/components/PermitsMap"), {
  ssr: false,
  loading: () => (
    <div className="h-[32rem] w-full rounded-lg border border-gray-200 dark:border-gray-700 flex items-center justify-center text-sm text-gray-400">
      Loading map…
    </div>
  ),
});

export default function MapPage() {
  const {
    permits,
    error,
    filters,
    setFilters,
    jurisdictionOptions,
    permitTypeOptions,
    valuationBounds,
    filtered,
    refresh,
  } = usePermits();
  const [selected, setSelected] = useState<Permit | null>(null);

  const mappable = filtered.filter((p) => p.latitude !== null && p.longitude !== null);
  const unmapped = filtered.length - mappable.length;

  return (
    <div className="min-h-screen p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          🗺️ Permit Map
        </h1>
        <button
          type="button"
          onClick={refresh}
          className="rounded border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
        >
          🔄 Refresh data
        </button>
      </div>

      <div className="mb-6">
        <NavTabs />
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

            <main className="flex-1 min-w-0 space-y-4">
              <p className="text-sm text-gray-500">
                Showing {mappable.length.toLocaleString("en-US")} of{" "}
                {filtered.length.toLocaleString("en-US")} matched permits on the map
                {unmapped > 0 &&
                  ` (${unmapped.toLocaleString("en-US")} have no location data yet)`}
                .
              </p>

              {mappable.length === 0 ? (
                <div className="h-[32rem] w-full rounded-lg border border-gray-200 dark:border-gray-700 flex items-center justify-center text-sm text-gray-400 text-center px-8">
                  None of the currently matched permits have coordinates yet.
                  Coordinates are captured going forward from the
                  Chicago/NYC/Austin APIs directly, or geocoded from address
                  for Allen (PDF ledger) permits and any API record missing
                  one -- re-run ingestion to backfill older rows, or adjust
                  filters. A geocode can still fail for a bad/ambiguous
                  address.
                </div>
              ) : (
                <PermitsMap
                  permits={mappable}
                  jurisdictions={jurisdictionOptions}
                  selectedId={selected?.id ?? null}
                  onSelect={setSelected}
                />
              )}

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
