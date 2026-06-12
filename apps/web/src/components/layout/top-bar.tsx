import { Search } from "lucide-react";

type TopBarProps = {
  title: string;
  description: string;
};

export function TopBar({ title, description }: TopBarProps) {
  return (
    <header className="border-b border-[#dfe3ea] bg-white">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div>
          <h1 className="text-xl font-semibold">{title}</h1>
          <p className="mt-1 text-sm text-[#6b7280]">{description}</p>
        </div>
        <label className="flex w-full max-w-sm items-center gap-2 rounded-md border border-[#dfe3ea] bg-[#f7f8fa] px-3 py-2 text-sm">
          <Search size={17} className="text-[#6b7280]" aria-hidden="true" />
          <input
            className="w-full border-0 bg-transparent outline-none"
            placeholder="搜索项目、实体、情报"
            type="search"
          />
        </label>
      </div>
    </header>
  );
}
