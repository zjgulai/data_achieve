"use client";

import {
  ArrowLeft,
  BookOpenCheck,
  ExternalLink,
  Link2,
  Printer,
} from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";
import type { ToolkitLecturePlaybook } from "@/types/toolkit";

type LecturePlaybookDetailProps = {
  playbook: ToolkitLecturePlaybook;
  detailHref?: string;
  backHref?: string;
  snapshotLabel?: string;
  mode?: "embedded" | "page";
};

export function LecturePlaybookDetail({
  playbook,
  detailHref,
  backHref,
  snapshotLabel,
  mode = "embedded",
}: LecturePlaybookDetailProps) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const pageHref = detailHref ?? `/toolkit/playbooks/${playbook.id}`;

  async function copyDeepLink() {
    try {
      await copyTextToClipboard(toAbsoluteUrl(pageHref));
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1600);
    } catch {
      setCopyState("failed");
    }
  }

  function printPlaybook() {
    window.print();
  }

  return (
    <article
      className={cn(
        "printable-playbook min-w-0 rounded-2xl bg-white print:rounded-none print:border-0 print:p-0 print:shadow-none",
        mode === "page" ? "border border-[#E9E5E2] p-5" : "",
      )}
    >
      <PrintStyles />

      <div className="mb-5 flex flex-col gap-3 print:hidden sm:flex-row sm:items-center sm:justify-between">
        {backHref ? (
          <a
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm font-semibold text-[#7A625A] transition hover:border-[#C25B6E] hover:text-[#A24D61]"
            href={backHref}
          >
            <ArrowLeft size={16} aria-hidden="true" />
            返回工具库
          </a>
        ) : (
          <span />
        )}
        <div className="flex flex-wrap gap-2">
          {mode === "embedded" ? (
            <a
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm font-semibold text-[#7A625A] transition hover:border-[#C25B6E] hover:text-[#A24D61]"
              href={pageHref}
            >
              <BookOpenCheck size={16} aria-hidden="true" />
              打开讲义页
            </a>
          ) : null}
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm font-semibold text-[#7A625A] transition hover:border-[#C25B6E] hover:text-[#A24D61]"
            onClick={() => void copyDeepLink()}
            type="button"
          >
            <Link2 size={16} aria-hidden="true" />
            {copyState === "copied" ? "已复制" : "复制链接"}
          </button>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#C25B6E] bg-[#C25B6E] px-3 text-sm font-semibold text-white transition hover:bg-[#A24D61]"
            onClick={printPlaybook}
            type="button"
          >
            <Printer size={16} aria-hidden="true" />
            打印讲义
          </button>
        </div>
      </div>

      {copyState === "failed" ? (
        <p className="mb-4 rounded-xl border border-[#F0C9C2] bg-[#FFF5F2] px-3 py-2 text-xs font-semibold text-[#A04437] print:hidden">
          复制失败，请直接使用浏览器地址栏链接。
        </p>
      ) : null}

      <div className="min-w-0">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-[#EDE6DF] bg-[#FBF8F5] px-2.5 py-1 text-[11px] font-semibold text-[#7A625A] print:border-[#D6D6D6] print:bg-white print:text-black">
                {playbook.level}
              </span>
              <span className="rounded-full border border-[#F1D9A8] bg-[#FFF9E9] px-2.5 py-1 text-[11px] font-semibold text-[#87611B] print:border-[#D6D6D6] print:bg-white print:text-black">
                {playbook.durationMinutes} 分钟
              </span>
              <span className="rounded-full border border-[#E6D3CE] bg-[#FFF8F6] px-2.5 py-1 text-[11px] font-semibold text-[#A24D61] print:border-[#D6D6D6] print:bg-white print:text-black">
                {playbook.evidenceCount} 条证据
              </span>
              {snapshotLabel ? (
                <span className="rounded-full border border-[#EDE6DF] bg-white px-2.5 py-1 text-[11px] font-semibold text-[#7A625A] print:border-[#D6D6D6] print:text-black">
                  {snapshotLabel}
                </span>
              ) : null}
            </div>
            <h3 className="text-xl font-semibold leading-7 text-[#1D1D1F] print:text-2xl print:text-black">
              {playbook.title}
            </h3>
            <p className="mt-2 text-sm leading-6 text-[#5F5757] print:text-[13px] print:text-black">
              {playbook.claim}
            </p>
            <p className="mt-3 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-xs leading-5 text-[#7A625A] print:border-[#D6D6D6] print:bg-white print:text-black">
              适用人群：{playbook.audience}
            </p>
          </div>
          <a
            className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm font-semibold text-[#7A625A] transition hover:border-[#C25B6E] hover:text-[#A24D61] print:hidden"
            href={`/intelligence/${playbook.intelligenceId}`}
          >
            打开情报
            <ExternalLink size={14} aria-hidden="true" />
          </a>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-2 print:grid-cols-1">
          <PlaybookList title="讲解顺序" items={playbook.teachingSequence} />
          <PlaybookList title="实操步骤" items={playbook.handsOnSteps} />
          <PlaybookList title="验收步骤" items={playbook.verificationSteps} />
          <PlaybookList title="风险边界" items={playbook.riskBoundaries} warning />
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
            {playbook.evidenceUrls.slice(0, 6).map((url, index) => (
              <a
                className="inline-flex min-w-0 items-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-xs font-semibold text-[#7A625A] transition hover:border-[#C25B6E] hover:text-[#A24D61] print:block print:border-0 print:bg-white print:px-0 print:py-0.5 print:text-black"
                href={url}
                key={url}
                rel="noreferrer"
                target="_blank"
              >
                <span className="truncate print:whitespace-normal">
                  证据 {index + 1}：{url}
                </span>
                <ExternalLink size={13} className="shrink-0 print:hidden" aria-hidden="true" />
              </a>
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}

function PlaybookList({
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
              className={cn(
                "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold print:border print:border-[#D6D6D6] print:bg-white print:text-black",
                warning ? "bg-[#FFF5F2] text-[#A04437]" : "bg-[#F5FBF3] text-[#44743E]",
              )}
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

function PrintStyles() {
  return (
    <style jsx global>{`
      @media print {
        @page {
          margin: 14mm;
        }

        body {
          background: #ffffff !important;
        }

        body * {
          visibility: hidden;
        }

        .printable-playbook,
        .printable-playbook * {
          visibility: visible;
        }

        .printable-playbook {
          position: absolute;
          inset: 0 auto auto 0;
          width: 100%;
        }
      }
    `}</style>
  );
}

function toAbsoluteUrl(href: string) {
  return new URL(href, window.location.origin).toString();
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
