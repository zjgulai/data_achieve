type TopBarProps = {
  title: string;
  description?: string;
};

export function TopBar({ title, description }: TopBarProps) {
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
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)]"
          >
            命令搜索 ⌘K
          </button>
        </div>
      </div>
    </header>
  );
}
