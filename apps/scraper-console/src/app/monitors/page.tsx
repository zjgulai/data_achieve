"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchProjects } from "@/lib/api/projects";
import {
  createMonitor,
  fetchMonitors,
  setMonitorStatus,
} from "@/lib/api/monitors";
import { Loader2, Radar } from "lucide-react";

const ENDPOINT_HINTS = [
  "exa_search_lite",
  "exa_search_auto",
  "exa_search_news",
  "exa_company_search",
  "exa_deep_lite",
  "anysearch_brand_media",
];

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

export default function MonitorsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [projectId, setProjectId] = useState("");
  const [endpointType, setEndpointType] = useState("exa_search_lite");
  const [paramsText, setParamsText] = useState('{"query": ""}');
  const [intervalHours, setIntervalHours] = useState(24);
  const [error, setError] = useState<string | null>(null);

  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => fetchProjects(),
  });
  const monitors = useQuery({
    queryKey: ["monitors"],
    queryFn: () => fetchMonitors(),
  });

  const create = useMutation({
    mutationFn: () => {
      const params = JSON.parse(paramsText) as Record<string, unknown>;
      return createMonitor({
        project_id: projectId,
        name: name.trim(),
        endpoint_type: endpointType.trim(),
        params,
        interval_hours: intervalHours,
      });
    },
    onSuccess: async () => {
      setName("");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["monitors"] });
    },
    onError: (err) => setError(`创建失败：${(err as Error).message}`),
  });

  const toggle = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "pause" | "resume" }) =>
      setMonitorStatus(id, action),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["monitors"] });
    },
    onError: (err) => setError(`操作失败：${(err as Error).message}`),
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!name.trim() || !projectId) {
      setError("请填写名称并选择项目。");
      return;
    }
    try {
      JSON.parse(paramsText);
    } catch {
      setError("参数必须是合法 JSON。");
      return;
    }
    create.mutate();
  }

  return (
    <AppShell
      title="搜索监控"
      description="定期重跑检索，新结果进入信号与通知"
      breadcrumbs={[{ label: "工作台" }, { label: "搜索监控" }]}
    >
      <div className="mb-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-4 py-3 text-xs text-[var(--text-tertiary)]">
        监控复用采集调度：按 1/6/24 小时重跑。通过 source_url 去重，
        新结果写入 new_search_result 信号，并通知工作区所有者。
      </div>

      {error && (
        <p role="alert" className="mb-4 rounded-lg bg-[var(--danger-soft)] px-4 py-3 text-xs text-[var(--state-danger)]">
          {error}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
            <Radar size={16} />
            现有监控
          </h2>
          {monitors.isLoading ? (
            <div className="flex justify-center py-6">
              <Loader2 size={18} className="animate-spin text-[var(--text-tertiary)]" />
            </div>
          ) : (monitors.data ?? []).length === 0 ? (
            <p className="mt-3 text-xs text-[var(--text-tertiary)]">还没有监控。</p>
          ) : (
            <ul className="mt-3 grid gap-2">
              {(monitors.data ?? []).map((monitor) => (
                <li
                  key={monitor.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border-subtle)] px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                      {monitor.name}
                    </p>
                    <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                      {monitor.endpoint_type} · 每 {monitor.interval_hours} 小时 ·{" "}
                      {monitor.status === "enabled" ? "运行中" : "已暂停"} · 上次{" "}
                      {formatTime(monitor.last_checked_at)} · 新增{" "}
                      {monitor.last_new_count ?? "—"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      toggle.mutate({
                        id: monitor.id,
                        action: monitor.status === "enabled" ? "pause" : "resume",
                      })
                    }
                    disabled={toggle.isPending}
                    className="shrink-0 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-60"
                  >
                    {monitor.status === "enabled" ? "暂停" : "恢复"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">新建监控</h2>
          <form onSubmit={onSubmit} className="mt-3 grid gap-3">
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]" htmlFor="monitor-name">
                名称
              </label>
              <input
                id="monitor-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="mt-1.5 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm outline-none focus:border-[var(--action-primary)]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]" htmlFor="monitor-project">
                项目
              </label>
              <select
                id="monitor-project"
                value={projectId}
                onChange={(event) => setProjectId(event.target.value)}
                className="mt-1.5 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
              >
                <option value="">选择项目</option>
                {(projects.data ?? []).map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]" htmlFor="monitor-endpoint">
                端点
              </label>
              <input
                id="monitor-endpoint"
                list="monitor-endpoint-options"
                value={endpointType}
                onChange={(event) => setEndpointType(event.target.value)}
                className="mt-1.5 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm outline-none focus:border-[var(--action-primary)]"
              />
              <datalist id="monitor-endpoint-options">
                {ENDPOINT_HINTS.map((endpoint) => (
                  <option key={endpoint} value={endpoint} />
                ))}
              </datalist>
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]" htmlFor="monitor-params">
                参数（JSON）
              </label>
              <textarea
                id="monitor-params"
                rows={3}
                value={paramsText}
                onChange={(event) => setParamsText(event.target.value)}
                className="mt-1.5 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 font-mono text-xs outline-none focus:border-[var(--action-primary)]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)]" htmlFor="monitor-interval">
                间隔
              </label>
              <select
                id="monitor-interval"
                value={intervalHours}
                onChange={(event) => setIntervalHours(Number(event.target.value))}
                className="mt-1.5 w-40 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
              >
                <option value={1}>每 1 小时</option>
                <option value={6}>每 6 小时</option>
                <option value={24}>每天</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={create.isPending}
              className="w-fit rounded-lg bg-[var(--action-primary)] px-3 py-2 text-xs font-semibold text-[var(--text-inverse)] disabled:opacity-60"
            >
              {create.isPending ? "创建中..." : "创建监控"}
            </button>
          </form>
        </section>
      </div>
    </AppShell>
  );
}