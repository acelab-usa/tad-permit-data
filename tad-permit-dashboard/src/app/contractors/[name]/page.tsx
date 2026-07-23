"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import PermitsTable from "@/components/PermitsTable";
import PermitDetail from "@/components/PermitDetail";
import { usePermits } from "@/lib/usePermits";
import { downloadCsv, toCsv } from "@/lib/csv";
import { PERMIT_CSV_COLUMNS, type Permit } from "@/lib/types";
import { formatCompactCurrency } from "@/lib/trends";

function slugFilename(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "contractor";
}

export default function ContractorDetailPage() {
  const params = useParams<{ name: string }>();
  const name = decodeURIComponent(params.name);
  const { permits, error, refresh } = usePermits();
  const [selected, setSelected] = useState<Permit | null>(null);

  const contractorPermits = (permits ?? []).filter((p) => p.contractor_name?.trim() === name);
  const totalValuation = contractorPermits.reduce((sum, p) => sum + (p.valuation ?? 0), 0);
  const jurisdictions = Array.from(new Set(contractorPermits.map((p) => p.jurisdiction))).sort();

  return (
    <div className="min-h-screen p-6 max-w-7xl mx-auto">
      <div className="mb-4">
        <Link href="/contractors" className="text-sm text-[var(--accent)] hover:underline">
          ← All contractors
        </Link>
      </div>

      <div className="flex items-center justify-between mb-6 gap-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 truncate">🧰 {name}</h1>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() =>
              downloadCsv(`${slugFilename(name)}-permits.csv`, toCsv(contractorPermits, PERMIT_CSV_COLUMNS))
            }
            disabled={contractorPermits.length === 0}
            className="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ⬇️ Export CSV
          </button>
          <button
            type="button"
            onClick={refresh}
            className="rounded-lg bg-[var(--accent)] text-black font-medium px-3 py-1.5 text-sm hover:brightness-95 transition-[filter]"
          >
            🔄 Refresh data
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-300 bg-red-50 dark:bg-red-950 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300">
          Failed to load permits: {error}
        </div>
      )}

      {permits === null ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm p-4">
              <div className="text-xs font-medium text-[var(--text-secondary)]">Permits</div>
              <div className="mt-1 text-2xl font-semibold text-[var(--text-primary)]">
                {contractorPermits.length.toLocaleString("en-US")}
              </div>
            </div>
            <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm p-4">
              <div className="text-xs font-medium text-[var(--text-secondary)]">Total valuation</div>
              <div className="mt-1 text-2xl font-semibold text-[var(--text-primary)] truncate">
                {formatCompactCurrency(totalValuation)}
              </div>
            </div>
            <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm p-4">
              <div className="text-xs font-medium text-[var(--text-secondary)]">Jurisdictions</div>
              <div className="mt-1 text-2xl font-semibold text-[var(--text-primary)] truncate" title={jurisdictions.join(", ")}>
                {jurisdictions.join(", ") || "—"}
              </div>
            </div>
          </div>

          {contractorPermits.length === 0 ? (
            <p className="text-sm text-gray-500">
              No permits found for &ldquo;{name}&rdquo;. It may have been removed by a re-ingestion, or the name
              doesn&apos;t match exactly (contractor names aren&apos;t normalized across sources yet).
            </p>
          ) : (
            <>
              <PermitsTable
                permits={contractorPermits}
                selectedId={selected?.id ?? null}
                onSelect={setSelected}
              />
              <section>
                <h2 className="text-lg font-semibold mb-2 text-gray-900 dark:text-gray-100">Permit detail</h2>
                <PermitDetail permit={selected} />
              </section>
            </>
          )}
        </div>
      )}
    </div>
  );
}
