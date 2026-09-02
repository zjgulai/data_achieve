"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Grid3x3, FolderKanban, Clock, Database, Key, BarChart2, BookOpen } from "lucide-react";

const navigation = [
  { name: "采集平台", href: "/platforms",       icon: Grid3x3 },
  { name: "我的项目", href: "/projects",         icon: FolderKanban },
  { name: "运行记录", href: "/runs",             icon: Clock },
  { name: "数据集",   href: "/datasets",         icon: Database },
  { name: "采集文档", href: "/collector-docs",   icon: BookOpen },
];

const secondaryNav = [
  { name: "凭证配置", href: "/settings/credentials", icon: Key },
];

const INSIGHT_URL = "/insight/dashboard";

export function Sidebar() {
  const pathname = usePathname();

  function active(href: string) {
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <aside className="hidden min-h-screen w-[17rem] overflow-y-auto border-r border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-5 lg:fixed lg:inset-y-0 lg:flex lg:flex-col">
      <Link className="mb-7 flex items-center gap-3 px-2" href="/platforms">
        <span className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-3)] bg-[var(--action-primary)] text-[var(--text-inverse)]">
          <Grid3x3 size={20} aria-hidden="true" />
        </span>
        <span>
          <span className="block text-sm font-bold text-[var(--text-primary)]">采集控制台</span>
          <span className="block text-xs text-[var(--text-tertiary)]">Data Intelligence Hub</span>
        </span>
      </Link>

      <nav aria-label="主导航" className="grid gap-1">
        {navigation.map((item) => {
          const on = active(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={on ? "page" : undefined}
              className={`flex min-h-11 items-center gap-3 rounded-[var(--radius-2)] px-3 py-2.5 text-sm font-semibold transition-colors duration-[var(--duration-base)] ${
                on
                  ? "bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              }`}
            >
              <Icon aria-hidden="true" className={on ? "text-[var(--action-primary)]" : "text-[var(--text-tertiary)]"} size={17} />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-[var(--border-subtle)] pt-4">
        <a
          href={INSIGHT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="mb-1 flex min-h-10 items-center gap-3 rounded-[var(--radius-2)] px-3 py-2 text-sm font-medium text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
        >
          <BarChart2 aria-hidden="true" size={16} />
          洞察面板
        </a>
        <nav aria-label="辅助导航" className="grid gap-1">
          {secondaryNav.map((item) => {
            const on = active(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={on ? "page" : undefined}
                className={`flex min-h-10 items-center gap-3 rounded-[var(--radius-2)] px-3 py-2 text-sm font-medium transition-colors duration-[var(--duration-base)] ${
                  on
                    ? "bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                    : "text-[var(--text-tertiary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                }`}
              >
                <Icon aria-hidden="true" size={16} />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}
