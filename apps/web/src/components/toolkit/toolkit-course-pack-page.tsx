"use client";

import {
  AlertCircle,
  ArrowLeft,
  BookOpenCheck,
  CheckCircle2,
  ExternalLink,
  Link2,
  Loader2,
  Printer,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getToolkitOverview } from "@/lib/api/toolkit";
import type { ToolkitLecturePlaybook, ToolkitOverview } from "@/types/toolkit";

export function ToolkitCoursePackPage() {
  const [overview, setOverview] = useState<ToolkitOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    let mounted = true;
    getToolkitOverview()
      .then((nextOverview) => {
        if (mounted) {
          setOverview(nextOverview);
          setError(null);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setOverview(null);
          setError(caught instanceof Error ? caught.message : "课程包 API 暂不可用");
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  const playbooks = useMemo(
    () => overview?.lecturePlaybooks ?? [],
    [overview?.lecturePlaybooks],
  );
  const totalMinutes = useMemo(
    () => playbooks.reduce((sum, playbook) => sum + playbook.durationMinutes, 0),
    [playbooks],
  );
  const totalEvidence = useMemo(
    () => playbooks.reduce((sum, playbook) => sum + playbook.evidenceCount, 0),
    [playbooks],
  );

  async function copyCoursePackLink() {
    try {
      await copyTextToClipboard(window.location.href);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1600);
    } catch {
      setCopyState("failed");
    }
  }

  if (error) {
    return (
      <StatusCard
        body="无法加载课程包。先确认登录状态和 API 健康状态，再刷新本页。"
        icon={AlertCircle}
        tone="error"
        title={error}
      />
    );
  }

  if (!overview) {
    return (
      <StatusCard
        body="正在读取最新工具库情报、讲义结构和证据快照。"
        icon={Loader2}
        title="课程包加载中"
      />
    );
  }

  return (
    <article className="printable-course-pack min-w-0 rounded-2xl border border-[#E9E5E2] bg-white p-5 print:rounded-none print:border-0 print:p-0">
      <CoursePackPrintStyles />

      <div className="mb-5 flex flex-col gap-3 print:hidden sm:flex-row sm:items-center sm:justify-between">
        <a
          className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm font-semibold text-[#7A625A] transition hover:border-[#C25B6E] hover:text-[#A24D61]"
          href="/toolkit"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          返回工具库
        </a>
        <div className="flex flex-wrap gap-2">
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm font-semibold text-[#7A625A] transition hover:border-[#C25B6E] hover:text-[#A24D61]"
            onClick={() => void copyCoursePackLink()}
            type="button"
          >
            <Link2 size={16} aria-hidden="true" />
            {copyState === "copied" ? "已复制" : "复制课程包链接"}
          </button>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#C25B6E] bg-[#C25B6E] px-3 text-sm font-semibold text-white transition hover:bg-[#A24D61]"
            onClick={() => window.print()}
            type="button"
          >
            <Printer size={16} aria-hidden="true" />
            打印全量讲义
          </button>
        </div>
      </div>

      {copyState === "failed" ? (
        <p className="mb-4 rounded-xl border border-[#F0C9C2] bg-[#FFF5F2] px-3 py-2 text-xs font-semibold text-[#A04437] print:hidden">
          复制失败，请直接使用浏览器地址栏链接。
        </p>
      ) : null}

      <header className="border-b border-[#EDE6DF] pb-5 print:border-[#D6D6D6]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-[#E6D3CE] bg-[#FFF8F6] px-3 py-1 text-xs font-semibold text-[#A24D61] print:border-[#D6D6D6] print:bg-white print:text-black">
                {formatDate(overview.metrics.lastCollectedAt)} 快照
              </span>
              <span className="rounded-full border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-1 text-xs font-semibold text-[#7A625A] print:border-[#D6D6D6] print:bg-white print:text-black">
                可打印课程包
              </span>
            </div>
            <h2 className="text-2xl font-semibold leading-8 text-[#1D1D1F] print:text-2xl print:text-black">
              数据采集工具与平台方法培训课程包
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[#5F5757] print:text-[13px] print:text-black">
              这份课程包把 14 张讲义按培训交付形态串起来，覆盖 AI 原生采集工具、浏览器自动化、Agent/MCP、GitHub API、平台方法和合规边界。
            </p>
          </div>
          <div className="grid min-w-[260px] grid-cols-2 gap-2 text-sm print:grid-cols-4">
            <CourseMetric label="讲义" value={`${playbooks.length} 张`} />
            <CourseMetric label="课时" value={`${totalMinutes} 分钟`} />
            <CourseMetric label="证据" value={`${totalEvidence} 条`} />
            <CourseMetric label="来源" value={`${overview.metrics.sourceCount} 个`} />
          </div>
        </div>
      </header>

      <section className="mt-5 grid gap-4 lg:grid-cols-3 print:grid-cols-1">
        {[
          "识别公开来源、官方 API、浏览器采集和 Agent 工具调用的适用边界。",
          "掌握高质量工具安装、验收、证据留存和风险复核的 SOP。",
          "把 GitHub、官方文档、电商、社媒、竞品站点沉淀成可复用采集方法卡。",
        ].map((goal) => (
          <div
            className="rounded-xl border border-[#EDE6DF] bg-[#FFFDFC] p-4 print:border-[#D6D6D6] print:bg-white"
            key={goal}
          >
            <CheckCircle2
              size={17}
              className="mb-2 text-[#6B8E5A] print:hidden"
              aria-hidden="true"
            />
            <p className="text-sm leading-6 text-[#5F5757] print:text-[13px] print:text-black">
              {goal}
            </p>
          </div>
        ))}
      </section>

      <section className="mt-6">
        <div className="mb-4 flex items-center gap-2">
          <BookOpenCheck size={18} className="text-[#C25B6E] print:hidden" aria-hidden="true" />
          <h3 className="text-lg font-semibold text-[#1D1D1F] print:text-black">
            课程包目录
          </h3>
        </div>
        <div className="grid gap-3 lg:grid-cols-2 print:grid-cols-1">
          {playbooks.map((playbook, index) => (
            <a
              className="rounded-xl border border-[#EDE6DF] bg-[#FFFDFC] p-4 transition hover:border-[#C25B6E] print:border-[#D6D6D6] print:bg-white"
              href={`/toolkit/playbooks/${playbook.id}`}
              key={playbook.id}
            >
              <div className="flex items-start gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#FBF8F5] text-sm font-semibold text-[#C25B6E] print:border print:border-[#D6D6D6] print:bg-white print:text-black">
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <h4 className="line-clamp-2 text-sm font-semibold leading-5 text-[#1D1D1F] print:text-black">
                    {playbook.title}
                  </h4>
                  <p className="mt-2 text-xs leading-5 text-[#5F5757] print:text-black">
                    {playbook.level} · {playbook.durationMinutes} 分钟 ·{" "}
                    {playbook.evidenceCount} 条证据
                  </p>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#86868B] print:text-black">
                    {playbook.claim}
                  </p>
                </div>
                <ExternalLink size={14} className="mt-1 shrink-0 text-[#C25B6E] print:hidden" />
              </div>
            </a>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <h3 className="mb-4 text-lg font-semibold text-[#1D1D1F] print:text-black">
          全量讲义
        </h3>
        <div className="grid gap-6">
          {playbooks.map((playbook, index) => (
            <CourseLesson
              index={index}
              key={playbook.id}
              playbook={playbook}
              snapshotLabel={`${formatDate(overview.metrics.lastCollectedAt)} 快照`}
            />
          ))}
        </div>
      </section>
    </article>
  );
}

function CourseLesson({
  playbook,
  index,
  snapshotLabel,
}: {
  playbook: ToolkitLecturePlaybook;
  index: number;
  snapshotLabel: string;
}) {
  return (
    <section className="course-pack-lesson rounded-2xl border border-[#E9E5E2] bg-white p-5 print:rounded-none print:border-[#D6D6D6] print:p-0 print:pt-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-[#EDE6DF] bg-[#FBF8F5] px-2.5 py-1 text-[11px] font-semibold text-[#7A625A] print:border-[#D6D6D6] print:bg-white print:text-black">
              第 {index + 1} 讲
            </span>
            <span className="rounded-full border border-[#F1D9A8] bg-[#FFF9E9] px-2.5 py-1 text-[11px] font-semibold text-[#87611B] print:border-[#D6D6D6] print:bg-white print:text-black">
              {playbook.durationMinutes} 分钟
            </span>
            <span className="rounded-full border border-[#E6D3CE] bg-[#FFF8F6] px-2.5 py-1 text-[11px] font-semibold text-[#A24D61] print:border-[#D6D6D6] print:bg-white print:text-black">
              {playbook.evidenceCount} 条证据
            </span>
            <span className="rounded-full border border-[#EDE6DF] bg-white px-2.5 py-1 text-[11px] font-semibold text-[#7A625A] print:border-[#D6D6D6] print:text-black">
              {snapshotLabel}
            </span>
          </div>
          <h4 className="text-xl font-semibold leading-7 text-[#1D1D1F] print:text-xl print:text-black">
            {playbook.title}
          </h4>
          <p className="mt-2 text-sm leading-6 text-[#5F5757] print:text-[13px] print:text-black">
            {playbook.claim}
          </p>
          <p className="mt-3 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-xs leading-5 text-[#7A625A] print:border-[#D6D6D6] print:bg-white print:text-black">
            适用人群：{playbook.audience}
          </p>
        </div>
        <a
          className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm font-semibold text-[#7A625A] transition hover:border-[#C25B6E] hover:text-[#A24D61] print:hidden"
          href={`/toolkit/playbooks/${playbook.id}`}
        >
          单讲页
          <ExternalLink size={14} aria-hidden="true" />
        </a>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2 print:grid-cols-1">
        <CourseList title="讲解顺序" items={playbook.teachingSequence} />
        <CourseList title="实操步骤" items={playbook.handsOnSteps} />
        <CourseList title="验收步骤" items={playbook.verificationSteps} />
        <CourseList title="风险边界" items={playbook.riskBoundaries} warning />
      </div>

      <div className="mt-5 rounded-xl border border-[#F1D9A8] bg-[#FFF9E9] p-4 print:border-[#D6D6D6] print:bg-white">
        <p className="text-xs font-semibold uppercase text-[#8C6824] print:text-black">
          课堂练习
        </p>
        <p className="mt-2 text-sm leading-6 text-[#87611B] print:text-[13px] print:text-black">
          {playbook.classroomExercise}
        </p>
      </div>

      <div className="mt-5 border-t border-[#EDE6DF] pt-4 print:border-[#D6D6D6]">
        <p className="mb-2 text-xs font-semibold uppercase text-[#B47767] print:text-black">
          讲义证据
        </p>
        <div className="grid gap-2 print:text-[11px]">
          {playbook.evidenceUrls.slice(0, 6).map((url, evidenceIndex) => (
            <a
              className="inline-flex min-w-0 items-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-xs font-semibold text-[#7A625A] transition hover:border-[#C25B6E] hover:text-[#A24D61] print:block print:border-0 print:bg-white print:px-0 print:py-0.5 print:text-black"
              href={url}
              key={url}
              rel="noreferrer"
              target="_blank"
            >
              <span className="truncate print:whitespace-normal">
                证据 {evidenceIndex + 1}：{url}
              </span>
              <ExternalLink size={13} className="shrink-0 print:hidden" aria-hidden="true" />
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}

function CourseList({
  title,
  items,
  warning = false,
}: {
  title: string;
  items: string[];
  warning?: boolean;
}) {
  return (
    <div className="rounded-xl border border-[#EDE6DF] bg-[#FFFDFC] p-4 print:border-[#D6D6D6] print:bg-white">
      <p className="mb-2 text-sm font-semibold text-[#1D1D1F] print:text-black">{title}</p>
      <ol className="grid gap-2 text-sm leading-6 text-[#5F5757] print:text-[13px] print:text-black">
        {items.map((item, index) => (
          <li className="flex gap-2" key={item}>
            <span
              className={
                warning
                  ? "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#FFF5F2] text-[11px] font-semibold text-[#A04437] print:border print:border-[#D6D6D6] print:bg-white print:text-black"
                  : "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#F5FBF3] text-[11px] font-semibold text-[#44743E] print:border print:border-[#D6D6D6] print:bg-white print:text-black"
              }
            >
              {index + 1}
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function CourseMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 print:border-[#D6D6D6] print:bg-white">
      <p className="text-[11px] font-semibold uppercase text-[#B47767] print:text-black">
        {label}
      </p>
      <p className="mt-1 truncate text-sm font-semibold text-[#1D1D1F] print:text-black">
        {value}
      </p>
    </div>
  );
}

function StatusCard({
  title,
  body,
  icon: Icon,
  tone = "neutral",
}: {
  title: string;
  body: string;
  icon: typeof Loader2;
  tone?: "neutral" | "error";
}) {
  return (
    <div className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
      <div className="flex items-start gap-3">
        <span
          className={
            tone === "error"
              ? "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#FFF5F2] text-[#A04437]"
              : "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#FFF8F6] text-[#C25B6E]"
          }
        >
          <Icon size={19} aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-base font-semibold text-[#1D1D1F]">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-[#5F5757]">{body}</p>
        </div>
      </div>
    </div>
  );
}

function CoursePackPrintStyles() {
  return (
    <style jsx global>{`
      @media print {
        @page {
          margin: 12mm;
        }

        body {
          background: #ffffff !important;
        }

        body * {
          visibility: hidden;
        }

        .printable-course-pack,
        .printable-course-pack * {
          visibility: visible;
        }

        .printable-course-pack {
          position: absolute;
          inset: 0 auto auto 0;
          width: 100%;
        }

        .course-pack-lesson {
          break-inside: avoid;
          page-break-inside: avoid;
        }

        .course-pack-lesson + .course-pack-lesson {
          break-before: page;
          page-break-before: always;
        }
      }
    `}</style>
  );
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "未核验";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value.slice(0, 10);
  }
  return parsed.toISOString().slice(0, 10);
}

async function copyTextToClipboard(value: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      // Fall through to the textarea copy path when browser permissions block Clipboard API.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}
