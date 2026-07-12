import {
  Bot,
  ChartNoAxesCombined,
  FolderKanban,
  Gauge,
  Store,
  TableProperties,
  type LucideIcon,
} from "lucide-react";
import type { Route } from "next";

export type NavigationChild = {
  href: Route;
  label: string;
};

export type NavigationItem = {
  href: Route;
  label: string;
  icon: LucideIcon;
  children: NavigationChild[];
};

function child(href: string, label: string): NavigationChild {
  return { href: href as Route, label };
}

function nav(
  href: string,
  label: string,
  icon: LucideIcon,
  children: NavigationChild[],
): NavigationItem {
  return { href: href as Route, label, icon, children };
}

function targetUrl(href: Route): URL {
  return new URL(String(href), "http://navigation.local");
}

export function isNavigationChildActive(
  pathname: string,
  search: string,
  item: NavigationChild,
): boolean {
  const target = targetUrl(item.href);
  if (target.pathname !== pathname) {
    return false;
  }

  const current = new URLSearchParams(search);
  for (const [key, expected] of target.searchParams) {
    if (key === "view" && expected === "scenarios" && !current.has(key)) {
      continue;
    }
    if (current.get(key) !== expected) {
      return false;
    }
  }
  return true;
}

export function isNavigationItemActive(
  pathname: string,
  search: string,
  item: NavigationItem,
): boolean {
  const primaryPath = targetUrl(item.href).pathname;
  if (
    pathname === primaryPath ||
    (primaryPath === "/api-market" && pathname.startsWith("/api-market/"))
  ) {
    return true;
  }
  return item.children.some((childItem) =>
    isNavigationChildActive(pathname, search, childItem),
  );
}

export const primaryNavigation = [
  nav("/dashboard", "工作台", Gauge, [
    child("/toolkit", "采集工具库"),
    child("/playbooks/site-user-playbook.html", "使用手册"),
  ]),
  nav("/projects", "监测项目", FolderKanban, [
    child("/domain/osint", "开源雷达"),
    child("/domain/ecommerce", "电商风向"),
    child("/domain/social", "社媒范围"),
    child("/domain/competitor", "竞品范围"),
    child("/domain/agent", "Agent 生态"),
    child("/domain/platform", "平台采集"),
    child("/domain/governance", "合规边界"),
  ]),
  nav("/automation", "采集工作流", Bot, [
    child("/tasks", "采集任务"),
    child("/sources", "数据源"),
  ]),
  nav("/datasets", "数据资产", TableProperties, [
    child("/raw-records", "原始数据"),
    child("/entities", "实体库"),
  ]),
  nav("/intelligence", "洞察与交付", ChartNoAxesCombined, [
    child("/signals", "信号中心"),
    child("/reports", "报告中心"),
    child("/alerts", "预警中心"),
    child("/notifications", "站内通知"),
  ]),
  nav("/api-market", "能力市场", Store, [
    child("/api-market?view=scenarios", "场景视图"),
    child("/api-market?view=matrix", "矩阵视图"),
    child("/api-market?view=list", "能力列表"),
  ]),
] satisfies NavigationItem[];
