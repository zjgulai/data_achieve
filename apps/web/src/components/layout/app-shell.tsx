import { Suspense } from "react";

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
    <div className="min-h-screen overflow-x-clip bg-[#F7F0EB] text-[#231A1A]">
      <Suspense fallback={null}>
        <Sidebar />
      </Suspense>
      <div className="min-h-screen pl-0 lg:pl-72">
        <TopBar title={title} description={description} />
        <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
          {brief ? (
            <section className="min-w-0 rounded-2xl border border-[#E9E5E2] bg-[#FFFDFC] px-4 py-3 sm:px-5">
              <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <p className="min-w-0 text-sm leading-6 text-[#5F5757]">
                  {brief}
                </p>
                {signals.length > 0 ? (
                  <div className="flex shrink-0 flex-wrap gap-2">
                    {signals.map((signal) => (
                      <span
                        className="rounded-full border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-1 text-xs font-semibold text-[#7A625A]"
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
  );
}
