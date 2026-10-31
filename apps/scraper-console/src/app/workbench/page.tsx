"use client";

import { Suspense, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowRight,
  Ban,
  CheckCircle,
  Clock,
  FolderKanban,
  ListChecks,
  Loader2,
  RefreshCw,
  Search,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { DOMAIN_LABELS } from "@/lib/api/projects";
import type { Project } from "@/lib/api/projects";
import type { CollectionTask } from "@/lib/api/tasks";
import { fetchWorkbenchSnapshot, previewWorkbenchPlan } from "@/lib/api/workbench";
import type { WorkbenchPlanDraft } from "@/lib/api/workbench";
import { AppShell } from "@/components/layout/app-shell";
import { hrefWithParams, mergeParams } from "@/lib/url-state";
import {
  buildWorkbenchSteps,
  currentStepKey,
  EVIDENCE_LEGEND,
  GATE_LEGEND,
  MISSING_WORKBENCH_ENDPOINTS,
  MISSING_WORKBENCH_ENDPOINT_LIST,
  readProjectParam,
  readQuestionParam,
  summarizeTasks,
  workbenchDataState,
} from "./state";
import type {
  WorkbenchDataState,
  WorkbenchReportSummary,
  WorkbenchRunSummary,
  WorkbenchStep,
  WorkbenchStepStatus,
} from "./state";

/** 轮询间隔。与运行页保持一致。 */
const REFETCH_INTERVAL_MS = 15_000;

/** 任务状态的中文名。 */
const TASK_STATUS_LABELS: Record<string, string> = {
  enabled: "已启用",
  running: "运行中",
  paused: "已暂停",
  disabled: "已禁用",
  draft: "草稿",
};

/** 步骤状态的图标、文字与配色。 */
const STEP_STATUS_META: Record<
  WorkbenchStepStatus,
  { label: string; icon: LucideIcon; text: string; badge: string }
> = {
  pending: {
    label: "待开始",
    icon: Clock,
    text: "text-[var(--text-tertiary)]",
    badge:
      "border-[var(--border-subtle)] bg-[var(--surface-muted)] text-[var(--text-secondary)]",
  },
  active: {
    label: "进行中",
    icon: Loader2,
    text: "text-[var(--state-info)]",
    badge:
      "border-[var(--border-subtle)] bg-[var(--accent-2-soft)] text-[var(--state-info)]",
  },
  done: {
    label: "已完成",
    icon: CheckCircle,
    text: "text-[var(--state-success)]",
    badge:
      "border-[var(--state-success)] bg-[var(--success-soft)] text-[var(--state-success)]",
  },
  blocked: {
    label: "被阻断",
    icon: Ban,
    text: "text-[var(--state-warning)]",
    badge:
      "border-[var(--state-warning)] bg-[var(--warning-soft)] text-[var(--state-warning)]",
  },
  failed: {
    label: "失败",
    icon: AlertCircle,
    text: "text-[var(--state-danger)]",
    badge:
      "border-[var(--state-danger)] bg-[var(--danger-soft)] text-[var(--state-danger)]",
  },
};

/** 格式化时间。无法解析时返回短横线。 */
function formatTime(value: string | null): string {
  if (value === null || value === "") return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { dateStyle: "short", timeStyle: "short" });
}

/** 截短 ID。只用于显示。 */
function shortId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id;
}

/** 把计划预览的失败转成用户可读的文案。 */
function planErrorMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : "未知错误";
  if (detail === "workbench_plans_preview_not_implemented") {
    return `计划预览接口未实现（${detail}）。后端缺 ${MISSING_WORKBENCH_ENDPOINTS.previewPlan}。`;
  }
  return `计划预览失败：${detail}`;
}

/* ─────────────────────────────────────────────────────────────
   Left rail
───────────────────────────────────────────────────────────── */

function LeftRail({
  projects,
  tasks,
  projectId,
  onSelectProject,
  taskSearch,
  onTaskSearchChange,
  isLoading,
  hasError,
}: {
  projects: Project[];
  tasks: CollectionTask[];
  projectId: string;
  onSelectProject: (value: string) => void;
  taskSearch: string;
  onTaskSearchChange: (value: string) => void;
  isLoading: boolean;
  hasError: boolean;
}) {
  const needle = taskSearch.trim().toLowerCase();
  const shownTasks =
    needle === ""
      ? tasks
      : tasks.filter(task => {
          const haystack = `${task.name} ${task.collector_type}`.toLowerCase();
          return haystack.includes(needle);
        });

  const skeletonRows = (
    <div className="mt-3 grid gap-1" aria-hidden="true">
      {[0, 1, 2].map(index => (
        <div
          key={index}
          className="h-9 animate-pulse rounded-[var(--radius-2)] bg-[var(--surface-muted)]"
        />
      ))}
    </div>
  );

  return (
    <aside
      aria-label="项目与任务"
      className="min-w-0 border-b border-[var(--border-subtle)] bg-[var(--surface-primary)] xl:h-full xl:overflow-y-auto xl:border-b-0 xl:border-r"
    >
      <section className="p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
            项目
          </h2>
          <Link
            href="/projects"
            className="text-xs font-medium text-[var(--action-primary)] hover:underline"
          >
            管理
          </Link>
        </div>
        {isLoading ? (
          skeletonRows
        ) : hasError ? (
          <p className="mt-3 px-1 text-xs text-[var(--state-danger)]">
            项目读取失败。
          </p>
        ) : projects.length === 0 ? (
          <p className="mt-3 rounded-[var(--radius-2)] border border-dashed border-[var(--border-subtle)] px-3 py-4 text-xs leading-relaxed text-[var(--text-tertiary)]">
            还没有项目。先创建一个项目。
          </p>
        ) : (
          <ul className="mt-3 grid gap-1">
            <li>
              <button
                type="button"
                onClick={() => onSelectProject("")}
                aria-pressed={projectId === ""}
                className={`flex w-full items-center gap-2 rounded-[var(--radius-2)] px-2.5 py-2 text-left text-sm ${
                  projectId === ""
                    ? "bg-[var(--accent-1-soft)] font-medium text-[var(--action-primary)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                }`}
              >
                <ListChecks size={14} aria-hidden="true" />
                全部项目
              </button>
            </li>
            {projects.map(project => (
              <li key={project.id}>
                <button
                  type="button"
                  onClick={() => onSelectProject(project.id)}
                  aria-pressed={projectId === project.id}
                  className={`flex w-full items-start gap-2 rounded-[var(--radius-2)] px-2.5 py-2 text-left ${
                    projectId === project.id
                      ? "bg-[var(--accent-1-soft)]"
                      : "hover:bg-[var(--surface-muted)]"
                  }`}
                >
                  <FolderKanban
                    size={14}
                    className="mt-0.5 shrink-0 text-[var(--text-tertiary)]"
                    aria-hidden="true"
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-[var(--text-primary)]">
                      {project.name}
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-[var(--text-tertiary)]">
                      {DOMAIN_LABELS[project.domain]}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="border-t border-[var(--border-subtle)] p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
            采集任务
          </h2>
          <span className="text-xs tabular-nums text-[var(--text-tertiary)]">
            {tasks.length}
          </span>
        </div>
        <label htmlFor="workbench-task-search" className="sr-only">
          搜索任务
        </label>
        <div className="relative mt-3">
          <Search
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]"
            aria-hidden="true"
          />
          <input
            id="workbench-task-search"
            type="search"
            value={taskSearch}
            onChange={event => onTaskSearchChange(event.target.value)}
            placeholder="搜索任务"
            className="h-9 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] pl-9 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
          />
        </div>
        {isLoading ? (
          skeletonRows
        ) : hasError ? (
          <p className="mt-3 px-1 text-xs text-[var(--state-danger)]">
            任务读取失败。
          </p>
        ) : tasks.length === 0 ? (
          <p className="mt-3 px-1 text-xs leading-relaxed text-[var(--text-tertiary)]">
            该项目还没有采集任务
          </p>
        ) : shownTasks.length === 0 ? (
          <p className="mt-3 px-1 text-xs leading-relaxed text-[var(--text-tertiary)]">
            没有匹配的任务
          </p>
        ) : (
          <ul className="mt-3 grid gap-1">
            {shownTasks.map(task => (
              <li
                key={task.id}
                className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2"
              >
                <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                  {task.name}
                </p>
                <p className="mt-0.5 truncate text-xs text-[var(--text-tertiary)]">
                  {task.collector_type} ·{" "}
                  {TASK_STATUS_LABELS[task.status] ?? task.status} · 最近{" "}
                  {formatTime(task.latest_run_started_at ?? task.last_run_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}

/* ─────────────────────────────────────────────────────────────
   Question form
───────────────────────────────────────────────────────────── */

function QuestionForm({
  question,
  onQuestionChange,
  projectId,
}: {
  question: string;
  onQuestionChange: (value: string) => void;
  projectId: string;
}) {
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [markets, setMarkets] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = question.trim() !== "" && projectId !== "" && !submitting;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (trimmed === "") return;
    if (projectId === "") {
      setError("先选择项目。");
      return;
    }
    setSubmitting(true);
    setError(null);
    const draft: WorkbenchPlanDraft = {
      project_id: projectId,
      decision_question: trimmed,
      brand: brand.trim(),
      category: category.trim(),
      markets: markets
        .split(",")
        .map(item => item.trim())
        .filter(item => item !== ""),
    };
    try {
      await previewWorkbenchPlan(draft);
      // 后端实现后在这里跳转 /workbench/[taskId]。
    } catch (err) {
      setError(planErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  function onQuestionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      aria-busy={submitting}
      className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5"
    >
      <h2 className="text-base font-bold text-[var(--text-primary)]">
        新建任务
      </h2>
      <p className="mt-1 text-xs leading-relaxed text-[var(--text-tertiary)]">
        先写决策问题。其余字段可以留空。
      </p>

      <div className="mt-4 grid gap-1.5">
        <label
          htmlFor="workbench-question"
          className="text-sm font-medium text-[var(--text-primary)]"
        >
          决策问题 <span className="text-[var(--state-danger)]">*</span>
        </label>
        <textarea
          id="workbench-question"
          value={question}
          onChange={event => onQuestionChange(event.target.value)}
          onKeyDown={onQuestionKeyDown}
          rows={3}
          required
          aria-describedby="workbench-question-hint"
          placeholder="例：Fit 与支撑，哪个是主要摩擦？"
          className="w-full resize-y rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm leading-relaxed text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
        />
        <p
          id="workbench-question-hint"
          className="text-xs text-[var(--text-tertiary)]"
        >
          Cmd/Ctrl+Enter 提交。
        </p>
      </div>

      <details className="mt-3 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2">
        <summary className="cursor-pointer text-xs font-medium text-[var(--text-secondary)]">
          更多设置
        </summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div className="grid gap-1.5">
            <label
              htmlFor="workbench-brand"
              className="text-xs font-medium text-[var(--text-secondary)]"
            >
              品牌
            </label>
            <input
              id="workbench-brand"
              value={brand}
              onChange={event => setBrand(event.target.value)}
              placeholder="如：Momcozy"
              className="h-9 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
            />
          </div>
          <div className="grid gap-1.5">
            <label
              htmlFor="workbench-category"
              className="text-xs font-medium text-[var(--text-secondary)]"
            >
              品类
            </label>
            <input
              id="workbench-category"
              value={category}
              onChange={event => setCategory(event.target.value)}
              placeholder="如：吸奶器"
              className="h-9 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
            />
          </div>
          <div className="grid gap-1.5">
            <label
              htmlFor="workbench-markets"
              className="text-xs font-medium text-[var(--text-secondary)]"
            >
              市场
            </label>
            <input
              id="workbench-markets"
              value={markets}
              onChange={event => setMarkets(event.target.value)}
              placeholder="逗号分隔，如：US, DE"
              className="h-9 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
            />
          </div>
        </div>
      </details>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={!canSubmit}
          className="inline-flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-medium text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? (
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <ArrowRight size={14} aria-hidden="true" />
          )}
          生成计划
        </button>
        <p className="text-xs text-[var(--text-tertiary)]">
          {projectId === ""
            ? "先选择项目。"
            : question.trim() === ""
              ? "填入决策问题后提交。"
              : "提交后调用计划预览端点。"}
        </p>
      </div>

      {error !== null ? (
        <p
          role="alert"
          className="mt-3 rounded-[var(--radius-2)] border border-[var(--state-danger)] bg-[var(--danger-soft)] px-3 py-2 text-xs leading-relaxed text-[var(--state-danger)]"
        >
          {error}
        </p>
      ) : null}
    </form>
  );
}

/* ─────────────────────────────────────────────────────────────
   Data state + steps
───────────────────────────────────────────────────────────── */

function DataStateBlock({
  state,
  errorMessage,
  onRetry,
  isFetching,
}: {
  state: WorkbenchDataState;
  errorMessage: string;
  onRetry: () => void;
  isFetching: boolean;
}) {
  if (state === "loading") {
    return (
      <div>
        <p className="sr-only">正在加载工作台数据。</p>
        <div className="grid gap-3" aria-hidden="true">
          <div className="h-20 animate-pulse rounded-[var(--radius-3)] bg-[var(--surface-muted)]" />
          <div className="h-20 animate-pulse rounded-[var(--radius-3)] bg-[var(--surface-muted)]" />
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div
        role="alert"
        className="rounded-[var(--radius-3)] border border-[var(--state-danger)] bg-[var(--danger-soft)] p-5 text-sm text-[var(--state-danger)]"
      >
        <p className="font-semibold">工作台数据加载失败。</p>
        <p className="mt-1 break-all text-xs">{errorMessage}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--state-danger)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--surface-primary)]"
        >
          {isFetching ? (
            <Loader2 size={12} className="animate-spin" aria-hidden="true" />
          ) : (
            <RefreshCw size={12} aria-hidden="true" />
          )}
          重试
        </button>
      </div>
    );
  }

  if (state === "empty") {
    return (
      <div className="rounded-[var(--radius-3)] border border-dashed border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
        <p className="text-sm font-semibold text-[var(--text-primary)]">
          还没有数据。
        </p>
        <p className="mt-1 text-xs leading-relaxed text-[var(--text-tertiary)]">
          先创建一个项目，再发起一次采集。
        </p>
        <Link
          href="/projects"
          className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-[var(--action-primary)] hover:underline"
        >
          去创建项目 <ArrowRight size={12} aria-hidden="true" />
        </Link>
      </div>
    );
  }

  return null;
}

function StepList({ steps }: { steps: WorkbenchStep[] }) {
  const activeKey = currentStepKey(steps);
  return (
    <ol aria-label="工作台五步流程" className="grid gap-2.5">
      {steps.map((step, index) => {
        const meta = STEP_STATUS_META[step.status];
        const Icon = meta.icon;
        const current = step.key === activeKey;
        return (
          <li
            key={step.key}
            aria-current={current ? "step" : undefined}
            className={`rounded-[var(--radius-3)] border bg-[var(--surface-primary)] p-4 ${
              current
                ? "border-[var(--action-primary)]"
                : "border-[var(--border-subtle)]"
            }`}
          >
            <div className="flex items-start gap-3">
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold tabular-nums ${meta.badge}`}
                aria-hidden="true"
              >
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <h3 className="text-sm font-bold text-[var(--text-primary)]">
                    {step.title}
                  </h3>
                  <span
                    className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${meta.badge}`}
                  >
                    <Icon
                      size={11}
                      className={step.status === "active" ? "animate-spin" : ""}
                      aria-hidden="true"
                    />
                    {meta.label}
                  </span>
                  <span className="ml-auto text-[11px] text-[var(--text-tertiary)]">
                    门禁 {step.gate}
                  </span>
                </div>
                <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-secondary)]">
                  {step.detail}
                </p>
                <p className="mt-1 break-all font-mono text-[11px] text-[var(--text-tertiary)]">
                  {step.source}
                </p>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function LatestActivity({
  latestRun,
  latestReport,
}: {
  latestRun: WorkbenchRunSummary | null;
  latestReport: WorkbenchReportSummary | null;
}) {
  return (
    <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
      <h2 className="text-base font-bold text-[var(--text-primary)]">最近活动</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
            最近运行
          </p>
          {latestRun === null ? (
            <p className="mt-1 text-sm text-[var(--text-tertiary)]">暂无运行</p>
          ) : (
            <Link
              href={`/runs/${latestRun.id}`}
              className="mt-1 block truncate text-sm font-medium text-[var(--action-primary)] hover:underline"
            >
              {shortId(latestRun.id)} · {latestRun.status} ·{" "}
              {latestRun.records_count} 条记录
            </Link>
          )}
        </div>
        <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
            最近报告
          </p>
          {latestReport === null ? (
            <p className="mt-1 text-sm text-[var(--text-tertiary)]">暂无报告</p>
          ) : (
            <p className="mt-1 truncate text-sm font-medium text-[var(--text-primary)]">
              {latestReport.title} · {latestReport.status}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────
   Right rail
───────────────────────────────────────────────────────────── */

function RightRail() {
  return (
    <aside
      aria-label="门禁与成本说明"
      className="min-w-0 space-y-5 border-t border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4 xl:h-full xl:overflow-y-auto xl:border-l xl:border-t-0"
    >
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          门禁说明
        </h2>
        <ul className="mt-3 grid gap-2">
          {GATE_LEGEND.map(gate => (
            <li
              key={gate.id}
              className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2"
            >
              <p className="font-mono text-xs font-semibold text-[var(--text-primary)]">
                {gate.id}
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-[var(--text-tertiary)]">
                {gate.description}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          证据等级
        </h2>
        <ul className="mt-3 grid gap-1.5">
          {EVIDENCE_LEGEND.map(item => (
            <li
              key={item.grade}
              className="flex items-baseline justify-between gap-2 text-xs"
            >
              <span className="text-[var(--text-secondary)]">{item.label}</span>
              <span className="shrink-0 font-mono text-[11px] text-[var(--text-tertiary)]">
                {item.claim}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          成本口径
        </h2>
        <p className="mt-2 text-xs leading-relaxed text-[var(--text-tertiary)]">
          已发生成本取运行的 total_cost_usd。计划估算需要{" "}
          {MISSING_WORKBENCH_ENDPOINTS.previewPlan}（未实现）。
        </p>
      </section>

      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          后端缺口
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-[var(--text-tertiary)]">
          下列端点尚未挂载。页面不臆造路径，也不显示假数据。
        </p>
        <ul className="mt-2 grid gap-1">
          {MISSING_WORKBENCH_ENDPOINT_LIST.map(endpoint => (
            <li
              key={endpoint}
              className="break-all rounded-[var(--radius-1)] bg-[var(--surface-muted)] px-2 py-1 font-mono text-[11px] text-[var(--text-secondary)]"
            >
              {endpoint}
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}

/* ─────────────────────────────────────────────────────────────
   Page
───────────────────────────────────────────────────────────── */

function WorkbenchContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const projectId = readProjectParam(searchParams);
  const [question, setQuestion] = useState(() => readQuestionParam(searchParams));
  const [taskSearch, setTaskSearch] = useState("");

  const query = useQuery({
    queryKey: ["workbench", projectId === "" ? "all" : projectId],
    queryFn: () => fetchWorkbenchSnapshot(projectId === "" ? undefined : projectId),
    refetchInterval: REFETCH_INTERVAL_MS,
  });

  const snapshot = query.data ?? null;
  const projects = snapshot?.projects ?? [];
  const tasks = snapshot?.tasks ?? [];
  const latestRun: WorkbenchRunSummary | null =
    snapshot !== null && snapshot.runs.length > 0 ? snapshot.runs[0] : null;
  const latestReport: WorkbenchReportSummary | null =
    snapshot !== null && snapshot.reports.length > 0
      ? snapshot.reports[0]
      : null;
  const summary = summarizeTasks(tasks);

  const steps = buildWorkbenchSteps({ question, latestRun, latestReport });
  const hasData =
    snapshot !== null &&
    snapshot.projects.length +
      snapshot.tasks.length +
      snapshot.runs.length +
      snapshot.reports.length >
      0;
  const viewState = workbenchDataState({
    isLoading: query.isLoading,
    hasError: query.isError,
    hasData,
  });
  const errorMessage =
    query.error instanceof Error ? query.error.message : "未知错误";

  function onProjectChange(value: string) {
    const next = mergeParams(new URLSearchParams(searchParams.toString()), {
      project: value === "" ? null : value,
    });
    router.replace(hrefWithParams(pathname, next), { scroll: false });
  }

  return (
    <AppShell
      title="工作台"
      description="选择项目，从问题走到报告。"
      fillViewport
      mainClassName="mx-auto grid min-h-0 w-full max-w-[1600px] flex-1 xl:grid-cols-[17.5rem_minmax(0,1fr)_22.5rem]"
    >
      <LeftRail
        projects={projects}
        tasks={tasks}
        projectId={projectId}
        onSelectProject={onProjectChange}
        taskSearch={taskSearch}
        onTaskSearchChange={setTaskSearch}
        isLoading={query.isLoading}
        hasError={query.isError}
      />

      <section
        aria-label="五步流程"
        aria-busy={query.isLoading}
        className="min-w-0 space-y-5 px-4 py-6 sm:px-6 xl:h-full xl:overflow-y-auto xl:border-r xl:border-[var(--border-subtle)]"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-[var(--text-primary)]">
              从问题到报告
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
              五步流程。每步状态来自后端接口。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label
              htmlFor="workbench-project"
              className="shrink-0 text-xs font-medium text-[var(--text-tertiary)]"
            >
              项目
            </label>
            <select
              id="workbench-project"
              value={projectId}
              onChange={event => onProjectChange(event.target.value)}
              className="h-9 max-w-[13rem] rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-2 text-sm text-[var(--text-primary)]"
            >
              <option value="">全部项目</option>
              {projects.map(project => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
            <p className="hidden text-xs tabular-nums text-[var(--text-tertiary)] md:block">
              任务 {summary.total} · 启用 {summary.enabled}
            </p>
            <button
              type="button"
              onClick={() => void query.refetch()}
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            >
              {query.isFetching ? (
                <Loader2 size={12} className="animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw size={12} aria-hidden="true" />
              )}
              刷新
            </button>
          </div>
        </div>

        <QuestionForm
          question={question}
          onQuestionChange={setQuestion}
          projectId={projectId}
        />

        <DataStateBlock
          state={viewState}
          errorMessage={errorMessage}
          onRetry={() => void query.refetch()}
          isFetching={query.isFetching}
        />

        <StepList steps={steps} />

        {viewState === "ready" ? (
          <LatestActivity latestRun={latestRun} latestReport={latestReport} />
        ) : null}
      </section>

      <RightRail />
    </AppShell>
  );
}

/** 页面骨架。`useSearchParams` 需要 Suspense 边界。 */
function WorkbenchFallback() {
  return (
    <AppShell
      title="工作台"
      description="选择项目，从问题走到报告。"
      fillViewport
      mainClassName="mx-auto flex min-h-0 w-full max-w-[1600px] flex-1 items-center justify-center px-6 py-24"
    >
      <p className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
        <Loader2 size={16} className="animate-spin" aria-hidden="true" />
        正在加载工作台。
      </p>
    </AppShell>
  );
}

export default function WorkbenchPage() {
  return (
    <Suspense fallback={<WorkbenchFallback />}>
      <WorkbenchContent />
    </Suspense>
  );
}
