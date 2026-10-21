"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Grid3x3, FolderKanban, Clock, Database, Key, BookOpen, Cable, ListChecks, LayoutDashboard, HeartPulse, Users, TrendingUp, BarChart3, Radar } from "lucide-react";

// 新 IA 的领域。见整合方案 §4.2。
const navigation = [
  { name: "工作台", href: "/dashboard", icon: LayoutDashboard },
  { name: "工具",   href: "/tools",     icon: Grid3x3 },
  { name: "TikTok 工作台", href: "/tools/tiktok", icon: TrendingUp },
  { name: "项目",   href: "/projects",  icon: FolderKanban },
  { name: "任务",   href: "/tasks",     icon: ListChecks },
  { name: "运行",   href: "/runs",      icon: Clock },
  { name: "监控",   href: "/monitors",  icon: Radar },
  { name: "资产",   href: "/assets",    icon: Database },
  { name: "接入",   href: "/connect",   icon: Cable },
  { name: "文档",   href: "/docs",      icon: BookOpen },
];

const secondaryNav = [
  { name: "用量与成本", href: "/usage", icon: BarChart3 },
  { name: "凭证设置", href: "/settings/credentials", icon: Key },
  { name: "提供方状态", href: "/settings/providers", icon: HeartPulse },
  { name: "成员与工作区", href: "/settings/members", icon: Users },
];

export function Sidebar() {
  const pathname = usePathname();

  function active(href: string) {
    return pathname === href || pathname.startsWith(`${href}/`);
  }

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
