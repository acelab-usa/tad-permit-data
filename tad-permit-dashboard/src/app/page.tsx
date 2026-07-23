"use client";

import MetricsRow from "@/components/MetricsRow";
import ChartCard from "@/components/charts/ChartCard";
import HorizontalBarChart from "@/components/charts/HorizontalBarChart";
import { usePermits } from "@/lib/usePermits";
import { REGISTERED_JURISDICTIONS } from "@/lib/jurisdictions";
import {
  countByPermitType,
  formatCompactCurrency,
  topContractors,
  valuationByJurisdiction,
} from "@/lib/trends";

// Overview is a pure at-a-glance summary -- unfiltered, no Filters sidebar,
// no permit-level table. Slicing the data is what /table, /map, and
// /trends are for; this page just answers "what's the state of things."
export default function OverviewPage() {
  const { permits, error, refresh } = usePermits();
  const allPermits = permits ?? [];

  const byJurisdiction = valuationByJurisdiction(allPermits);
  const byType = countByPermitType(allPermits);
  const byContractor = topContractors(allPermits, 5);

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
        <div className="space-y-6">
          <MetricsRow permits={allPermits} />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <ChartCard
              title="Valuation by jurisdiction"
              tableColumns={["Jurisdiction", "Total valuation"]}
              tableRows={byJurisdiction.map((d) => ({ label: d.label, value: formatCompactCurrency(d.value) }))}
            >
              <HorizontalBarChart
                data={byJurisdiction}
                valueFormat={formatCompactCurrency}
                ariaLabel="Total permit valuation by jurisdiction"
              />
            </ChartCard>

            <ChartCard
              title="Permit type distribution"
              tableColumns={["Permit type", "Count"]}
              tableRows={byType.map((d) => ({ label: d.label, value: d.value.toLocaleString("en-US") }))}
            >
              <HorizontalBarChart
                data={byType.slice(0, 6)}
                valueFormat={(v) => v.toLocaleString("en-US")}
                ariaLabel="Permit count by normalized type"
              />
            </ChartCard>

            <ChartCard
              title="Top contractors"
              tableColumns={["Contractor", "Permits"]}
              tableRows={byContractor.map((d) => ({ label: d.label, value: d.value.toLocaleString("en-US") }))}
            >
              <HorizontalBarChart
                data={byContractor}
                valueFormat={(v) => v.toLocaleString("en-US")}
                ariaLabel="Permit count by contractor"
              />
            </ChartCard>
          </div>

          <p className="text-xs text-gray-500 dark:text-gray-400">
            Unfiltered, all jurisdictions — filter and drill down on Table, Map, or Trends.
          </p>
        </div>
      )}
    </div>
  );
}
