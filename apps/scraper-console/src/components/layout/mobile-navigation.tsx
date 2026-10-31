"use client";

import { Grid3x3, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { NavigationSections } from "@/components/layout/navigation-sections";

const focusableSelector =
  'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * 移动端导航。
 *
 * 侧栏在 <lg 断点隐藏。这个抽屉复用同一份 PRIMARY_NAVIGATION 渲染逻辑，
 * 交互与 apps/web 的 mobile-navigation 一致：遮罩、焦点陷阱、路由变化关闭。
 */
export function MobileNavigation() {
  const [open, setOpen] = useState(false);
  const openerRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const pathname = usePathname();

  const close = useCallback(() => {
    setOpen(false);
    window.requestAnimationFrame(() => openerRef.current?.focus());
  }, []);

  // 路由变化自动关闭。点击链接已调用 close；这里覆盖前进、后退等导航。
  // 放到下一帧，避免在 effect 内同步 setState。
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setOpen(false));
    return () => window.cancelAnimationFrame(frame);
  }, [pathname]);

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
        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] text-[var(--text-secondary)] transition-colors duration-[var(--duration-base)] hover:bg-[var(--surface-muted)] lg:hidden"
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
            className="fixed inset-0 z-40 bg-[var(--overlay-1)] lg:hidden"
            onClick={close}
            tabIndex={-1}
            type="button"
          />
          <aside
            aria-label="移动主导航"
            aria-modal="true"
            className="fixed inset-y-0 left-0 z-50 w-[min(20rem,88vw)] overflow-y-auto border-r border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5 shadow-[var(--shadow-overlay)] lg:hidden"
            id="mobile-primary-navigation"
            ref={drawerRef}
            role="dialog"
          >
            <div className="flex items-center justify-between gap-3">
              <Link
                className="order-1 flex items-center gap-3"
                href="/tools"
                onClick={close}
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-3)] bg-[var(--action-primary)] text-[var(--text-inverse)]">
                  <Grid3x3 aria-hidden="true" size={20} />
                </span>
                <span>
                  <span className="block text-sm font-bold text-[var(--text-primary)]">
                    采集控制台
                  </span>
                  <span className="block text-xs text-[var(--text-tertiary)]">
                    Data Intelligence Hub
                  </span>
                </span>
              </Link>
              <button
                aria-label="关闭导航"
                className="order-2 inline-flex h-11 w-11 items-center justify-center rounded-[var(--radius-2)] border border-[var(--border-subtle)] text-[var(--text-secondary)] transition-colors duration-[var(--duration-base)] hover:bg-[var(--surface-muted)]"
                onClick={close}
                ref={closeButtonRef}
                type="button"
              >
                <X aria-hidden="true" size={18} />
              </button>
            </div>

            <div className="mt-6">
              <NavigationSections pathname={pathname} onNavigate={close} />
            </div>
          </aside>
        </>
      ) : null}
    </>
  );
}
