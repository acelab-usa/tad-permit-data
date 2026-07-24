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
    { label: "Permits matched", value: permits.length.toLocaleString("en-US"), icon: "📄", chip: "bg-[var(--accent-wash)]" },
    { label: "Jurisdictions", value: jurisdictionCount.toString(), icon: "🏙️", chip: "bg-sky-400/15" },
    {
      label: "Total valuation",
      value: formatCompactCurrency(totalValuation),
      title: formatCurrency(totalValuation),
      icon: "💰",
      chip: "bg-amber-400/15",
    },
    {
      label: "Avg valuation",
      value: avgValuation !== null ? formatCompactCurrency(avgValuation) : "N/A",
      title: avgValuation !== null ? formatCurrency(avgValuation) : undefined,
      icon: "📊",
      chip: "bg-violet-400/15",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-xl border border-white/10 bg-[var(--chart-surface)] shadow-sm p-4"
        >
          <div className="flex items-center gap-2">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-sm ${stat.chip}`}
              aria-hidden
            >
              {stat.icon}
            </span>
            <span className="text-xs font-medium text-[var(--text-secondary)]">{stat.label}</span>
          </div>
          <div
            className="mt-2 text-2xl font-semibold text-[var(--text-primary)] truncate"
            title={stat.title}
          >
            {stat.value}
          </div>
        </div>
      ))}
    </div>
  );
}
