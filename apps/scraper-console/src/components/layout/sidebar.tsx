"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Grid3x3 } from "lucide-react";
import { NavigationSections } from "@/components/layout/navigation-sections";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden min-h-screen w-[17rem] overflow-y-auto border-r border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-5 lg:fixed lg:inset-y-0 lg:flex lg:flex-col">
      <Link className="mb-7 flex items-center gap-3 px-2" href="/tools">
        <span className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-3)] bg-[var(--action-primary)] text-[var(--text-inverse)]">
          <Grid3x3 size={20} aria-hidden="true" />
        </span>
        <span>
          <span className="block text-sm font-bold text-[var(--text-primary)]">采集控制台</span>
          <span className="block text-xs text-[var(--text-tertiary)]">Data Intelligence Hub</span>
        </span>
      </Link>

      <NavigationSections pathname={pathname} />
    </aside>
  );
}
