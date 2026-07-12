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
    <aside className="hidden min-h-screen w-72 overflow-y-auto border-r border-[#E9E5E2] bg-white px-4 py-5 lg:fixed lg:inset-y-0 lg:flex lg:flex-col">
      <Link className="mb-7 flex items-center gap-3 px-2" href="/dashboard">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#C25B6E] text-white">
          <ChartNoAxesCombined size={20} aria-hidden="true" />
        </span>
        <span>
          <span className="block text-sm font-semibold text-[#1D1D1F]">
            Data Intelligence
          </span>
          <span className="block text-xs text-[#86868B]">Hub</span>
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
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors ${
                  active
                    ? "bg-[#F8E6E2] text-[#9B4355]"
                    : "text-[#5F5757] hover:bg-[#FBF8F5] hover:text-[#1D1D1F]"
                }`}
                data-testid="primary-nav-link"
                href={item.href}
              >
                <Icon
                  aria-hidden="true"
                  className={active ? "text-[#C25B6E]" : "text-[#86868B]"}
                  size={17}
                />
                {item.label}
              </Link>
              {active ? (
                <div className="ml-7 mt-1 grid gap-1 border-l border-[#EDE6DF] pl-3">
                  {item.children.map((child) => {
                    const childActive = isNavigationChildActive(
                      pathname,
                      search,
                      child,
                    );
                    return (
                      <Link
                        aria-current={childActive ? "page" : undefined}
                        className={`rounded-lg px-2 py-1.5 text-xs font-medium transition-colors ${
                          childActive
                            ? "bg-[#FFF4F0] text-[#9B4355]"
                            : "text-[#7A706D] hover:bg-[#FBF8F5] hover:text-[#1D1D1F]"
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
