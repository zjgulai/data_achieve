"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * 资产域的两个视图。
 *
 * 数据集与原始记录是两层不同对象：
 * - 数据集走 /api/automation/product-datasets。由原始记录派生。
 * - 原始记录走 /api/raw-records。逐条原始数据。
 *
 * 两者都归资产域。见整合方案 §4.3。
 */
const TABS = [
  { href: "/assets", label: "数据集" },
  { href: "/assets/records", label: "原始记录" },
] as const;

export function AssetsTabs() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="资产视图"
      className="mb-6 flex gap-1 border-b border-[var(--border-subtle)]"
    >
      {TABS.map(tab => {
        // 精确匹配。前缀匹配会让两个标签同时高亮。
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={[
              "-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
              active
                ? "border-[var(--action-primary)] text-[var(--action-primary)]"
                : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
            ].join(" ")}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
