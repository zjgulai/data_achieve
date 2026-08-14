"use client";

import { ChartNoAxesCombined, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  isNavigationChildActive,
  isNavigationItemActive,
  primaryNavigation,
} from "@/components/layout/navigation";

const focusableSelector =
  'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function MobileNavigation() {
  const [open, setOpen] = useState(false);
  const openerRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const pathname = usePathname();
  const search = useSearchParams().toString();

  const close = useCallback(() => {
    setOpen(false);
    window.requestAnimationFrame(() => openerRef.current?.focus());
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }

    const focusFrame = window.requestAnimationFrame(() => {
      closeButtonRef.current?.focus();
    });

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab") {
        return;
      }

      const drawer = drawerRef.current;
      if (!drawer) {
        return;
      }
      const focusable = Array.from(
        drawer.querySelectorAll<HTMLElement>(focusableSelector),
      );
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) {
        event.preventDefault();
        return;
      }

      const activeElement = document.activeElement;
      if (
        event.shiftKey &&
        (activeElement === first || !drawer.contains(activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [close, open]);

  return (
    <>
      <button
        aria-controls="mobile-primary-navigation"
        aria-expanded={open}
        aria-label="打开导航"
        className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#E9E5E2] bg-[#FFFDFC] text-[#7A625A] transition-colors hover:bg-[#FBF8F5] lg:hidden"
        onClick={() => setOpen(true)}
        ref={openerRef}
        type="button"
      >
        <Menu aria-hidden="true" size={19} />
      </button>
      {open ? (
        <>
          <button
            aria-label="关闭导航遮罩"
            className="fixed inset-0 z-40 bg-[#231A1A]/35 lg:hidden"
            onClick={close}
            tabIndex={-1}
            type="button"
          />
          <aside
            aria-label="移动主导航"
            aria-modal="true"
            className="fixed inset-y-0 left-0 z-50 w-[min(20rem,88vw)] overflow-y-auto border-r border-[#E9E5E2] bg-white p-5 shadow-2xl lg:hidden"
            id="mobile-primary-navigation"
            ref={drawerRef}
            role="dialog"
          >
            <div className="flex items-center justify-between gap-3">
              <button
                aria-label="关闭导航"
                className="order-2 inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#E9E5E2] text-[#7A625A]"
                onClick={close}
                ref={closeButtonRef}
                type="button"
              >
                <X aria-hidden="true" size={18} />
              </button>
              <Link
                className="order-1 flex items-center gap-3"
                href="/dashboard"
                onClick={close}
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#C25B6E] text-white">
                  <ChartNoAxesCombined aria-hidden="true" size={20} />
                </span>
                <span className="text-sm font-semibold text-[#1D1D1F]">
                  Data Intelligence Hub
                </span>
              </Link>
            </div>

            <nav aria-label="主导航" className="mt-6 grid gap-2">
              {primaryNavigation.map((item) => {
                const active = isNavigationItemActive(pathname, search, item);
                const Icon = item.icon;
                return (
                  <div key={String(item.href)}>
                    <Link
                      aria-current={active ? "page" : undefined}
                      className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold ${
                        active
                          ? "bg-[#F8E6E2] text-[#9B4355]"
                          : "text-[#5F5757] hover:bg-[#FBF8F5]"
                      }`}
                      data-testid="mobile-primary-nav-link"
                      href={item.href}
                      onClick={close}
                    >
                      <Icon aria-hidden="true" size={17} />
                      {item.label}
                    </Link>
                    {active ? (
                      <div className="ml-8 mt-1 grid gap-1 border-l border-[#EDE6DF] pl-3">
                        {item.children.map((child) => {
                          const childActive = isNavigationChildActive(
                            pathname,
                            search,
                            child,
                          );
                          return (
                            <Link
                              aria-current={childActive ? "page" : undefined}
                              className={`rounded-lg px-2 py-1.5 text-xs font-medium ${
                                childActive
                                  ? "bg-[#FFF4F0] text-[#9B4355]"
                                  : "text-[#7A706D] hover:bg-[#FBF8F5]"
                              }`}
                              href={child.href}
                              key={String(child.href)}
                              onClick={close}
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
        </>
      ) : null}
    </>
  );
}
