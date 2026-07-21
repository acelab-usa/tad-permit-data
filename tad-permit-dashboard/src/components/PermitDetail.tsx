"use client";

import { useState } from "react";
import { parseBuildingSystems, type Permit } from "@/lib/types";

export default function PermitDetail({ permit }: { permit: Permit | null }) {
  const [showRawScope, setShowRawScope] = useState(false);

  if (!permit) {
    return (
      <p className="text-sm text-gray-400">
        Select a permit from the table above to see its full detail.
      </p>
    );
  }

  const systems = parseBuildingSystems(permit.building_systems);

  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
        {permit.permit_id} — {permit.jurisdiction} — {permit.address || "UNKNOWN"}
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        <div className="space-y-1">
          <p>
            <span className="font-medium">Owner:</span> {permit.owner_name || "—"}
          </p>
          <p>
            <span className="font-medium">Contractor:</span> {permit.contractor_name || "—"}
          </p>
          <p>
            <span className="font-medium">Source:</span> {permit.source_format} (
            {permit.source_url || "n/a"})
          </p>
          <p>
            <span className="font-medium">Extracted at:</span> {permit.extracted_at}
          </p>
        </div>
        <div className="space-y-1">
          <p>
            <span className="font-medium">Building systems:</span>{" "}
            {systems.length > 0 ? systems.join(", ") : "—"}
          </p>
          <p>
            <span className="font-medium">Permit type (raw):</span>{" "}
            {permit.permit_type_raw || "—"}
          </p>
        </div>
      </div>

      <div>
        <p className="font-medium text-sm">Scope summary</p>
        <p className="text-sm text-gray-700 dark:text-gray-300">
          {permit.scope_summary || "—"}
        </p>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setShowRawScope((v) => !v)}
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
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
