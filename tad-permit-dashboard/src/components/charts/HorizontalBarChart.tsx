"use client";

import type { DataPoint } from "@/lib/trends";
import { niceTicks } from "./niceTicks";

interface HorizontalBarChartProps {
  data: DataPoint[]; // expected pre-sorted, descending
  valueFormat: (value: number) => string;
  ariaLabel: string;
}

const LABEL_WIDTH = 128;
const VALUE_WIDTH = 84;
const BAR_HEIGHT = 18;

// One series, one hue (magnitude is encoded by bar length, not by color --
// see dataviz skill: a value-ramp on nominal categories double-encodes the
// same information and fails the categorical checks by design).
export default function HorizontalBarChart({ data, valueFormat, ariaLabel }: HorizontalBarChartProps) {
  const maxValue = data.length > 0 ? Math.max(...data.map((d) => d.value)) : 0;
  const ticks = niceTicks(maxValue, 4);
  const domainMax = ticks[ticks.length - 1] || 1;

  if (data.length === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">No data for the current filters.</p>;
  }

  return (
    <div role="img" aria-label={ariaLabel} className="relative">
      <div className="absolute inset-y-0" style={{ left: LABEL_WIDTH, right: VALUE_WIDTH }}>
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

      <div className="relative space-y-2.5">
        {data.map((d) => (
          <div key={d.label} tabIndex={0} className="group flex items-center gap-3 outline-none">
            <div
              className="shrink-0 truncate text-xs text-gray-600 dark:text-gray-300"
              style={{ width: LABEL_WIDTH }}
              title={d.label}
            >
              {d.label}
            </div>
            <div className="relative flex-1" style={{ height: BAR_HEIGHT }}>
              <div
                className="absolute inset-y-0 left-0 rounded-r-[4px] bg-[var(--accent)] transition-[filter] group-hover:brightness-110 group-focus:brightness-110"
                style={{ width: `${Math.max((d.value / domainMax) * 100, d.value > 0 ? 0.5 : 0)}%` }}
              />
            </div>
            <div
              className="shrink-0 text-right text-xs font-medium tabular-nums text-gray-900 dark:text-gray-100"
              style={{ width: VALUE_WIDTH }}
            >
              {valueFormat(d.value)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
