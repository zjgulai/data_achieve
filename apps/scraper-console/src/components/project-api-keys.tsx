"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, RefreshCw } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import {
  fetchMcpToolPolicies,
  type McpToolPolicies,
} from "@/lib/api/mcp-tool-policies";
import {
  fetchProjectApiKeys,
  issueProjectApiKey,
  patchProjectApiKey,
  revokeProjectApiKey,
  type IssuedProjectApiKey,
  type ProjectApiKey,
} from "@/lib/api/project-api-keys";

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

/** access_mode 分组标题。顺序即渲染顺序：只读 → 执行 → 控制。 */
const ACCESS_MODE_GROUPS: ReadonlyArray<{
  mode: McpToolPolicies["tools"][number]["access_mode"];
  title: string;
}> = [
  { mode: "read", title: "只读" },
  { mode: "execute", title: "执行" },
  { mode: "control", title: "控制" },
];

/** 预设按钮的展示顺序与文案。键名是后端 PRESETS 的字面量。 */
const PRESET_BUTTONS: ReadonlyArray<{ key: string; label: string }> = [
  { key: "readonly_discovery", label: "只读发现" },
  { key: "search_research", label: "搜索研究" },
  { key: "tiktok", label: "TikTok" },
  { key: "ops_query", label: "运维查询" },
  { key: "all", label: "全部" },
];

type KeyFormValues = {
  label: string;
  tool_allowlist: string[];
  daily_collect_quota: number;
};

type KeyFormProps = {
  readonly policies: McpToolPolicies;
  readonly busy: boolean;
  /** 编辑态预填的密钥；签发态为 null。 */
  readonly editing: ProjectApiKey | null;
  readonly onSubmit: (values: KeyFormValues) => void;
  readonly onCancel?: () => void;
};

/** 签发与编辑共用的表单：工具复选框从策略注册表渲染，预设并集进勾选集合。 */
function KeyForm({ policies, busy, editing, onSubmit, onCancel }: KeyFormProps) {
  const [label, setLabel] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [allowlist, setAllowlist] = useState<string[]>(() => {
    if (editing) {
      // 注册表可能已下架部分工具：预填取交集，PATCH 才能通过校验。
      const known = new Set(policies.tools.map((tool) => tool.name));
      return editing.tool_allowlist.filter((name) => known.has(name));
    }
    return ["web_search", "web_fetch"];
  });
  const [quota, setQuota] = useState<number>(
    editing ? editing.daily_collect_quota : 50
  );

  const toolsByMode = new Map<string, typeof policies.tools>();
  for (const tool of policies.tools) {
    const list = toolsByMode.get(tool.access_mode) ?? [];
    list.push(tool);
    toolsByMode.set(tool.access_mode, list);
  }
  // 未来注册表扩出未知 access_mode 时兜底成「其他」组，避免静默吞工具。
  const knownModes = new Set(ACCESS_MODE_GROUPS.map((group) => group.mode));
  const otherTools = policies.tools.filter(
    (tool) => !knownModes.has(tool.access_mode)
  );
  const knownPresets = PRESET_BUTTONS.filter((preset) =>
    Object.prototype.hasOwnProperty.call(policies.presets, preset.key)
  );

  function toggleTool(tool: string) {
    setAllowlist((current) =>
      current.includes(tool)
        ? current.filter((item) => item !== tool)
        : [...current, tool]
    );
  }

  /** 把 preset 数组并集进当前勾选集合；all 即全选注册表全部工具。 */
  function applyPreset(presetKey: string) {
    const members = policies.presets[presetKey] ?? [];
    setAllowlist((current) => Array.from(new Set([...current, ...members])));
  }

  function renderToolGroup(title: string, tools: McpToolPolicies["tools"]) {
    if (tools.length === 0) return null;
    return (
      <div key={title} className="mt-2">
        <p className="text-[11px] text-[var(--text-tertiary)]">
          {title}（{tools.length}）
        </p>
        <div className="mt-1 flex flex-wrap gap-2">
          {tools.map((tool) => (
            <label
              key={tool.name}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2 py-1 text-xs text-[var(--text-secondary)]"
            >
              <input
                type="checkbox"
                checked={allowlist.includes(tool.name)}
                onChange={() => toggleTool(tool.name)}
              />
              {tool.name}
            </label>
          ))}
        </div>
      </div>
    );
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        const missing: string[] = [];
        if (!editing && !label.trim()) missing.push("标签必填");
        if (allowlist.length === 0) missing.push("允许工具至少选一个");
        if (missing.length > 0) {
          setFormError(`${missing.join("，")}。`);
          return;
        }
        setFormError(null);
        onSubmit({
          label: label.trim(),
          tool_allowlist: allowlist,
          daily_collect_quota: quota,
        });
      }}
      className="mt-3 grid gap-3"
    >
      {formError && (
        <p role="alert" className="rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-xs text-[var(--state-danger)]">
          {formError}
        </p>
      )}

      {editing && (
        <p className="text-xs text-[var(--text-secondary)]">
          正在编辑密钥「{editing.label}」。标签不可修改。
        </p>
      )}

      {!editing && (
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
      )}

      <fieldset>
        <legend className="text-xs font-medium text-[var(--text-secondary)]">
          预设（并集进勾选，可再手动增减）
        </legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {knownPresets.map((preset) => (
            <button
              key={preset.key}
              type="button"
              onClick={() => applyPreset(preset.key)}
              disabled={busy}
              className="rounded-lg border border-[var(--border-subtle)] px-2 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-60"
            >
              {preset.label}
            </button>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="text-xs font-medium text-[var(--text-secondary)]">
          允许工具（至少选一个）
        </legend>
        {ACCESS_MODE_GROUPS.map((group) =>
          renderToolGroup(group.title, toolsByMode.get(group.mode) ?? [])
        )}
        {renderToolGroup("其他", otherTools)}
      </fieldset>

      <div>
        <label
          className="block text-xs font-medium text-[var(--text-secondary)]"
          htmlFor="key-quota"
        >
          每日采集额度
        </label>
        <input
          id="key-quota"
          type="number"
          min={1}
          max={100000}
          value={quota}
          onChange={(event) => {
            const next = Number(event.target.value);
            // 清空或非法输入不改状态，防止额度意外变成 0。
            if (Number.isFinite(next) && next >= 1) setQuota(next);
          }}
          className="mt-1.5 w-32 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm outline-none focus:border-[var(--action-primary)]"
        />
      </div>

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={busy}
          className="w-fit rounded-lg bg-[var(--action-primary)] px-3 py-2 text-xs font-semibold text-[var(--text-inverse)] disabled:opacity-60"
        >
          {editing
            ? busy
              ? "保存中..."
              : "保存修改"
            : busy
              ? "签发中..."
              : "签发密钥"}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-60"
          >
            取消
          </button>
        )}
      </div>
    </form>
  );
}

export function ProjectApiKeys({ projectId }: { readonly projectId: string }) {
  const queryClient = useQueryClient();
  const [issued, setIssued] = useState<IssuedProjectApiKey | null>(null);
  const [editingKey, setEditingKey] = useState<ProjectApiKey | null>(null);
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

  // 策略注册表：后端严格鉴权，与密钥管理同权限。401/403 不重试。
  const policiesQuery = useQuery({
    queryKey: ["mcp-tool-policies"],
    queryFn: () => fetchMcpToolPolicies(),
    retry: (count, err) => {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403))
        return false;
      return count < 2;
    },
  });

  const issue = useMutation({
    mutationFn: (values: KeyFormValues) =>
      issueProjectApiKey(projectId, {
        label: values.label,
        tool_allowlist: values.tool_allowlist,
        daily_collect_quota: values.daily_collect_quota,
      }),
    onSuccess: async (key) => {
      setIssued(key);
      setEditingKey(null);
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

  const update = useMutation({
    mutationFn: (input: {
      keyId: string;
      values: { tool_allowlist: string[]; daily_collect_quota: number };
    }) =>
      patchProjectApiKey(projectId, input.keyId, {
        tool_allowlist: input.values.tool_allowlist,
        daily_collect_quota: input.values.daily_collect_quota,
      }),
    onSuccess: async () => {
      setEditingKey(null);
      setActionError(null);
      await queryClient.invalidateQueries({
        queryKey: ["project-api-keys", projectId],
      });
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        if (err.status === 400 && err.message === "unknown_tool_in_allowlist") {
          setActionError(
            "白名单里有工具已不在注册表中。刷新页面后重新勾选。"
          );
        } else if (
          err.status === 400 &&
          err.message === "project_api_key_allowlist_required"
        ) {
          setActionError("允许工具至少选一个。");
        } else if (err.status === 404) {
          setActionError("密钥不存在或已撤销。刷新后重试。");
        } else {
          setActionError(`保存失败：${err.message}`);
        }
      } else {
        setActionError(`保存失败：${err.message}`);
      }
    },
  });

  const revoke = useMutation({
    mutationFn: (keyId: string) => revokeProjectApiKey(projectId, keyId),
    onSuccess: async () => {
      setIssued(null);
      setEditingKey(null);
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
  const busy = issue.isPending || update.isPending || revoke.isPending;
  const policies = policiesQuery.data ?? null;
  // 编辑态仍显示活跃密钥行（keyQuery 里有 active），表单预填编辑密钥。
  const showEditForm = active !== null && editingKey?.id === active.id;

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

      {keysQuery.isLoading || policiesQuery.isLoading ? (
        <div className="flex justify-center py-6">
          <Loader2 size={18} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      ) : forbidden ? (
        <p className="mt-3 text-xs text-[var(--text-tertiary)]">
          只有工作区所有者或项目所有者可以管理密钥。
        </p>
      ) : keysQuery.error ? (
        <p className="mt-3 text-xs text-[var(--state-danger)]">
          密钥列表加载失败：{(keysQuery.error as Error).message}
        </p>
      ) : policiesQuery.error ? (
        <div className="mt-3 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-xs text-[var(--state-danger)]">
          <p>
            策略加载失败：{(policiesQuery.error as Error).message}
          </p>
          <button
            type="button"
            onClick={() => policiesQuery.refetch()}
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
          >
            <RefreshCw size={14} />
            重试
          </button>
        </div>
      ) : active ? (
        <div className="mt-3">
          <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2">
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
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setEditingKey(active);
                    setActionError(null);
                  }}
                  disabled={busy}
                  className="rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-60"
                >
                  编辑
                </button>
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
          </div>
          {showEditForm && policies && editingKey && (
            <KeyForm
              key={editingKey.id}
              policies={policies}
              busy={busy}
              editing={editingKey}
              onCancel={() => setEditingKey(null)}
              onSubmit={(values) =>
                update.mutate({ keyId: editingKey.id, values })
              }
            />
          )}
        </div>
      ) : policies ? (
        <KeyForm
          policies={policies}
          busy={busy}
          editing={null}
          onSubmit={(values) => issue.mutate(values)}
        />
      ) : null}
    </section>
  );
}
