"use client";

import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { colorForJurisdiction } from "@/lib/jurisdictionColors";
import type { Permit } from "@/lib/types";

interface PermitsMapProps {
  permits: Permit[]; // must already be filtered to permits with a valid lat/lon
  jurisdictions: string[]; // full known set, for stable per-jurisdiction coloring
  selectedId: number | null;
  onSelect: (permit: Permit) => void;
}

const DEFAULT_CENTER: [number, number] = [39.8283, -98.5795]; // continental US
const DEFAULT_ZOOM = 4;

// Recenters/fits the map to the current point set whenever it changes
// (a filter changed, or the underlying permit list refreshed).
function FitBounds({ permits }: { permits: Permit[] }) {
  const map = useMap();
  const idKey = permits.map((p) => p.id).join(",");

  useEffect(() => {
    if (permits.length === 0) return;
    const points = permits.map((p) => [p.latitude as number, p.longitude as number] as [number, number]);
    if (points.length === 1) {
      map.setView(points[0], 13);
    } else {
      map.fitBounds(points, { padding: [30, 30] });
    }
    // Only needs to re-run when the actual set of plotted points changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idKey]);

  return null;
}

function formatValuation(value: number | null): string {
  return value === null ? "—" : `$${value.toLocaleString("en-US")}`;
}

export default function PermitsMap({ permits, jurisdictions, selectedId, onSelect }: PermitsMapProps) {
  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={DEFAULT_ZOOM}
      scrollWheelZoom
      className="h-[32rem] w-full rounded-lg border border-gray-200 dark:border-gray-700"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds permits={permits} />
      {permits.map((permit) => {
        const color = colorForJurisdiction(permit.jurisdiction, jurisdictions);
        const isSelected = selectedId === permit.id;
        return (
          <CircleMarker
            key={permit.id}
            center={[permit.latitude as number, permit.longitude as number]}
            radius={isSelected ? 9 : 6}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: isSelected ? 0.9 : 0.6,
              weight: isSelected ? 3 : 1,
            }}
            eventHandlers={{ click: () => onSelect(permit) }}
          >
            <Tooltip direction="top" offset={[0, -6]}>
              <div className="text-xs leading-snug">
                <div className="font-semibold">
                  {permit.permit_id} — {permit.jurisdiction}
                </div>
                <div>{permit.address || "UNKNOWN"}</div>
                <div>{permit.permit_type_normalized ?? "—"}</div>
                <div>{formatValuation(permit.valuation)}</div>
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
