"use client";

import Filters from "@/components/Filters";
import NavTabs from "@/components/NavTabs";
import ChartCard from "@/components/charts/ChartCard";
import TrendLineChart from "@/components/charts/TrendLineChart";
import HorizontalBarChart from "@/components/charts/HorizontalBarChart";
import { usePermits } from "@/lib/usePermits";
import { REGISTERED_JURISDICTIONS } from "@/lib/jurisdictions";
import {
  countByPermitType,
  formatCompactCurrency,
  permitsByMonth,
  valuationByJurisdiction,
} from "@/lib/trends";

export default function TrendsPage() {
  const { permits, error, filters, setFilters, jurisdictionOptions, permitTypeOptions, valuationBounds, filtered, refresh } =
    usePermits();

  const monthly = permitsByMonth(filtered);
  const byJurisdiction = valuationByJurisdiction(filtered);
  const byType = countByPermitType(filtered);

  return (
    <div className="min-h-screen p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">📈 Permit Trends</h1>
        <button
          type="button"
          onClick={refresh}
          className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          🔄 Refresh data
        </button>
      </div>

      <div className="mb-6">
        <NavTabs />
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
              <ChartCard
                title="Permits filed over time"
                subtitle="Monthly count across the current filter selection"
                tableColumns={["Month", "Permits"]}
                tableRows={monthly.map((d) => ({ label: d.label, value: d.value.toLocaleString("en-US") }))}
              >
                <TrendLineChart data={monthly} />
              </ChartCard>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <ChartCard
                  title="Valuation by jurisdiction"
                  subtitle="Sum of reported project valuation"
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
                  subtitle="Count by normalized permit type"
                  tableColumns={["Permit type", "Count"]}
                  tableRows={byType.map((d) => ({ label: d.label, value: d.value.toLocaleString("en-US") }))}
                >
                  <HorizontalBarChart
                    data={byType}
                    valueFormat={(v) => v.toLocaleString("en-US")}
                    ariaLabel="Permit count by normalized type"
                  />
                </ChartCard>
              </div>
            </main>
          </div>
        )
      )}
    </div>
  );
}
