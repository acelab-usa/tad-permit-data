"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Table" },
  { href: "/map", label: "Map" },
  { href: "/trends", label: "Trends" },
];

export default function NavTabs() {
  const pathname = usePathname();

  return (
    <nav className="flex gap-1 rounded-lg border border-gray-200 dark:border-gray-700 p-1 w-fit bg-white/60 dark:bg-black/20">
      {TABS.map((tab) => {
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              active
                ? "bg-[var(--accent)] text-white"
                : "text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
