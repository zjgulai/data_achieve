"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchProject, DOMAIN_LABELS, DOMAIN_COLORS } from "@/lib/api/projects";
import { Loader2, FolderKanban, PlayCircle, Database, Calendar } from "lucide-react";
import Link from "next/link";

type Props = {
  params: Promise<{ id: string }>;
};

export default function ProjectDetailPage({ params }: Props) {
  const { id } = use(params);
  
  const { data: project, isLoading, error } = useQuery({
    queryKey: ["project", id],
    queryFn: () => fetchProject(id),
  });

  if (isLoading) {
    return (
      <AppShell title="加载中..." description="">
        <div className="flex justify-center py-16">
          <Loader2 size={32} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      </AppShell>
    );
  }

  if (error || !project) {
    return (
      <AppShell title="加载失败" description="">
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-6 text-sm text-[var(--state-danger)]">
          {(error as Error)?.message || "项目不存在"}
        </div>
      </AppShell>
    );
  }

  const domain = project.domain as keyof typeof DOMAIN_LABELS;

  return (
    <AppShell
      title={project.name}
      description={project.description || undefined}
      breadcrumbs={[
        { label: "我的项目", href: "/projects" },
        { label: project.name },
      ]}
    >
      <div className="mb-6 flex items-center gap-3">
        <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${DOMAIN_COLORS[domain]}`}>
          {DOMAIN_LABELS[domain]}
        </span>
        {project.status === "archived" && (
          <span className="rounded-full bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-tertiary)]">
            已归档
          </span>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* 任务列表 */}
        <div className="lg:col-span-2">
          <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
                <PlayCircle size={18} />
                采集任务
              </h2>
              <Link
                href={`/tasks/new?project_id=${project.id}`}
                className="rounded-[var(--radius-2)] bg-[var(--action-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]"
              >
                + 新建任务
              </Link>
            </div>
            <div className="mt-6 text-center py-8 text-sm text-[var(--text-tertiary)]">
              暂无任务，点击上方按钮创建
            </div>
          </div>

          {/* 运行记录 */}
          <div className="mt-6 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
            <h2 className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
              <Calendar size={18} />
              最近运行
            </h2>
            <div className="mt-6 text-center py-8 text-sm text-[var(--text-tertiary)]">
              暂无运行记录
            </div>
          </div>
        </div>

        {/* 右侧数据集 */}
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
          <h2 className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
            <Database size={18} />
            数据集
          </h2>
          <div className="mt-6 text-center py-8 text-sm text-[var(--text-tertiary)]">
            暂无数据集
          </div>
        </div>
      </div>
    </AppShell>
  );
}
