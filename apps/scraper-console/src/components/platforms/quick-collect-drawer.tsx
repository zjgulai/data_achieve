"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { X, CheckCircle, AlertCircle, Loader2, ArrowRight } from "lucide-react";
import type { CollectorEndpoint } from "@/lib/api/collectors";
import { postQuickCollect, type QuickCollectResponse } from "@/lib/api/quick-collect";
import { fetchProjects } from "@/lib/api/projects";
import { ApiError } from "@/lib/api/client";

/* ── Param field definitions per endpoint_type ── */
type FieldDef = {
  key: string;
  label: string;
  type: "text" | "number";
  required: boolean;
  placeholder: string;
  defaultValue?: string | number;
};

const PARAM_FIELDS: Record<string, FieldDef[]> = {
  tikhub_tiktok_video_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "wearable breast pump" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_tiktok_user_posts: [
    { key: "unique_id", label: "账号名 (unique_id)", type: "text", required: true, placeholder: "charlidamelio" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_tiktok_hashtag_posts: [
    { key: "ch_id", label: "话题 ID (ch_id)", type: "text", required: true, placeholder: "7273" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_instagram_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "momcozy breast pump" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_instagram_user_posts: [
    { key: "user_id", label: "账号 user_id", type: "text", required: true, placeholder: "12345678" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "12", defaultValue: 12 },
  ],
  tikhub_xiaohongshu_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "吸奶器" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_tiktok: [
    { key: "actor_id", label: "Actor ID", type: "text", required: true, placeholder: "clockworks/tiktok-scraper", defaultValue: "clockworks/tiktok-scraper" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
    { key: "max_total_charge_usd", label: "费用上限 (USD)", type: "number", required: false, placeholder: "0.5", defaultValue: 0.5 },
  ],
  apify_instagram: [
    { key: "actor_id", label: "Actor ID", type: "text", required: true, placeholder: "apify/instagram-scraper", defaultValue: "apify/instagram-scraper" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
    { key: "max_total_charge_usd", label: "费用上限 (USD)", type: "number", required: false, placeholder: "0.5", defaultValue: 0.5 },
  ],
  github_repo: [
    { key: "owner", label: "仓库所有者", type: "text", required: true, placeholder: "facebook" },
    { key: "repo", label: "仓库名称", type: "text", required: true, placeholder: "react" },
  ],
  github_topic: [
    { key: "topic", label: "GitHub 话题", type: "text", required: true, placeholder: "machine-learning" },
    { key: "max_results", label: "最大结果数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  public_feed: [
    { key: "url", label: "RSS/Atom URL", type: "text", required: true, placeholder: "https://example.com/feed.xml" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  generic_web: [
    { key: "url", label: "网页 URL", type: "text", required: true, placeholder: "https://example.com/page" },
  ],
};

function getDefaultParams(endpoint_type: string): Record<string, string | number> {
  const fields = PARAM_FIELDS[endpoint_type] ?? [];
  const out: Record<string, string | number> = {};
  for (const f of fields) {
    if (f.defaultValue !== undefined) out[f.key] = f.defaultValue;
    else if (f.type === "text") out[f.key] = "";
    else out[f.key] = 0;
  }
  return out;
}

/* ── Result card ── */
function RunResult({ result }: { result: QuickCollectResponse }) {
  const router = useRouter();
  const ok = result.status === "completed";
  return (
    <div
      className={`mt-4 rounded-[var(--radius-3)] border p-4 ${
        ok
          ? "border-[var(--state-success)] bg-[var(--success-soft)]"
          : "border-[var(--state-danger)] bg-[var(--danger-soft)]"
      }`}
    >
      <div className="flex items-start gap-3">
        {ok ? (
          <CheckCircle size={18} className="mt-0.5 shrink-0 text-[var(--state-success)]" />
        ) : (
          <AlertCircle size={18} className="mt-0.5 shrink-0 text-[var(--state-danger)]" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-[var(--text-primary)]">
            {ok ? "采集完成" : "采集失败"}
          </p>
          {ok ? (
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              写入 <span className="font-semibold text-[var(--state-success)]">{result.records_count}</span> 条原始记录
            </p>
          ) : (
            <p className="mt-1 text-sm text-[var(--state-danger)]">
              {result.error_message ?? "未知错误"}
            </p>
          )}
          <div className="mt-3 grid gap-1 text-xs text-[var(--text-tertiary)]">
            <span>运行 ID: <code className="font-mono">{result.task_run_id.slice(0, 8)}…</code></span>
            <span>状态: <code>{result.status}</code></span>
          </div>
          {ok && (
            <button
              type="button"
              onClick={() => router.push(`/collect/${result.task_run_id}`)}
              className="mt-3 flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--text-inverse)] transition-opacity hover:opacity-90"
            >
              查看详细结果
              <ArrowRight size={12} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Drawer ── */
type Props = {
  endpoint: CollectorEndpoint;
  open: boolean;
  onClose: () => void;
};

export function QuickCollectDrawer({ endpoint, open, onClose }: Props) {
  const fields = PARAM_FIELDS[endpoint.endpoint_type] ?? [];

  const [params, setParams] = useState<Record<string, string | number>>(
    () => getDefaultParams(endpoint.endpoint_type)
  );
  const [projectId, setProjectId] = useState<string>("");

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: () =>
      postQuickCollect({
        project_id: projectId,
        endpoint_type: endpoint.endpoint_type,
        params,
        label: endpoint.label,
      }),
  });

  /* sync project_id when projects loaded */
  if (projects && projects.length > 0 && !projectId) {
    setProjectId(projects[0].id);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  function handleClose() {
    mutation.reset();
    onClose();
  }

  if (!open) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-[var(--overlay-scrim)]"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`快速采集：${endpoint.label}`}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-[var(--border-subtle)] bg-[var(--surface-primary)] shadow-[var(--shadow-overlay)]"
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[var(--border-subtle)] px-6 py-4">
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              快速采集
            </h2>
            <p className="mt-0.5 text-sm text-[var(--text-secondary)]">
              {endpoint.label}
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label="关闭"
            className="rounded-[var(--radius-2)] p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {/* Meta */}
          <div className="mb-5 rounded-[var(--radius-2)] bg-[var(--surface-muted)] px-4 py-3 text-xs text-[var(--text-tertiary)]">
            <p>{endpoint.description}</p>
            {endpoint.cost_hint && (
              <p className="mt-1 text-[var(--state-info)]">
                预估费用：{endpoint.cost_hint}
              </p>
            )}
          </div>

          {mutation.isSuccess ? (
            <>
              <RunResult result={mutation.data} />
              <button
                type="button"
                onClick={() => mutation.reset()}
                className="mt-4 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              >
                再次采集
              </button>
            </>
          ) : (
            <form onSubmit={handleSubmit} className="grid gap-5">
              {/* Project selector */}
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-[var(--text-primary)]">
                  所属项目 <span className="text-[var(--state-danger)]">*</span>
                </label>
                <select
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  required
                  className="h-10 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
                >
                  {!projects || projects.length === 0 ? (
                    <option value="">加载中...</option>
                  ) : (
                    projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))
                  )}
                </select>
              </div>

              {/* Dynamic param fields */}
              {fields.map((field) => (
                <div key={field.key} className="grid gap-1.5">
                  <label className="text-sm font-medium text-[var(--text-primary)]">
                    {field.label}
                    {field.required && (
                      <span className="ml-1 text-[var(--state-danger)]">*</span>
                    )}
                  </label>
                  <input
                    type={field.type}
                    value={String(params[field.key] ?? "")}
                    onChange={(e) =>
                      setParams((prev) => ({
                        ...prev,
                        [field.key]:
                          field.type === "number"
                            ? Number(e.target.value)
                            : e.target.value,
                      }))
                    }
                    placeholder={field.placeholder}
                    required={field.required}
                    min={field.type === "number" ? 1 : undefined}
                    className="h-10 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
                  />
                </div>
              ))}

              {/* Error banner */}
              {mutation.isError && (
                <div className="rounded-[var(--radius-2)] border border-[var(--state-danger)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--state-danger)]">
                  {mutation.error instanceof ApiError
                    ? mutation.error.message
                    : "采集失败，请稍后重试"}
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={mutation.isPending}
                  className="flex-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-4 py-2.5 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)] disabled:opacity-50"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={mutation.isPending || !projectId}
                  className="flex flex-1 items-center justify-center gap-2 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--text-inverse)] transition-colors hover:bg-[var(--action-primary-hover)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {mutation.isPending ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      采集中...
                    </>
                  ) : (
                    "▶ 开始采集"
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </>
  );
}
