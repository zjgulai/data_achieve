export function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-5 py-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
        {label}
      </p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-[var(--text-primary)]">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">{hint}</p> : null}
    </div>
  );
}
