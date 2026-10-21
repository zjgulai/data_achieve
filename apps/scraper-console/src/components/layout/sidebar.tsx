"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  Cable,
  Clock,
  Database,
  FileText,
  FolderKanban,
  Grid3x3,
  HeartPulse,
  Key,
  LayoutDashboard,
  ListChecks,
  TrendingUp,
  Users,
  Wrench,
} from "lucide-react";
import {
  PRIMARY_NAVIGATION,
  SECONDARY_NAVIGATION,
  activeNavigationHref,
  type NavigationItem,
} from "@/lib/routes";

/**
 * 路径到图标。
 *
 * 图标留在视图层。routes.ts 只存导航数据，因此 Node 测试可以直接加载它。
 */
const NAV_ICONS: Record<string, typeof Grid3x3> = {
  "/workbench": LayoutDashboard,
  "/capabilities": Grid3x3,
  "/reports": FileText,
  "/runs": Clock,
  "/tools": Wrench,
  "/tools/tiktok": TrendingUp,
  "/projects": FolderKanban,
  "/tasks": ListChecks,
  "/assets": Database,
  "/connect": Cable,
  "/docs": BookOpen,
  "/dashboard": LayoutDashboard,
  "/settings/credentials": Key,
  "/settings/providers": HeartPulse,
  "/settings/members": Users,
};

/** 所有导航路径。选中态取最长匹配。 */
const NAV_HREFS: readonly string[] = [
  ...PRIMARY_NAVIGATION.map(item => item.href),
  ...SECONDARY_NAVIGATION.map(item => item.href),
];

/** 一个导航链接。二级导航使用较小的字号与较浅的默认色。 */
function NavigationLink({
  item,
  active,
  secondary,
}: {
  readonly item: NavigationItem;
  readonly active: boolean;
  readonly secondary: boolean;
}) {
  const Icon = NAV_ICONS[item.href] ?? Grid3x3;
  const size = secondary ? 16 : 17;
  const base = secondary
    ? "min-h-10 px-3 py-2 text-sm font-medium"
    : "min-h-11 px-3 py-2.5 text-sm font-semibold";
  const tone = active
    ? "bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
    : secondary
      ? "text-[var(--text-tertiary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
      : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]";

  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={`flex items-center gap-3 rounded-[var(--radius-2)] transition-colors duration-[var(--duration-base)] ${base} ${tone}`}
    >
      <Icon
        aria-hidden="true"
        size={size}
        className={active ? "text-[var(--action-primary)]" : "text-[var(--text-tertiary)]"}
      />
      {item.name}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  // 取最长匹配。/capabilities/[toolId] 时父项高亮，/tools/tiktok 时只高亮自己。
  const activeHref = activeNavigationHref(pathname, NAV_HREFS);

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
        {PRIMARY_NAVIGATION.map(item => (
          <NavigationLink
            key={item.href}
            item={item}
            active={item.href === activeHref}
            secondary={false}
          />
        ))}
      </nav>

      <div className="mt-auto border-t border-[var(--border-subtle)] pt-4">
        <nav aria-label="辅助导航" className="grid gap-1">
          {SECONDARY_NAVIGATION.map(item => (
            <NavigationLink
              key={item.href}
              item={item}
              active={item.href === activeHref}
              secondary
            />
          ))}
        </nav>
      </div>
    </aside>
  );
}
