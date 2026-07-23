"use client";

import { useState } from "react";
import { parseBuildingSystems, type Permit } from "@/lib/types";

export default function PermitDetail({ permit }: { permit: Permit | null }) {
  const [showRawScope, setShowRawScope] = useState(false);

  if (!permit) {
    return (
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm p-4">
        <p className="text-sm text-gray-400">
          Select a permit from the table above to see its full detail.
        </p>
      </div>
    );
  }

  const systems = parseBuildingSystems(permit.building_systems);

  return (
    <div className="space-y-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[var(--chart-surface)] shadow-sm p-4">
      <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
        {permit.permit_id} — {permit.jurisdiction} — {permit.address || "UNKNOWN"}
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        <div className="space-y-1.5">
          <p>
            <span className="font-medium text-gray-500 dark:text-gray-400">Owner:</span>{" "}
            <span className="text-gray-800 dark:text-gray-100">{permit.owner_name || "—"}</span>
          </p>
          <p>
            <span className="font-medium text-gray-500 dark:text-gray-400">Contractor:</span>{" "}
            <span className="text-gray-800 dark:text-gray-100">{permit.contractor_name || "—"}</span>
          </p>
          <p>
            <span className="font-medium text-gray-500 dark:text-gray-400">Source:</span>{" "}
            <span className="text-gray-800 dark:text-gray-100">
              {permit.source_format} ({permit.source_url || "n/a"})
            </span>
          </p>
          <p>
            <span className="font-medium text-gray-500 dark:text-gray-400">Extracted at:</span>{" "}
            <span className="text-gray-800 dark:text-gray-100">{permit.extracted_at}</span>
          </p>
        </div>
        <div className="space-y-1.5">
          <p>
            <span className="font-medium text-gray-500 dark:text-gray-400">Building systems:</span>{" "}
            <span className="text-gray-800 dark:text-gray-100">
              {systems.length > 0 ? systems.join(", ") : "—"}
            </span>
          </p>
          <p>
            <span className="font-medium text-gray-500 dark:text-gray-400">Permit type (raw):</span>{" "}
            <span className="text-gray-800 dark:text-gray-100">{permit.permit_type_raw || "—"}</span>
          </p>
        </div>
      </div>

      <div>
        <p className="font-medium text-sm text-gray-500 dark:text-gray-400">Scope summary</p>
        <p className="text-sm text-gray-700 dark:text-gray-300">
          {permit.scope_summary || "—"}
        </p>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setShowRawScope((v) => !v)}
          className="text-sm text-[var(--accent)] hover:underline"
        >
          {showRawScope ? "▾ Hide raw scope of work" : "▸ Raw scope of work"}
        </button>
        {showRawScope && (
          <p className="mt-2 text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
            {permit.raw_scope_of_work || "—"}
          </p>
        )}
      </div>
    </div>
  );
}
