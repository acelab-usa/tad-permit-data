"use client";

import { Fragment, useState } from "react";
import Link from "next/link";
import type { DataPoint } from "@/lib/trends";
import { niceTicks } from "./niceTicks";

interface HorizontalBarChartProps {
  data: DataPoint[]; // expected pre-sorted, descending
  valueFormat: (value: number) => string;
  ariaLabel: string;
  // When provided, each bar's label becomes a link (e.g. a contractor name
  // linking to its drill-down page) instead of plain text. Optional --
  // most uses of this chart (jurisdiction, permit type) have nowhere to
  // link to.
  linkFor?: (label: string) => string;
}

const BAR_HEIGHT = 18;
// Label/value columns cap at a max width but shrink with the container
// (minmax(0, cap)) -- a fixed pixel width left no room for the bar track
// at all in narrow cards (e.g. the Overview page's 3-up grid).
const GRID_TEMPLATE = "minmax(0,7rem) 1fr minmax(3rem,4rem)";

// One series, one hue (magnitude is encoded by bar length, not by color --
// see dataviz skill: a value-ramp on nominal categories double-encodes the
// same information and fails the categorical checks by design).
export default function HorizontalBarChart({ data, valueFormat, ariaLabel, linkFor }: HorizontalBarChartProps) {
  const [hovered, setHovered] = useState<number | null>(null);
  const maxValue = data.length > 0 ? Math.max(...data.map((d) => d.value)) : 0;
  const ticks = niceTicks(maxValue, 4);
  const domainMax = ticks[ticks.length - 1] || 1;

  if (data.length === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">No data for the current filters.</p>;
  }

  return (
    <div
      role="img"
      aria-label={ariaLabel}
      className="grid items-center gap-x-3 gap-y-2.5"
      style={{ gridTemplateColumns: GRID_TEMPLATE }}
    >
      {/* Gridline overlay: one grid item spanning column 2 across every
          row, so tick positions are plain CSS percentages of that column's
          actual rendered width -- no JS measurement needed. */}
      <div className="relative" style={{ gridColumn: 2, gridRow: `1 / span ${data.length}` }}>
        {ticks.map((t) => (
          <div
            key={t}
            className="absolute inset-y-0 border-l"
            style={{
              left: `${(t / domainMax) * 100}%`,
              borderColor: t === 0 ? "var(--chart-baseline)" : "var(--chart-gridline)",
            }}
          />
        ))}
      </div>

      {data.map((d, i) => {
        const rowHandlers = {
          onPointerEnter: () => setHovered(i),
          onPointerLeave: () => setHovered((h) => (h === i ? null : h)),
          onFocus: () => setHovered(i),
          onBlur: () => setHovered((h) => (h === i ? null : h)),
        };
        const labelClassName = `truncate text-xs outline-none ${
          linkFor
            ? "text-[var(--accent)] hover:underline"
            : "text-gray-600 dark:text-gray-300"
        }`;
        return (
          <Fragment key={d.label}>
            {linkFor ? (
              <Link
                href={linkFor(d.label)}
                className={labelClassName}
                style={{ gridRow: i + 1, gridColumn: 1 }}
                title={d.label}
                {...rowHandlers}
              >
                {d.label}
              </Link>
            ) : (
              <div
                tabIndex={0}
                className={labelClassName}
                style={{ gridRow: i + 1, gridColumn: 1 }}
                title={d.label}
                {...rowHandlers}
              >
                {d.label}
              </div>
            )}
            <div className="relative" style={{ gridRow: i + 1, gridColumn: 2, height: BAR_HEIGHT }} {...rowHandlers}>
              <div
                className="absolute inset-y-0 left-0 rounded-r-[4px] bg-[var(--accent)] transition-[filter]"
                style={{
                  width: `${Math.max((d.value / domainMax) * 100, d.value > 0 ? 0.5 : 0)}%`,
                  filter: hovered === i ? "brightness(1.1)" : undefined,
                }}
              />
            </div>
            <div
              className="text-right text-xs font-medium tabular-nums text-gray-900 dark:text-gray-100"
              style={{ gridRow: i + 1, gridColumn: 3 }}
            >
              {valueFormat(d.value)}
            </div>
          </Fragment>
        );
      })}
    </div>
  );
}
