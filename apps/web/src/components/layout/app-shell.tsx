import { Suspense } from "react";

import { ProjectSelectionProvider } from "@/components/layout/project-selection-provider";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";

type AppShellProps = {
  title: string;
  description: string;
  brief?: string;
  signals?: readonly string[];
  children: React.ReactNode;
};

export function AppShell({
  title,
  description,
  brief,
  signals = [],
  children,
}: AppShellProps) {
  return (
    <ProjectSelectionProvider>
      <div className="min-h-screen overflow-x-clip bg-[var(--surface-canvas)] text-[var(--text-primary)]">
        <Suspense fallback={null}>
          <Sidebar />
        </Suspense>
        <div className="min-h-screen pl-0 lg:pl-[var(--sidebar-width)]">
          <TopBar title={title} description={description} />
          <main className="mx-auto flex w-full max-w-[var(--content-max)] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
            {brief ? (
              <section
                aria-label="页面上下文"
                className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3 sm:px-5"
              >
                <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <p className="min-w-0 text-sm leading-6 text-[var(--text-secondary)]">
                    {brief}
                  </p>
                  {signals.length > 0 ? (
                    <div className="flex shrink-0 flex-wrap gap-2">
                      {signals.map((signal) => (
                        <span
                          className="rounded-full border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-semibold text-[var(--text-secondary)]"
                          key={signal}
                        >
                          {signal}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}
            {children}
          </main>
        </div>
      </div>
    </ProjectSelectionProvider>
  );
}
