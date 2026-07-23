import type { Permit } from "@/lib/types";
import { formatCompactCurrency } from "@/lib/trends";

function formatCurrency(value: number): string {
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

export default function MetricsRow({ permits }: { permits: Permit[] }) {
  const jurisdictionCount = new Set(permits.map((p) => p.jurisdiction)).size;
  const valuations = permits.map((p) => p.valuation).filter((v): v is number => v !== null);
  const totalValuation = valuations.reduce((sum, v) => sum + v, 0);
  const avgValuation = valuations.length > 0 ? totalValuation / valuations.length : null;

  const stats = [
    { label: "Permits matched", value: permits.length.toLocaleString("en-US"), icon: "📄" },
    { label: "Jurisdictions", value: jurisdictionCount.toString(), icon: "🏙️" },
    {
      label: "Total valuation",
      value: formatCompactCurrency(totalValuation),
      title: formatCurrency(totalValuation),
      icon: "💰",
    },
    {
      label: "Avg valuation",
      value: avgValuation !== null ? formatCompactCurrency(avgValuation) : "N/A",
      title: avgValuation !== null ? formatCurrency(avgValuation) : undefined,
      icon: "📊",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm p-4"
        >
          <div className="flex items-center gap-2">
            <span
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[var(--accent-wash)] text-sm"
              aria-hidden
            >
              {stat.icon}
            </span>
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{stat.label}</span>
          </div>
          <div
            className="mt-2 text-2xl font-semibold text-gray-900 dark:text-gray-100 truncate"
            title={stat.title}
          >
            {stat.value}
          </div>
        </div>
      ))}
    </div>
  );
}
