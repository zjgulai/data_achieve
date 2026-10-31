"use client";

import Link from "next/link";
import {
  BarChart3,
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
  Radar,
  Settings,
  TrendingUp,
  Users,
  Wrench,
} from "lucide-react";
import {
  PRIMARY_NAVIGATION,
  activeNavigationHref,
  navigationHrefs,
  type NavigationItem,
  type NavigationSection,
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
  "/monitors": Radar,
  "/usage": BarChart3,
  "/tools": Wrench,
  "/tools/tiktok": TrendingUp,
  "/projects": FolderKanban,
  "/tasks": ListChecks,
  "/assets": Database,
  "/assets/records": Database,
  "/abi": Database,
  "/connect": Cable,
  "/docs": BookOpen,
  "/dashboard": LayoutDashboard,
  "/settings/credentials": Key,
  "/settings/providers": HeartPulse,
  "/settings/members": Users,
};

/** 一级项图标。可点击项与纯标题共用。 */
const SECTION_ICONS: Record<string, typeof Grid3x3> = {
  工作台: LayoutDashboard,
  报告: FileText,
  连接器: Cable,
  设置: Settings,
};

/** 所有导航路径。选中态取最长匹配。 */
const NAV_HREFS: readonly string[] = navigationHrefs(PRIMARY_NAVIGATION);

/** 一个二级链接。 */
function NavigationLink({
  item,
  active,
  onNavigate,
}: {
  readonly item: NavigationItem;
  readonly active: boolean;
  readonly onNavigate?: () => void;
}) {
  const Icon = NAV_ICONS[item.href] ?? Grid3x3;
  const tone = active
    ? "bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
    : "text-[var(--text-tertiary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]";

  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={`flex min-h-10 items-center gap-3 rounded-[var(--radius-2)] px-3 py-2 text-sm font-medium transition-colors duration-[var(--duration-base)] ${tone}`}
      onClick={onNavigate}
    >
      <Icon
        aria-hidden="true"
        size={16}
        className={active ? "text-[var(--action-primary)]" : "text-[var(--text-tertiary)]"}
      />
      {item.name}
    </Link>
  );
}

/**
 * 一个一级项。
 *
 * 有 href 的可点击。没有 href 的只作分组标题，不跳转。
 */
function SectionTitle({
  section,
  active,
  onNavigate,
}: {
  readonly section: NavigationSection;
  readonly active: boolean;
  readonly onNavigate?: () => void;
}) {
  const Icon = SECTION_ICONS[section.name] ?? Grid3x3;
  const base =
    "flex min-h-11 items-center gap-3 rounded-[var(--radius-2)] px-3 py-2.5 text-sm font-semibold";
  const iconClass = active
    ? "text-[var(--action-primary)]"
    : "text-[var(--text-tertiary)]";

  if (!section.href) {
    return (
      <div className={`${base} text-[var(--text-secondary)]`}>
        <Icon aria-hidden="true" size={17} className={iconClass} />
        {section.name}
      </div>
    );
  }

  const tone = active
    ? "bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
    : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]";

  return (
    <Link
      href={section.href}
      aria-current={active ? "page" : undefined}
      className={`${base} transition-colors duration-[var(--duration-base)] ${tone}`}
      onClick={onNavigate}
    >
      <Icon aria-hidden="true" size={17} className={iconClass} />
      {section.name}
    </Link>
  );
}

/**
 * 侧栏与移动抽屉共用的分组导航。
 *
 * 两处必须渲染同一套数据。不要另抄一份 PRIMARY_NAVIGATION。
 */
export function NavigationSections({
  pathname,
  onNavigate,
}: {
  readonly pathname: string;
  /** 点击链接后的回调。移动抽屉用它关闭自己。 */
  readonly onNavigate?: () => void;
}) {
  // 取最长匹配。/capabilities/[toolId] 时父项高亮，/tools/tiktok 时只高亮自己。
  const activeHref = activeNavigationHref(pathname, NAV_HREFS);

  return (
    <nav aria-label="主导航" className="grid gap-6">
      {PRIMARY_NAVIGATION.map(section => (
        <div key={section.name} className="grid gap-1">
          <SectionTitle
            section={section}
            active={section.href === activeHref}
            onNavigate={onNavigate}
          />
          {section.groups?.map(group => (
            <div key={group.name} className="grid gap-1">
              <p className="px-3 pb-1 pt-2 text-xs font-medium text-[var(--text-tertiary)]">
                {group.name}
              </p>
              {group.items.map(item => (
                <NavigationLink
                  key={item.href}
                  item={item}
                  active={item.href === activeHref}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          ))}
          {section.items?.map(item => (
            <NavigationLink
              key={item.href}
              item={item}
              active={item.href === activeHref}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      ))}
    </nav>
  );
}
