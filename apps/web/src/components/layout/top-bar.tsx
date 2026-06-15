import { GlobalSearch } from "@/components/layout/global-search";

type TopBarProps = {
  title: string;
  description: string;
};

export function TopBar({ title, description }: TopBarProps) {
  return (
    <header className="border-b border-[#E9E5E2] bg-white/95">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-[#1D1D1F]">
            {title}
          </h1>
          <p className="mt-1 text-sm text-[#86868B]">{description}</p>
        </div>
        <GlobalSearch />
      </div>
    </header>
  );
}
