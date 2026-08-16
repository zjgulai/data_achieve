"use client";

import { ChartNoAxesCombined } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import {
  isNavigationChildActive,
  isNavigationItemActive,
  primaryNavigation,
} from "@/components/layout/navigation";

export function Sidebar() {
  const pathname = usePathname();
  const search = useSearchParams().toString();

  return (
    <aside className="hidden min-h-screen w-[var(--sidebar-width)] overflow-y-auto border-r border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-5 lg:fixed lg:inset-y-0 lg:flex lg:flex-col">
      <Link className="mb-7 flex items-center gap-3 px-2" href="/dashboard">
        <span className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-3)] bg-[var(--action-primary)] text-[var(--text-inverse)]">
          <ChartNoAxesCombined size={20} aria-hidden="true" />
        </span>
        <span>
          <span className="block text-sm font-semibold text-[var(--text-primary)]">
            Data Intelligence
          </span>
          <span className="block text-xs text-[var(--text-tertiary)]">Hub</span>
        </span>
      </Link>

      <nav aria-label="主导航" className="grid gap-2">
        {primaryNavigation.map((item) => {
          const active = isNavigationItemActive(pathname, search, item);
          const Icon = item.icon;
          return (
            <div key={String(item.href)}>
              <Link
                aria-current={active ? "page" : undefined}
                className={`flex min-h-11 items-center gap-3 rounded-[var(--radius-2)] px-3 py-2.5 text-sm font-semibold transition-colors duration-[var(--duration-base)] ${
                  active
                    ? "bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                }`}
                data-testid="primary-nav-link"
                href={item.href}
              >
                <Icon
                  aria-hidden="true"
                  className={active ? "text-[var(--action-primary)]" : "text-[var(--text-tertiary)]"}
                  size={17}
                />
                {item.label}
              </Link>
              {active ? (
                <div className="ml-7 mt-1 grid gap-1 border-l border-[var(--border-subtle)] pl-3">
                  {item.children.map((child) => {
                    const childActive = isNavigationChildActive(
                      pathname,
                      search,
                      child,
                    );
                    return (
                      <Link
                        aria-current={childActive ? "page" : undefined}
                        className={`rounded-[var(--radius-2)] px-2 py-1.5 text-xs font-medium transition-colors duration-[var(--duration-base)] ${
                          childActive
                            ? "bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                            : "text-[var(--text-tertiary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                        }`}
                        href={child.href}
                        key={String(child.href)}
                      >
                        {child.label}
                      </Link>
                    );
                  })}
                </div>
              ) : null}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
