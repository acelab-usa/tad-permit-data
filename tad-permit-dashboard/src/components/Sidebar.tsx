"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: "📊" },
  { href: "/table", label: "Table", icon: "📋" },
  { href: "/map", label: "Map", icon: "🗺️" },
  { href: "/trends", label: "Trends", icon: "📈" },
];

// App-level navigation. A vertical rail on lg+ screens (the standard
// modern-dashboard shell -- Linear/Vercel/Retool-style), collapsing to a
// horizontal pill bar on small screens where a fixed rail would eat too
// much width. One component, two layouts, so there's a single source of
// truth for "what pages exist" instead of two nav lists to keep in sync.
export default function Sidebar() {
  const pathname = usePathname();

  return (
    <>
      <aside className="hidden lg:flex lg:flex-col lg:w-56 lg:shrink-0 lg:sticky lg:top-0 lg:h-screen border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-[var(--chart-surface)] px-3 py-5">
        <div className="px-2 mb-6 text-base font-bold text-gray-900 dark:text-gray-100">
          🏗️ Permit Data
        </div>
        <nav className="flex flex-col gap-0.5">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-[var(--accent)] text-white"
                    : "text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                }`}
              >
                <span aria-hidden>{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="lg:hidden border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-[var(--chart-surface)] px-6 py-3">
        <nav className="flex gap-1 rounded-lg border border-gray-200 dark:border-gray-700 p-1 w-fit bg-white/60 dark:bg-black/20">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  active
                    ? "bg-[var(--accent)] text-white"
                    : "text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </>
  );
}
