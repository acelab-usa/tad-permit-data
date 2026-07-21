import type { Permit } from "@/lib/types";

function formatCurrency(value: number): string {
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

export default function MetricsRow({ permits }: { permits: Permit[] }) {
  const jurisdictionCount = new Set(permits.map((p) => p.jurisdiction)).size;
  const valuations = permits.map((p) => p.valuation).filter((v): v is number => v !== null);
  const totalValuation = valuations.reduce((sum, v) => sum + v, 0);
  const avgValuation = valuations.length > 0 ? totalValuation / valuations.length : null;

  const stats = [
    { label: "Permits matched", value: permits.length.toLocaleString("en-US") },
    { label: "Jurisdictions", value: jurisdictionCount.toString() },
    { label: "Total valuation", value: formatCurrency(totalValuation) },
    { label: "Avg valuation", value: avgValuation !== null ? formatCurrency(avgValuation) : "N/A" },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-lg border border-gray-200 dark:border-gray-700 p-3"
        >
          <div className="text-xs text-gray-500 dark:text-gray-400">{stat.label}</div>
          <div className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            {stat.value}
          </div>
        </div>
      ))}
    </div>
  );
}
