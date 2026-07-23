"use client";

import { useId, useState } from "react";

interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  tableColumns: [string, string];
  tableRows: { label: string; value: string }[];
}

// Shared card chrome for every trends chart: title, the chart itself, and
// a table-view twin behind a disclosure toggle -- every chart's data stays
// reachable without relying on hover/color (dataviz skill's accessibility
// pass requirement).
export default function ChartCard({ title, subtitle, children, tableColumns, tableRows }: ChartCardProps) {
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm p-4">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
          {subtitle && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{subtitle}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          aria-expanded={showTable}
          aria-controls={tableId}
          className="shrink-0 text-xs text-[var(--accent)] hover:underline"
        >
          {showTable ? "Hide table" : "View as table"}
        </button>
      </div>

      {children}

      {showTable && (
        <div id={tableId} className="mt-3 max-h-56 overflow-y-auto rounded-lg border border-gray-100 dark:border-gray-800">
          <table className="min-w-full text-xs">
            <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
              <tr>
                <th className="text-left font-medium text-gray-600 dark:text-gray-300 px-3 py-1.5">
                  {tableColumns[0]}
                </th>
                <th className="text-right font-medium text-gray-600 dark:text-gray-300 px-3 py-1.5">
                  {tableColumns[1]}
                </th>
              </tr>
            </thead>
            <tbody>
              {tableRows.map((row) => (
                <tr key={row.label} className="border-t border-gray-100 dark:border-gray-800">
                  <td className="px-3 py-1.5 text-gray-800 dark:text-gray-100">{row.label}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-gray-800 dark:text-gray-100">
                    {row.value}
                  </td>
                </tr>
              ))}
              {tableRows.length === 0 && (
                <tr>
                  <td colSpan={2} className="px-3 py-4 text-center text-gray-400">
                    No data for the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
