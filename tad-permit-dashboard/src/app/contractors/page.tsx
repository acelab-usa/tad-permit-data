"use client";

import Link from "next/link";
import Filters from "@/components/Filters";
import { usePermits } from "@/lib/usePermits";
import { REGISTERED_JURISDICTIONS } from "@/lib/jurisdictions";
import { formatCompactCurrency, summarizeContractors } from "@/lib/trends";

export default function ContractorsPage() {
  const { permits, error, filters, setFilters, jurisdictionOptions, permitTypeOptions, valuationBounds, filtered, refresh } =
    usePermits();

  const contractors = summarizeContractors(filtered);

  return (
    <div className="min-h-screen p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">🧰 Contractors</h1>
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
        filters && (
          <div className="flex flex-col lg:flex-row gap-6">
            <Filters
              jurisdictionOptions={jurisdictionOptions}
              permitTypeOptions={permitTypeOptions}
              valuationBounds={valuationBounds}
              filters={filters}
              onChange={setFilters}
            />

            <main className="flex-1 min-w-0">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                {contractors.length.toLocaleString("en-US")} contractor{contractors.length === 1 ? "" : "s"} in the
                current filter selection. Use the search box in Filters to narrow by name.
              </p>

              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm overflow-hidden">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-100 dark:bg-gray-800">
                    <tr>
                      <th className="text-left font-medium text-gray-600 dark:text-gray-300 px-4 py-2.5">
                        Contractor
                      </th>
                      <th className="text-right font-medium text-gray-600 dark:text-gray-300 px-4 py-2.5">
                        Permits
                      </th>
                      <th className="text-right font-medium text-gray-600 dark:text-gray-300 px-4 py-2.5">
                        Total valuation
                      </th>
                      <th className="text-left font-medium text-gray-600 dark:text-gray-300 px-4 py-2.5">
                        Jurisdictions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {contractors.map((c, i) => (
                      <tr
                        key={c.name}
                        className={`border-t border-gray-100 dark:border-gray-800 ${
                          i % 2 === 1 ? "bg-gray-50/60 dark:bg-gray-800/20" : ""
                        }`}
                      >
                        <td className="px-4 py-2 text-gray-800 dark:text-gray-100">
                          <Link
                            href={`/contractors/${encodeURIComponent(c.name)}`}
                            className="text-[var(--accent)] hover:underline"
                          >
                            {c.name}
                          </Link>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-gray-800 dark:text-gray-100">
                          {c.permitCount.toLocaleString("en-US")}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-gray-800 dark:text-gray-100">
                          {formatCompactCurrency(c.totalValuation)}
                        </td>
                        <td className="px-4 py-2 text-gray-600 dark:text-gray-400">
                          {c.jurisdictions.join(", ")}
                        </td>
                      </tr>
                    ))}
                    {contractors.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-4 py-6 text-center text-gray-400">
                          No contractors match the current filters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </main>
          </div>
        )
      )}
    </div>
  );
}
