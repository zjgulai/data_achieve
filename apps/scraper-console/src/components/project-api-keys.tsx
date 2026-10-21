"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2 } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import {
  fetchProjectApiKeys,
  issueProjectApiKey,
  MCP_TOOL_OPTIONS,
  revokeProjectApiKey,
  type IssuedProjectApiKey,
} from "@/lib/api/project-api-keys";

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function ProjectApiKeys({ projectId }: { readonly projectId: string }) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");
  const [quota, setQuota] = useState(50);
  const [allowlist, setAllowlist] = useState<string[]>(["web_search", "web_fetch"]);
  const [issued, setIssued] = useState<IssuedProjectApiKey | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const keysQuery = useQuery({
    queryKey: ["project-api-keys", projectId],
    queryFn: () => fetchProjectApiKeys(projectId),
    retry: (count, err) => {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403))
        return false;
      return count < 2;
    },
  });

  const issue = useMutation({
    mutationFn: () =>
      issueProjectApiKey(projectId, {
        label: label.trim(),
        tool_allowlist: allowlist,
        daily_collect_quota: quota,
      }),
    onSuccess: async (key) => {
      setIssued(key);
      setLabel("");
      setActionError(null);
      await queryClient.invalidateQueries({
        queryKey: ["project-api-keys", projectId],
      });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        setActionError("该项目已有一把未撤销的密钥。先撤销再签发。");
      } else {
        setActionError(`签发失败：${err.message}`);
      }
    },
  });

  const revoke = useMutation({
    mutationFn: (keyId: string) => revokeProjectApiKey(projectId, keyId),
    onSuccess: async () => {
      setIssued(null);
      setActionError(null);
      await queryClient.invalidateQueries({
        queryKey: ["project-api-keys", projectId],
      });
    },
    onError: (err) => setActionError(`撤销失败：${err.message}`),
  });

  const forbidden =
    keysQuery.error instanceof ApiError && keysQuery.error.status === 403;
  const active = (keysQuery.data ?? []).find((key) => !key.revoked_at) ?? null;
  const busy = issue.isPending || revoke.isPending;

  function toggleTool(tool: string) {
    setAllowlist((current) =>
      current.includes(tool)
        ? current.filter((item) => item !== tool)
        : [...current, tool]
    );
  }

  return (
    <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
      <h2 className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
        <KeyRound size={18} />
        API 密钥
      </h2>
      <p className="mt-1 text-xs text-[var(--text-tertiary)]">
        供 MCP 客户端使用。每个项目最多一把有效密钥；轮换先撤销再签发。
        明文只在签发时显示一次。
      </p>

      {actionError && (
        <p role="alert" className="mt-3 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-xs text-[var(--state-danger)]">
          {actionError}
        </p>
      )}

      {issued && (
        <div className="mt-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-3 py-2">
          <p className="text-xs font-medium text-[var(--text-secondary)]">
            新密钥已生成。现在复制，之后无法再次查看。
          </p>
          <code className="mt-1 block break-all text-xs text-[var(--text-primary)]">
            {issued.plaintext}
          </code>
        </div>
      )}

      {keysQuery.isLoading ? (
        <div className="flex justify-center py-6">
          <Loader2 size={18} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      ) : forbidden ? (
        <p className="mt-3 text-xs text-[var(--text-tertiary)]">
          只有工作区所有者或项目所有者可以管理密钥。
        </p>
      ) : keysQuery.error ? (
        <p className="mt-3 text-xs text-[var(--state-danger)]">
          加载失败：{(keysQuery.error as Error).message}
        </p>
      ) : active ? (
        <div className="mt-3 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                {active.label}
              </p>
              <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                {active.key_prefix}… · 今日 {active.quota_used}/
                {active.daily_collect_quota} · 最近使用{" "}
                {formatTime(active.last_used_at)}
              </p>
              <p className="mt-0.5 break-all text-xs text-[var(--text-tertiary)]">
                允许工具：{active.tool_allowlist.join("、")}
              </p>
            </div>
            <button
              type="button"
              onClick={() => revoke.mutate(active.id)}
              disabled={busy}
              className="shrink-0 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--state-danger)] hover:bg-[var(--danger-soft)] disabled:opacity-60"
            >
              撤销
            </button>
          </div>
        </div>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setActionError(null);
            if (!label.trim() || allowlist.length === 0) {
              setActionError("标签必填，允许工具至少选一个。");
              return;
            }
            issue.mutate();
          }}
          className="mt-3 grid gap-3"
        >
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]" htmlFor="key-label">
              标签
            </label>
            <input
              id="key-label"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="例如：外部 agent"
              className="mt-1.5 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm outline-none focus:border-[var(--action-primary)]"
            />
          </div>

          <fieldset>
            <legend className="text-xs font-medium text-[var(--text-secondary)]">
              允许工具（贵工具默认不勾）
            </legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {MCP_TOOL_OPTIONS.map((tool) => (
                <label
                  key={tool}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2 py-1 text-xs text-[var(--text-secondary)]"
                >
                  <input
                    type="checkbox"
                    checked={allowlist.includes(tool)}
                    onChange={() => toggleTool(tool)}
                  />
                  {tool}
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)]" htmlFor="key-quota">
              每日采集额度
            </label>
            <input
              id="key-quota"
              type="number"
              min={1}
              max={100000}
              value={quota}
              onChange={(event) => setQuota(Number(event.target.value))}
              className="mt-1.5 w-32 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm outline-none focus:border-[var(--action-primary)]"
            />
          </div>

          <button
            type="submit"
            disabled={busy}
            className="w-fit rounded-lg bg-[var(--action-primary)] px-3 py-2 text-xs font-semibold text-[var(--text-inverse)] disabled:opacity-60"
          >
            {issue.isPending ? "签发中..." : "签发密钥"}
          </button>
        </form>
      )}
    </section>
  );
}