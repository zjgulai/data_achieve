"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getToolkitOverview } from "@/lib/api/toolkit";
import type { ToolkitOverview } from "@/types/toolkit";

import { LecturePlaybookDetail } from "./lecture-playbook-detail";

type ToolkitLecturePlaybookPageProps = {
  playbookId: string;
};

export function ToolkitLecturePlaybookPage({
  playbookId,
}: ToolkitLecturePlaybookPageProps) {
  const [overview, setOverview] = useState<ToolkitOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          setError(caught instanceof Error ? caught.message : "讲义 API 暂不可用");
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  const playbook = useMemo(
    () => overview?.lecturePlaybooks.find((item) => item.id === playbookId),
    [overview?.lecturePlaybooks, playbookId],
  );

  if (error) {
    return (
      <StatusCard
        body="无法加载讲义详情。先确认登录状态和 API 健康状态，再刷新本页。"
        icon={AlertCircle}
        tone="error"
        title={error}
      />
    );
  }

  if (!overview) {
    return (
      <StatusCard
        body="正在读取最新工具库情报和讲义结构。"
        icon={Loader2}
        title="讲义加载中"
      />
    );
  }

  if (!playbook) {
    return (
      <StatusCard
        body="当前讲义 ID 不存在，返回工具库重新选择一张讲义。"
        icon={AlertCircle}
        tone="error"
        title="没有找到这张讲义"
      />
    );
  }

  return (
    <LecturePlaybookDetail
      backHref={`/toolkit?lecture=${encodeURIComponent(playbook.id)}`}
      detailHref={`/toolkit/playbooks/${playbook.id}`}
      mode="page"
      playbook={playbook}
      snapshotLabel={`${formatDate(overview.metrics.lastCollectedAt)} 快照`}
    />
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
