"use client";

import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import L from "leaflet";
import "leaflet.markercluster";
import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
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

// Leaflet's tile layer wraps horizontally by default -- panning far enough
// east/west shows a repeated copy of the world's tiles. Markers exist at one
// fixed lat/lng each and never get duplicated onto those extra copies,
// which is what made pins seem to "disappear" when scrolled past a wrap
// boundary. There's no reason this map needs infinite world panning, so
// `noWrap` on the tile layer stops the repeated copies from rendering at
// all, and `maxBounds` (a single world's worth, north/south included) stops
// the user from dragging into the now-empty space beyond it.
const WORLD_BOUNDS: [[number, number], [number, number]] = [
  [-90, -180],
  [90, 180],
];

// Leaflet measures its container's size once when the map is created and
// has no way to know if that size changes afterward (a window resize, a
// sidebar collapsing, a parent layout shift) unless something tells it to
// recheck. Defensive measure, not specific to any bug found so far --
// keeps the map correctly sized regardless of what else changes around it.
function SyncMapSize() {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    // Correct any stale initial measurement once layout has had a chance to settle.
    const raf = requestAnimationFrame(() => map.invalidateSize());

    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(container);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, [map]);

  return null;
}

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

// Leaflet's default marker icon is an image asset that doesn't resolve
// correctly through Next.js's bundler without extra config -- a well-known
// gotcha. A colored circle drawn via a DivIcon (plain HTML/CSS) sidesteps
// that entirely while keeping the same jurisdiction-colored-dot look the
// unclustered version had, and DivIcons work fine with markercluster
// (unlike the CircleMarker/SVG-path layer used before, which
// leaflet.markercluster doesn't support -- it only clusters L.Marker-like
// layers).
//
// A solid-fill dot with a light ring (rather than the same-color
// half-opacity border the first version used) reads with real contrast
// against the dark basemap regardless of hue, and a drop shadow gives it
// depth instead of looking like a flat sticker. Selected state swaps the
// ring to the brand accent instead of just growing the dot.
function markerIcon(color: string, isSelected: boolean): L.DivIcon {
  const size = isSelected ? 14 : 10;
  const ringWidth = isSelected ? 3 : 2;
  const ringColor = isSelected ? "var(--accent)" : "rgba(245, 244, 238, 0.85)";
  const total = size + ringWidth * 2;
  return L.divIcon({
    className: "",
    html: `<div style="width:${size}px;height:${size}px;border-radius:9999px;background:${color};border:${ringWidth}px solid ${ringColor};box-shadow:0 1px 6px rgba(0,0,0,0.7);box-sizing:content-box;"></div>`,
    iconSize: [total, total],
    iconAnchor: [total / 2, total / 2],
  });
}

// Replaces leaflet.markercluster's own default look (a two-tone
// yellow/orange/green ring, unchanged since the plugin's original 2012
// release) with a dark pill in the brand accent, sized in the same
// small/medium/large tiers the plugin uses.
function clusterIcon(cluster: { getChildCount: () => number }): L.DivIcon {
  const count = cluster.getChildCount();
  const size = count < 10 ? 32 : count < 100 ? 40 : 48;
  const fontSize = count < 100 ? 13 : 12;
  return L.divIcon({
    className: "",
    html: `<div style="width:${size}px;height:${size}px;border-radius:9999px;background:var(--chart-surface);border:2px solid var(--accent);display:flex;align-items:center;justify-content:center;color:var(--accent);font-weight:700;font-size:${fontSize}px;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;box-shadow:0 2px 10px rgba(0,0,0,0.7);">${count}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function tooltipHtml(permit: Permit): string {
  return `
    <div style="font-size:12px;line-height:1.4">
      <div style="font-weight:600">${permit.permit_id} — ${permit.jurisdiction}</div>
      <div>${permit.address || "UNKNOWN"}</div>
      <div>${permit.permit_type_normalized ?? "—"}</div>
      <div>${formatValuation(permit.valuation)}</div>
    </div>
  `;
}

// Builds (and rebuilds, on permit-set changes) a marker cluster group --
// nearby markers collapse into a single numbered bubble at lower zoom
// levels and split apart as you zoom in, so a dense cluster of permits
// (e.g. downtown Chicago) stays clickable instead of a pile of
// overlapping, unclickable dots.
function ClusteredMarkers({ permits, jurisdictions, selectedId, onSelect }: PermitsMapProps) {
  const map = useMap();
  const markersByIdRef = useRef<Map<number, L.Marker>>(new Map());
  const idKey = permits.map((p) => p.id).join(",");
  const jurisdictionKey = jurisdictions.join(",");

  useEffect(() => {
    const clusterGroup = L.markerClusterGroup({ maxClusterRadius: 60, iconCreateFunction: clusterIcon });
    const markersById = new Map<number, L.Marker>();

    permits.forEach((permit) => {
      const color = colorForJurisdiction(permit.jurisdiction, jurisdictions);
      const marker = L.marker([permit.latitude as number, permit.longitude as number], {
        icon: markerIcon(color, false),
      });
      marker.bindTooltip(tooltipHtml(permit), { direction: "top", offset: [0, -8] });
      marker.on("click", () => onSelect(permit));
      clusterGroup.addLayer(marker);
      markersById.set(permit.id, marker);
    });

    map.addLayer(clusterGroup);
    markersByIdRef.current = markersById;

    return () => {
      map.removeLayer(clusterGroup);
      markersByIdRef.current = new Map();
    };
    // Rebuild only when the actual point set or color assignment changes --
    // onSelect is stable (setState setter) and selectedId is handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idKey, jurisdictionKey, map]);

  // Update just the selected/unselected marker icons in place, without
  // rebuilding (and re-clustering) the whole layer on every click.
  useEffect(() => {
    markersByIdRef.current.forEach((marker, id) => {
      const permit = permits.find((p) => p.id === id);
      if (!permit) return;
      const color = colorForJurisdiction(permit.jurisdiction, jurisdictions);
      marker.setIcon(markerIcon(color, id === selectedId));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, idKey, jurisdictionKey]);

  return null;
}

export default function PermitsMap({ permits, jurisdictions, selectedId, onSelect }: PermitsMapProps) {
  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={DEFAULT_ZOOM}
      scrollWheelZoom
      maxBounds={WORLD_BOUNDS}
      maxBoundsViscosity={1.0}
      minZoom={2}
      className="h-[32rem] w-full rounded-lg border border-gray-200 dark:border-gray-700"
    >
      <TileLayer
        // A dark basemap so the map reads as part of the app's black/green
        // theme instead of a light-gray box sitting in an otherwise dark
        // page. CartoDB's free "dark matter" tiles are the standard choice
        // for this (no API key required).
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        subdomains="abcd"
        noWrap
      />
      <SyncMapSize />
      <FitBounds permits={permits} />
      <ClusteredMarkers
        permits={permits}
        jurisdictions={jurisdictions}
        selectedId={selectedId}
        onSelect={onSelect}
      />
    </MapContainer>
  );
}
