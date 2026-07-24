"use client";

import Link from "next/link";
import MetricsRow from "@/components/MetricsRow";
import RecentPermitsList from "@/components/RecentPermitsList";
import { usePermits } from "@/lib/usePermits";
import { REGISTERED_JURISDICTIONS } from "@/lib/jurisdictions";
import { countByJurisdiction, countByPermitType, summarizeContractors } from "@/lib/trends";

interface HighlightTileProps {
  icon: string;
  chip: string;
  label: string;
  name: string | null;
  detail: string | null;
  href?: string;
}

// A single winner, not a ranked list -- the full breakdown for each of
// these lives on Trends; this just teases the #1 and links out rather
// than repeating the chart.
function HighlightTile({ icon, chip, label, name, detail, href }: HighlightTileProps) {
  const nameEl = name === null ? (
    <span className="text-gray-400">—</span>
  ) : href ? (
    <Link href={href} className="text-[var(--accent)] hover:underline">
      {name}
    </Link>
  ) : (
    name
  );

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm p-4">
      <div className="flex items-center gap-2">
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-sm ${chip}`}
          aria-hidden
        >
          {icon}
        </span>
        <span className="text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      </div>
      <div className="mt-2 text-lg font-semibold text-[var(--text-primary)] truncate">{nameEl}</div>
      {detail && <div className="text-xs text-[var(--text-secondary)]">{detail}</div>}
    </div>
  );
}

// Overview is a pure at-a-glance summary -- unfiltered, no Filters
// sidebar. Every full chart/breakdown lives on /trends; this page only
// ever shows a single winner per category plus recent individual permits,
// so there's nothing here that duplicates what Trends already shows.
export default function OverviewPage() {
  const { permits, error, refresh } = usePermits();
  const allPermits = permits ?? [];

  const topJurisdiction = countByJurisdiction(allPermits)[0] ?? null;
  const topType = countByPermitType(allPermits)[0] ?? null;
  const topContractor = summarizeContractors(allPermits)[0] ?? null;

  return (
    <div className="min-h-screen p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">📊 Overview</h1>
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
        <div className="space-y-6">
          <MetricsRow permits={allPermits} />

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <HighlightTile
              icon="🏙️"
              chip="bg-sky-400/15"
              label="Top jurisdiction"
              name={topJurisdiction?.label ?? null}
              detail={topJurisdiction ? `${topJurisdiction.value.toLocaleString("en-US")} permits` : null}
              href="/trends"
            />
            <HighlightTile
              icon="🏷️"
              chip="bg-amber-400/15"
              label="Top permit type"
              name={topType?.label ?? null}
              detail={topType ? `${topType.value.toLocaleString("en-US")} permits` : null}
              href="/trends"
            />
            <HighlightTile
              icon="🧰"
              chip="bg-violet-400/15"
              label="Top contractor"
              name={topContractor?.name ?? null}
              detail={topContractor ? `${topContractor.permitCount.toLocaleString("en-US")} permits` : null}
              href={topContractor ? `/contractors/${encodeURIComponent(topContractor.name)}` : undefined}
            />
          </div>

          <RecentPermitsList permits={allPermits} />

          <p className="text-xs text-gray-500 dark:text-gray-400">
            Unfiltered, all jurisdictions — full breakdowns on Trends, drill down on Table or Map.
          </p>
        </div>
      )}
    </div>
  );
}
