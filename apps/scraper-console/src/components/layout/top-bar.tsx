type TopBarProps = {
  title: string;
  description?: string;
};

export function TopBar({ title, description }: TopBarProps) {
  // A "命令搜索 ⌘K" button used to sit here with no click handler. It was
  // removed rather than left as a dead affordance; a real command palette is a
  // separate piece of work.
  return (
    <header className="border-b border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-4 sm:px-6 lg:px-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[var(--text-primary)]">
            {title}
          </h1>
          {description && (
            <p className="mt-1 text-sm text-[var(--text-tertiary)]">
              {description}
            </p>
          )}
        </div>
      </div>
    </header>
  );
}
