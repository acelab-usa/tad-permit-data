"use client";

import { useState } from "react";
import Filters from "@/components/Filters";
import MetricsRow from "@/components/MetricsRow";
import PermitsTable from "@/components/PermitsTable";
import PermitDetail from "@/components/PermitDetail";
import { usePermits } from "@/lib/usePermits";
import { REGISTERED_JURISDICTIONS } from "@/lib/jurisdictions";
import { downloadCsv, toCsv } from "@/lib/csv";
import { PERMIT_CSV_COLUMNS, type Permit } from "@/lib/types";

function exportFilename(): string {
  return `permits-export-${new Date().toISOString().slice(0, 10)}.csv`;
}

export default function TablePage() {
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

  return (
    <div className="min-h-screen p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          🏗️ Permit Lookup
        </h1>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => downloadCsv(exportFilename(), toCsv(filtered, PERMIT_CSV_COLUMNS))}
            disabled={filtered.length === 0}
            className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ⬇️ Export CSV
          </button>
          <button
            type="button"
            onClick={refresh}
            className="rounded-lg bg-[var(--accent)] text-black font-medium px-3 py-1.5 text-sm hover:brightness-95 transition-[filter]"
          >
            🔄 Refresh data
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-300 bg-red-50 dark:bg-red-950 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300">
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
