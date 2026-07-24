"use client";

import MetricsRow from "@/components/MetricsRow";
import { usePermits } from "@/lib/usePermits";
import { REGISTERED_JURISDICTIONS } from "@/lib/jurisdictions";

// Overview is a pure at-a-glance summary -- unfiltered, no Filters
// sidebar, no charts, no permit-level table. Just the headline numbers;
// every chart lives on /trends and every other kind of drill-down lives
// on /table or /map, so there's exactly one place each thing shows up.
export default function OverviewPage() {
  const { permits, error, refresh } = usePermits();
  const allPermits = permits ?? [];

  return (
    <div className="min-h-screen p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">📊 Overview</h1>
        <button
          type="button"
          onClick={refresh}
          className="rounded-lg bg-[var(--accent)] text-black font-medium px-3 py-1.5 text-sm hover:brightness-95 transition-[filter]"
        >
          🔄 Refresh data
        </button>
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
        <div className="space-y-3">
          <MetricsRow permits={allPermits} />
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Unfiltered, all jurisdictions — charts live on Trends, drill down on Table or Map.
          </p>
        </div>
      )}
    </div>
  );
}
