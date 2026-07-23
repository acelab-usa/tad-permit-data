import CheckboxGroup from "./CheckboxGroup";
import type { FiltersState } from "@/lib/filters";

interface FiltersProps {
  jurisdictionOptions: readonly string[];
  permitTypeOptions: readonly string[];
  valuationBounds: { min: number; max: number } | null;
  filters: FiltersState;
  onChange: (next: FiltersState) => void;
}

export default function Filters({
  jurisdictionOptions,
  permitTypeOptions,
  valuationBounds,
  filters,
  onChange,
}: FiltersProps) {
  function set<K extends keyof FiltersState>(key: K, value: FiltersState[K]) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <aside className="w-full lg:w-72 shrink-0 space-y-5 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm p-4 lg:sticky lg:top-6 lg:self-start lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
        Filters
      </h2>

      <CheckboxGroup
        label="Jurisdiction"
        options={jurisdictionOptions}
        selected={filters.jurisdictions}
        onChange={(next) => set("jurisdictions", next)}
      />

      <CheckboxGroup
        label="Permit type"
        options={permitTypeOptions}
        selected={filters.permitTypes}
        onChange={(next) => set("permitTypes", next)}
      />

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
          Search (address, owner, contractor, permit #)
        </label>
        <input
          type="text"
          value={filters.searchText}
          onChange={(e) => set("searchText", e.target.value)}
          placeholder="e.g. 123 Main St"
          className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1.5 text-sm outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
          Filing date range
        </label>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={filters.dateFrom}
            onChange={(e) => set("dateFrom", e.target.value)}
            className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1.5 text-sm outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
          />
          <span className="text-gray-400">–</span>
          <input
            type="date"
            value={filters.dateTo}
            onChange={(e) => set("dateTo", e.target.value)}
            className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1.5 text-sm outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
          />
        </div>
      </div>

      {valuationBounds && (
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
            Valuation range ($)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={filters.valuationMin ?? ""}
              placeholder={valuationBounds.min.toString()}
              onChange={(e) =>
                set("valuationMin", e.target.value === "" ? null : Number(e.target.value))
              }
              className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1.5 text-sm outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
            />
            <span className="text-gray-400">–</span>
            <input
              type="number"
              value={filters.valuationMax ?? ""}
              placeholder={valuationBounds.max.toString()}
              onChange={(e) =>
                set("valuationMax", e.target.value === "" ? null : Number(e.target.value))
              }
              className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1.5 text-sm outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
            />
          </div>
        </div>
      )}
    </aside>
  );
}
