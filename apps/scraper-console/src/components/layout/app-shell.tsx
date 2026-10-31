import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";

type Crumb = { label: string; href?: string };

type AppShellProps = {
  title: string;
  description?: string;
  brief?: string;
  breadcrumbs?: Crumb[];
  /**
   * 覆盖内容区样式。
   *
   * 工作台用全宽三栏，其余页面保持默认的 max-w-7xl 单列。
   */
  mainClassName?: string;
  /**
   * 让页面在 xl 及以上锁住视口高度，内容区内部滚动。
   *
   * 默认关闭。开启后低于 xl 的断点仍按普通文档流滚动，
   * 因为工作台的三栏只在 xl 才展开。
   */
  fillViewport?: boolean;
  children: React.ReactNode;
};

export function AppShell({
  title,
  description,
  brief,
  breadcrumbs,
  mainClassName,
  fillViewport = false,
  children,
}: AppShellProps) {
  return (
    <div
      className={`overflow-x-clip bg-[var(--surface-canvas)] text-[var(--text-primary)] ${
        fillViewport
          ? "flex min-h-dvh flex-col xl:h-dvh xl:overflow-hidden"
          : "min-h-screen"
      }`}
    >
      <Sidebar />
      <div
        className={
          fillViewport
            ? "flex min-h-0 flex-1 flex-col pl-0 lg:pl-[17rem]"
            : "min-h-screen pl-0 lg:pl-[17rem]"
        }
      >
        <TopBar title={title} description={description} />
        <main
          className={
            mainClassName ??
            "mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8"
          }
        >

          {breadcrumbs && breadcrumbs.length > 0 && (
            <nav aria-label="面包屑" className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)]">
              {breadcrumbs.map((crumb, i) => (
                <span key={i} className="flex items-center gap-1.5">
                  {i > 0 && <ChevronRight size={12} aria-hidden="true" />}
                  {crumb.href ? (
                    <Link href={crumb.href} className="hover:text-[var(--text-primary)]">
                      {crumb.label}
                    </Link>
                  ) : (
                    <span className="text-[var(--text-primary)] font-medium">{crumb.label}</span>
                  )}
                </span>
              ))}
            </nav>
          )}

          {brief && (
            <p className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3 text-sm leading-relaxed text-[var(--text-secondary)]">
              {brief}
            </p>
          )}

          {children}
        </main>
      </div>
    </div>
  );
}
