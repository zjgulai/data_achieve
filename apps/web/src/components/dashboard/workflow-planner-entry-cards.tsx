import Link from "next/link";
import type { Route } from "next";

const plannerEntries = [
  {
    href: "/automation/planner?mode=periodic_monitoring",
    title: "创建监测项目",
    description: "配置品牌、品类、竞品、平台与周期，生成可解释计划。",
  },
  {
    href: "/automation/planner?mode=batch_research",
    title: "批量检索与解析",
    description: "输入关键词与 Seed URL，预览跨平台查询和解析路线。",
  },
] as const;

export function WorkflowPlannerEntryCards() {
  return (
    <section
      aria-labelledby="workflow-planner-entry-heading"
      className="min-w-0 rounded-[var(--radius-4)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4 sm:p-5"
      data-testid="workflow-planner-entry-cards"
    >
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--action-primary)]">
          Choose a job
        </p>
        <h2
          className="mt-2 text-xl font-semibold text-[var(--text-primary)]"
          id="workflow-planner-entry-heading"
        >
          先选择今天要完成的工作
        </h2>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          两条主路径都只生成可审阅 Preview；保存与执行仍是独立动作。
        </p>
      </div>
      <div className="mt-4 grid min-w-0 gap-3 md:grid-cols-2">
        {plannerEntries.map((entry, index) => (
          <Link
            className="group min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4 transition-colors duration-[var(--duration-base)] hover:border-[var(--action-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
            href={entry.href as Route}
            key={entry.href}
          >
            <span className="text-xs font-semibold text-[var(--action-primary)]">
              0{index + 1}
            </span>
            <span className="mt-2 block font-semibold text-[var(--text-primary)] group-hover:text-[var(--action-primary)]">
              {entry.title}
            </span>
            <span className="mt-2 block text-sm leading-6 text-[var(--text-secondary)]">
              {entry.description}
            </span>
          </Link>
        ))}
      </div>
      <div className="mt-4 flex flex-col gap-2 border-t border-[var(--border-subtle)] pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-[var(--text-tertiary)]">
          继续已有工作？按当前 Project 查看版本历史。
        </p>
        <Link
          className="inline-flex min-h-[var(--touch-target)] items-center justify-center rounded-[var(--radius-2)] border border-[var(--border-strong)] px-3 text-sm font-semibold text-[var(--action-primary)] hover:border-[var(--action-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
          href="/automation/plans"
        >
          查看已保存计划
        </Link>
      </div>
    </section>
  );
}
