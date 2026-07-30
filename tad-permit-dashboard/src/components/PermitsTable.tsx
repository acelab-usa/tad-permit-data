import { useEffect, useRef, useState } from "react";
import type { Permit } from "@/lib/types";

interface PermitsTableProps {
  permits: Permit[];
  selectedId: number | null;
  onSelect: (permit: Permit) => void;
}

const PAGE_SIZE = 50;

const COLUMNS: { key: keyof Permit; label: string }[] = [
  { key: "permit_id", label: "Permit ID" },
  { key: "jurisdiction", label: "Jurisdiction" },
  { key: "filing_date", label: "Filing date" },
  { key: "permit_type_normalized", label: "Type" },
  { key: "address", label: "Address" },
  { key: "owner_name", label: "Owner" },
  { key: "contractor_name", label: "Contractor" },
  { key: "valuation", label: "Valuation" },
  { key: "square_footage", label: "Sq Ft" },
  { key: "scope_summary", label: "Scope summary" },
];

function formatCell(permit: Permit, key: keyof Permit): string {
  const value = permit[key];
  if (value === null || value === undefined || value === "") return "—";
  if (key === "valuation") return `$${Number(value).toLocaleString("en-US")}`;
  if (key === "square_footage") return Number(value).toLocaleString("en-US");
  if (key === "filing_date") return String(value).slice(0, 10);
  return String(value);
}

export default function PermitsTable({ permits, selectedId, onSelect }: PermitsTableProps) {
  // Sorted newest-first, nulls last -- same default ordering as the
  // Streamlit predecessor.
  const sorted = [...permits].sort((a, b) => {
    if (!a.filing_date && !b.filing_date) return 0;
    if (!a.filing_date) return 1;
    if (!b.filing_date) return -1;
    return b.filing_date.localeCompare(a.filing_date);
  });

  // Rendering every matching row at once got slow once the dataset grew
  // past a few thousand permits -- a large DOM table is what actually
  // drags on scroll/paint, independent of how fast the data arrived.
  // Paginate the rendered rows instead of virtualizing; reset to page 1
  // whenever the (already-filtered) permits list changes underneath us
  // (tracked during render, React's supported pattern for this, rather
  // than an effect) so a stale page number doesn't strand the view past
  // the new end.
  const [page, setPage] = useState(1);
  const [prevPermits, setPrevPermits] = useState(permits);
  if (permits !== prevPermits) {
    setPrevPermits(permits);
    setPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const start = (currentPage - 1) * PAGE_SIZE;
  const pageRows = sorted.slice(start, start + PAGE_SIZE);

  // The row list scrolls independently of the page -- switching pages
  // without resetting this would leave whatever scrollTop the previous
  // page ended at, so a Next click while scrolled down lands partway
  // into the new page's rows instead of at its top.
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 });
  }, [currentPage]);

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm">
      <div ref={scrollRef} className="max-h-[32rem] overflow-y-auto overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-100 dark:bg-gray-800 sticky top-0 z-10">
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className="text-left font-medium text-gray-600 dark:text-gray-300 px-3 py-2.5 whitespace-nowrap"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((permit, i) => (
              <tr
                key={permit.id}
                onClick={() => onSelect(permit)}
                className={`cursor-pointer border-t border-gray-100 dark:border-gray-800 hover:bg-[var(--accent-wash)] transition-colors ${
                  selectedId === permit.id
                    ? "bg-[var(--accent-wash)]"
                    : i % 2 === 1
                      ? "bg-gray-50/60 dark:bg-gray-800/20"
                      : ""
                }`}
              >
                {COLUMNS.map((col) => (
                  <td
                    key={col.key}
                    className="px-3 py-2 text-gray-800 dark:text-gray-100 max-w-xs truncate"
                    title={formatCell(permit, col.key)}
                  >
                    {formatCell(permit, col.key)}
                  </td>
                ))}
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length} className="px-3 py-6 text-center text-gray-400">
                  No permits match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {sorted.length > 0 && (
        <div className="flex items-center justify-between gap-3 border-t border-gray-100 dark:border-gray-800 px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
          <span>
            Showing {(start + 1).toLocaleString("en-US")}–{Math.min(start + PAGE_SIZE, sorted.length).toLocaleString("en-US")} of{" "}
            {sorted.length.toLocaleString("en-US")}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage(currentPage - 1)}
              disabled={currentPage <= 1}
              className="rounded-md border border-gray-300 dark:border-gray-700 px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Prev
            </button>
            <span className="tabular-nums">
              Page {currentPage} of {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="rounded-md border border-gray-300 dark:border-gray-700 px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
