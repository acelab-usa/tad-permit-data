import type { Permit } from "@/lib/types";

interface PermitsTableProps {
  permits: Permit[];
  selectedId: number | null;
  onSelect: (permit: Permit) => void;
}

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

  return (
    <div className="max-h-[32rem] overflow-y-auto overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0 z-10">
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className="text-left font-medium text-gray-600 dark:text-gray-300 px-3 py-2 whitespace-nowrap"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((permit) => (
            <tr
              key={permit.id}
              onClick={() => onSelect(permit)}
              className={`cursor-pointer border-t border-gray-100 dark:border-gray-800 hover:bg-blue-50 dark:hover:bg-gray-800 ${
                selectedId === permit.id ? "bg-blue-50 dark:bg-gray-800" : ""
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
  );
}
