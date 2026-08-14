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
  {
    href: "/automation/plans",
    title: "已保存计划",
    description: "按当前 Project 查看不可变 Version 历史与结构化比较。",
  },
] as const;

export function WorkflowPlannerEntryCards() {
  return (
    <section
      aria-labelledby="workflow-planner-entry-heading"
      className="min-w-0 rounded-2xl border border-[#E9E5E2] bg-[#FFFDFC] p-4 sm:p-5"
      data-testid="workflow-planner-entry-cards"
    >
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9A7467]">
          Workflow Planner
        </p>
        <h2
          className="mt-2 text-xl font-semibold text-[#2E201C]"
          id="workflow-planner-entry-heading"
        >
          从业务输入生成采集计划预览
        </h2>
        <p className="mt-2 text-sm leading-6 text-[#716562]">
          阶段二支持显式保存不可变 WorkflowPlan Version，并保留可审阅历史。
        </p>
      </div>
      <div className="mt-4 grid min-w-0 gap-3 md:grid-cols-3">
        {plannerEntries.map((entry) => (
          <Link
            className="group min-w-0 rounded-2xl border border-[#E8DDD6] bg-white p-4 transition-colors hover:border-[#C97865] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#9F4E3D]"
            href={entry.href as Route}
            key={entry.href}
          >
            <span className="block font-semibold text-[#392823] group-hover:text-[#8A4436]">
              {entry.title}
            </span>
            <span className="mt-2 block text-sm leading-6 text-[#716562]">
              {entry.description}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
