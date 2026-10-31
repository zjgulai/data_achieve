"use client";

import { useEffect } from "react";
import Link from "next/link";

import { AppShell } from "@/components/layout/app-shell";

const PRIMARY_BUTTON_CLASS =
  "inline-flex items-center rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-medium text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]";

const SECONDARY_LINK_CLASS =
  "inline-flex items-center rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]";

export default function ErrorPage({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <AppShell
      title="页面出错"
      description="页面渲染时出现异常，可以重试或返回工作台。"
    >
      <section
        role="alert"
        className="rounded-[var(--radius-3)] border border-[var(--state-danger)] bg-[var(--danger-soft)] p-6"
      >
        <h2 className="text-sm font-semibold text-[var(--state-danger)]">
          错误摘要
        </h2>
        <p className="mt-2 break-all text-xs leading-relaxed text-[var(--state-danger)]">
          {error.message !== "" ? error.message : "未知错误"}
        </p>
        {error.digest ? (
          <p className="mt-2 break-all font-mono text-[11px] text-[var(--text-tertiary)]">
            错误编号：{error.digest}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => retry()}
            className={PRIMARY_BUTTON_CLASS}
          >
            重试
          </button>
          <Link href="/workbench" className={SECONDARY_LINK_CLASS}>
            回工作台
          </Link>
        </div>
      </section>
    </AppShell>
  );
}
