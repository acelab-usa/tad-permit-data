import Link from "next/link";
import type { Permit } from "@/lib/types";

const LIMIT = 8;

function formatValuation(value: number | null): string {
  return value === null ? "—" : `$${value.toLocaleString("en-US")}`;
}

// A compact teaser for the Overview page -- individual records, not
// aggregates, so it doesn't overlap with Trends' charts at all. The full
// sortable/filterable table lives on /table.
export default function RecentPermitsList({ permits }: { permits: Permit[] }) {
  const recent = [...permits]
    .filter((p) => p.filing_date)
    .sort((a, b) => b.filing_date!.localeCompare(a.filing_date!))
    .slice(0, LIMIT);

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Recent permits</h3>
        <Link href="/table" className="text-xs text-[var(--accent)] hover:underline">
          View all in Table →
        </Link>
      </div>

      {recent.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">No dated permits match the current filters.</p>
      ) : (
        <div className="overflow-x-auto -mx-4">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                <th className="px-4 py-1.5">Permit ID</th>
                <th className="px-4 py-1.5">Jurisdiction</th>
                <th className="px-4 py-1.5">Filed</th>
                <th className="px-4 py-1.5">Type</th>
                <th className="px-4 py-1.5">Address</th>
                <th className="px-4 py-1.5 text-right">Valuation</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((permit) => (
                <tr key={permit.id} className="border-t border-gray-100 dark:border-gray-800">
                  <td className="px-4 py-1.5 text-gray-800 dark:text-gray-100 whitespace-nowrap">
                    {permit.permit_id}
                  </td>
                  <td className="px-4 py-1.5 text-gray-800 dark:text-gray-100 whitespace-nowrap">
                    {permit.jurisdiction}
                  </td>
                  <td className="px-4 py-1.5 text-gray-800 dark:text-gray-100 whitespace-nowrap">
                    {permit.filing_date?.slice(0, 10)}
                  </td>
                  <td className="px-4 py-1.5 text-gray-800 dark:text-gray-100 whitespace-nowrap">
                    {permit.permit_type_normalized ?? "—"}
                  </td>
                  <td className="px-4 py-1.5 text-gray-800 dark:text-gray-100 max-w-[16rem] truncate" title={permit.address ?? undefined}>
                    {permit.address || "—"}
                  </td>
                  <td className="px-4 py-1.5 text-right tabular-nums text-gray-800 dark:text-gray-100 whitespace-nowrap">
                    {formatValuation(permit.valuation)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
