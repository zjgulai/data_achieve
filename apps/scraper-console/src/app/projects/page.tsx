"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import {
  fetchProjects,
  createProject,
  DOMAIN_LABELS,
  DOMAIN_COLORS,
  type ProjectDomain,
} from "@/lib/api/projects";
import { Plus, FolderKanban, ChevronRight, Loader2 } from "lucide-react";
import { ApiError } from "@/lib/api/client";

const DOMAINS: ProjectDomain[] = ["social", "ecommerce", "competitor", "osint", "mixed"];

function CreateProjectModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [domain, setDomain] = useState<ProjectDomain>("social");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => createProject({ name: name.trim(), domain, description: description.trim() || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "创建失败"),
  });

  return (
    <>
      <div className="fixed inset-0 z-40 bg-[var(--overlay-scrim)]" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="创建项目"
        className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6 shadow-[var(--shadow-overlay)]"
      >
        <h2 className="text-base font-bold text-[var(--text-primary)]">新建项目</h2>
        <div className="mt-4 grid gap-4">
          <div className="grid gap-1.5">
            <label className="text-sm font-medium text-[var(--text-primary)]">
              项目名称 <span className="text-[var(--state-danger)]">*</span>
            </label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="如：Momcozy 品牌监测"
              className="h-10 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
            />
          </div>

          <div className="grid gap-1.5">
            <label className="text-sm font-medium text-[var(--text-primary)]">
              类型 <span className="text-[var(--state-danger)]">*</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {DOMAINS.map(d => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDomain(d)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    domain === d
                      ? "bg-[var(--action-primary)] text-[var(--text-inverse)]"
                      : "border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                  }`}
                >
                  {DOMAIN_LABELS[d]}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-1.5">
            <label className="text-sm font-medium text-[var(--text-primary)]">备注（可选）</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="描述这个项目的监测目标"
              rows={2}
              className="w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)] resize-none"
            />
          </div>

          {error && <p className="text-sm text-[var(--state-danger)]">{error}</p>}

          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]">
              取消
            </button>
            <button
              type="button"
              disabled={!name.trim() || create.isPending}
              onClick={() => create.mutate()}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--action-primary)] py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] disabled:opacity-50"
            >
              {create.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
              创建
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export default function ProjectsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const { data: projects, isLoading, error } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
  });

  const active = projects?.filter(p => p.status === "active") ?? [];
  const archived = projects?.filter(p => p.status === "archived") ?? [];

  return (
    <AppShell title="我的项目" description="管理长期监测项目">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--text-tertiary)]">
          {active.length} 个活跃项目
        </p>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]"
        >
          <Plus size={15} />
          新建项目
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 size={24} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      ) : error ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-6 text-sm text-[var(--state-danger)]">
          加载失败：{(error as Error).message}
        </div>
      ) : active.length === 0 ? (
        <div className="rounded-[var(--radius-3)] border-2 border-dashed border-[var(--border-subtle)] py-16 text-center">
          <FolderKanban size={36} className="mx-auto text-[var(--text-tertiary)]" />
          <p className="mt-3 text-base font-semibold text-[var(--text-primary)]">还没有项目</p>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">创建一个项目，管理你的采集任务和数据集</p>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="mt-5 inline-flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-5 py-2.5 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]"
          >
            <Plus size={15} />
            新建项目
          </button>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {active.map(project => (
            <Link
              key={project.id}
              href={`/projects/${project.id}`}
              className="group flex flex-col rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5 transition-shadow hover:shadow-[0_4px_12px_rgb(36_27_27/8%)]"
            >
              <div className="flex items-start justify-between">
                <h3 className="text-sm font-bold text-[var(--text-primary)] group-hover:text-[var(--action-primary)] transition-colors">
                  {project.name}
                </h3>
                <ChevronRight size={16} className="mt-0.5 shrink-0 text-[var(--text-tertiary)] group-hover:text-[var(--action-primary)] transition-colors" />
              </div>

              {project.description && (
                <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-[var(--text-tertiary)]">
                  {project.description}
                </p>
              )}

              <div className="mt-auto pt-4">
                <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${DOMAIN_COLORS[project.domain as keyof typeof DOMAIN_COLORS]}`}>
                  {DOMAIN_LABELS[project.domain as keyof typeof DOMAIN_LABELS] ?? project.domain}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {archived.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-sm text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">
            已归档项目 ({archived.length})
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {archived.map(project => (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="flex flex-col rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] p-5 opacity-70 transition-opacity hover:opacity-100"
              >
                <h3 className="text-sm font-semibold text-[var(--text-secondary)]">{project.name}</h3>
                <span className="mt-3 text-xs text-[var(--text-tertiary)]">已归档</span>
              </Link>
            ))}
          </div>
        </details>
      )}

      {showCreate && <CreateProjectModal onClose={() => setShowCreate(false)} />}
    </AppShell>
  );
}
