"use client";

import { useState } from "react";
import type { DataPoint } from "@/lib/trends";
import { niceTicks } from "./niceTicks";
import { useContainerWidth } from "./useContainerWidth";

const HEIGHT = 220;
// Extra top margin makes room for the endpoint's direct-label text, which
// sits above the highest point on the line -- without it, a point at (or
// near) the domain max clips its own label against the SVG's top edge.
const MARGIN = { top: 28, right: 32, bottom: 28, left: 44 };

export default function TrendLineChart({ data }: { data: DataPoint[] }) {
  const { ref, width } = useContainerWidth<HTMLDivElement>();
  const [hovered, setHovered] = useState<number | null>(null);

  const plotWidth = Math.max(width - MARGIN.left - MARGIN.right, 1);
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const maxValue = data.length > 0 ? Math.max(...data.map((d) => d.value)) : 0;
  const ticks = niceTicks(maxValue);
  const domainMax = ticks[ticks.length - 1] || 1;

  const x = (i: number) => (data.length <= 1 ? plotWidth / 2 : (i / (data.length - 1)) * plotWidth);
  const y = (v: number) => plotHeight - (v / domainMax) * plotHeight;

  const points = data.map((d, i) => ({ ...d, cx: x(i), cy: y(d.value) }));
  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.cx},${p.cy}`).join(" ");
  const areaPath =
    points.length > 0
      ? `${linePath} L${points[points.length - 1].cx},${plotHeight} L${points[0].cx},${plotHeight} Z`
      : "";

  // Thin out x-axis tick labels once there are more months than comfortably
  // fit -- every point still renders, only the label cadence changes.
  const labelStride = data.length > 8 ? Math.ceil(data.length / 8) : 1;
  const last = points[points.length - 1];

  return (
    <div ref={ref} className="relative">
      <svg viewBox={`0 0 ${width} ${HEIGHT}`} width="100%" height={HEIGHT} role="img" aria-label="Permits filed per month">
        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={0}
                x2={plotWidth}
                y1={y(t)}
                y2={y(t)}
                stroke="var(--chart-gridline)"
                strokeWidth={1}
              />
              <text x={-8} y={y(t)} dy="0.32em" textAnchor="end" fontSize={11} fill="var(--text-muted)">
                {t.toLocaleString("en-US")}
              </text>
            </g>
          ))}
          <line x1={0} x2={plotWidth} y1={plotHeight} y2={plotHeight} stroke="var(--chart-baseline)" strokeWidth={1} />

          {points.map((p, i) => (
            <text
              key={p.label}
              x={p.cx}
              y={plotHeight + 20}
              textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}
              fontSize={11}
              fill="var(--text-muted)"
            >
              {i % labelStride === 0 || i === points.length - 1 ? p.label : ""}
            </text>
          ))}

          {areaPath && <path d={areaPath} fill="var(--accent)" opacity={0.1} />}
          {linePath && (
            <path d={linePath} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          )}

          {last && (
            <>
              <circle cx={last.cx} cy={last.cy} r={5} fill="var(--accent)" stroke="var(--chart-surface)" strokeWidth={2} />
              <text
                x={last.cx}
                y={last.cy - 12}
                textAnchor={points.length > 1 ? "end" : "middle"}
                fontSize={12}
                fontWeight={600}
                fill="var(--text-primary)"
              >
                {last.value.toLocaleString("en-US")}
              </text>
            </>
          )}

          {hovered !== null && points[hovered] && (
            <line
              x1={points[hovered].cx}
              x2={points[hovered].cx}
              y1={0}
              y2={plotHeight}
              stroke="var(--text-muted)"
              strokeWidth={1}
              opacity={0.5}
            />
          )}

          {points.map((p, i) => (
            <rect
              key={p.label}
              x={p.cx - plotWidth / Math.max(points.length, 1) / 2}
              y={0}
              width={plotWidth / Math.max(points.length, 1)}
              height={plotHeight}
              fill="transparent"
              tabIndex={0}
              onPointerEnter={() => setHovered(i)}
              onPointerLeave={() => setHovered((h) => (h === i ? null : h))}
              onFocus={() => setHovered(i)}
              onBlur={() => setHovered((h) => (h === i ? null : h))}
            />
          ))}

          {hovered !== null && points[hovered] && (
            <circle cx={points[hovered].cx} cy={points[hovered].cy} r={5} fill="var(--accent)" stroke="var(--chart-surface)" strokeWidth={2} />
          )}
        </g>
      </svg>

      {hovered !== null && points[hovered] && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-md px-2.5 py-1.5 text-xs"
          style={{
            left: Math.min(Math.max(points[hovered].cx + MARGIN.left, 60), width - 60),
            top: 4,
            transform: "translateX(-50%)",
          }}
        >
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {points[hovered].value.toLocaleString("en-US")}
          </div>
          <div className="text-gray-500 dark:text-gray-400">{points[hovered].label}</div>
        </div>
      )}

      {data.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-gray-400">
          No dated permits match the current filters.
        </div>
      )}
    </div>
  );
}
