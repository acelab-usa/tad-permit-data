"use client";

import { useEffect, useRef, useState } from "react";

// Charts are hand-rolled SVG (no charting library dependency), so they need
// their own pixel-accurate width to lay out ticks/labels -- viewBox scaling
// alone would scale text size along with it. Falls back to defaultWidth
// until the first ResizeObserver callback fires.
export function useContainerWidth<T extends HTMLElement>(defaultWidth = 640) {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(defaultWidth);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    setWidth(el.clientWidth || defaultWidth);
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setWidth(entry.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [defaultWidth]);

  return { ref, width };
}
