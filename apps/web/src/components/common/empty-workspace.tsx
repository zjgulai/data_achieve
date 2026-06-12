type EmptyWorkspaceProps = {
  title: string;
  detail: string;
};

export function EmptyWorkspace({ title, detail }: EmptyWorkspaceProps) {
  return (
    <section className="rounded-lg border border-[#dfe3ea] bg-white p-8">
      <div className="max-w-2xl">
        <p className="text-sm font-semibold uppercase tracking-[0.1em] text-[#0f766e]">
          Empty state
        </p>
        <h2 className="mt-3 text-xl font-semibold">{title}</h2>
        <p className="mt-3 text-sm leading-6 text-[#6b7280]">{detail}</p>
      </div>
    </section>
  );
}
