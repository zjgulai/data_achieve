"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { X, CheckCircle, AlertCircle, Loader2, ArrowRight } from "lucide-react";
import type { CollectorEndpoint } from "@/lib/api/collectors";
import { canStartCollection } from "@/lib/collection-policy";
import { fetchTool } from "@/lib/api/tools";
import {
  buildForm,
  buildInitialValues,
  evaluateSubmit,
  submitBlockMessage,
  serializeParams,
  splitList,
  type FormValue,
  type FormValues,
  type ParamField,
} from "@/lib/quick-collect-form";
import { postQuickCollect, type QuickCollectResponse } from "@/lib/api/quick-collect";
import { fetchProjects } from "@/lib/api/projects";
import { ApiError } from "@/lib/api/client";
import { isSuccessfulRunStatus } from "@/lib/run-status";
import {
  parseRunReceipt,
  recordPreviewEntries,
} from "@/lib/quick-collect-receipt";
import { useFocusTrap } from "@/components/ui/use-focus-trap";

/* ── 输入框样式。与既有控件一致。 ── */
const INPUT_CLASS =
  "h-10 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]";

const TEXTAREA_CLASS =
  "w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 font-mono text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]";

/* ── 结果卡 ── */

function RunResult({ result }: { result: QuickCollectResponse }) {
  const router = useRouter();
  const ok = isSuccessfulRunStatus(result.status);

  // 三块证据都可以缺：失败运行没有记录，端点可能无结构化输出，
  // 价格簿也可能没有该端点价格。解析在 lib 里做，这里只负责渲染。
  const receipt = parseRunReceipt(result);

  return (
    <div
      className={`mt-4 rounded-[var(--radius-3)] border p-4 ${
        ok
          ? "border-[var(--state-success)] bg-[var(--success-soft)]"
          : "border-[var(--state-danger)] bg-[var(--danger-soft)]"
      }`}
      data-testid="quick-collect-run-result"
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
              写入{" "}
              <span className="font-semibold text-[var(--state-success)]">
                {receipt.recordsCount}
              </span>{" "}
              条原始记录
            </p>
          ) : (
            <p className="mt-1 text-sm text-[var(--state-danger)]">
              {result.error_message ?? "未知错误"}
            </p>
          )}

          {/* 回执证据：耗时与花费。取不到就不显示该项。
              后端 output 是固定 5 键的信封（records_count / entities_count /
              records_returned / records_truncated / limit），把它渲染成
              「输出 N 个字段」永远显示 5，是噪音，故不展示。 */}
          {(receipt.durationMs !== null || receipt.costUsd !== null) && (
            <div
              className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--text-secondary)]"
              data-testid="quick-collect-run-receipt"
            >
              {receipt.durationMs !== null && (
                <span data-testid="quick-collect-duration">
                  耗时 <span className="font-semibold">{receipt.durationMs}</span> ms
                </span>
              )}
              {receipt.costUsd !== null && (
                <span data-testid="quick-collect-cost">
                  花费{" "}
                  <span className="font-semibold">
                    {receipt.costUsd === 0 ? "0" : `$${receipt.costUsd.toFixed(4)}`}
                  </span>
                </span>
              )}
            </div>
          )}

          {/* 记录样本：让用户当场看到拿到了什么，不用跳页。 */}
          {ok && receipt.sample.length > 0 && (
            <div className="mt-3" data-testid="quick-collect-record-sample">
              <p className="text-xs font-semibold text-[var(--text-tertiary)]">
                记录样本（前 {receipt.sample.length} 条，共 {receipt.recordsCount} 条）
              </p>
              <ul className="mt-1 grid gap-1">
                {receipt.sample.map((record, index) => (
                  <li
                    key={index}
                    className="truncate rounded-[var(--radius-1)] bg-[var(--surface-primary)] px-2 py-1 font-mono text-[11px] text-[var(--text-secondary)]"
                  >
                    {recordPreviewEntries(record)
                      .map(([key, value]) => `${key}=${value}`)
                      .join("  ")}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-3 grid gap-1 text-xs text-[var(--text-tertiary)]">
            <span>
              运行 ID: <code className="font-mono">{result.task_run_id.slice(0, 8)}…</code>
            </span>
            <span>
              状态: <code>{result.status}</code>
            </span>
          </div>
          {ok && (
            <button
              type="button"
              onClick={() => router.push(`/runs/${result.task_run_id}`)}
              className="mt-3 flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--text-inverse)] transition-opacity hover:opacity-90"
            >
              查看本次运行
              <ArrowRight size={12} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── 单个字段 ── */
function ParamInput({
  field,
  value,
  onChange,
}: {
  field: ParamField;
  value: FormValue | undefined;
  onChange: (name: string, value: FormValue) => void;
}) {
  const label = (
    <label
      htmlFor={`param-${field.name}`}
      className="text-sm font-medium text-[var(--text-primary)]"
    >
      {field.label}
      {field.required && <span className="ml-1 text-[var(--state-danger)]">*</span>}
    </label>
  );

  const hint = field.description ? (
    <p className="text-xs text-[var(--text-tertiary)]">{field.description}</p>
  ) : null;

  if (field.kind === "boolean") {
    return (
      <div className="grid gap-1.5">
        <div className="flex items-center gap-2">
          <input
            id={`param-${field.name}`}
            type="checkbox"
            checked={value === true}
            onChange={(e) => onChange(field.name, e.target.checked)}
            className="h-4 w-4 rounded-[var(--radius-1)] border border-[var(--border-subtle)] accent-[var(--action-primary)]"
          />
          {label}
        </div>
        {hint}
      </div>
    );
  }

  if (field.kind === "enum") {
    return (
      <div className="grid gap-1.5">
        {label}
        <select
          id={`param-${field.name}`}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(field.name, e.target.value)}
          required={field.required}
          className={INPUT_CLASS}
        >
          {!field.required && <option value="">不限</option>}
          {field.options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {hint}
      </div>
    );
  }

  if (field.kind === "list") {
    const raw = typeof value === "string" ? value : "";
    const count = splitList(raw).length;
    const overLimit = field.maxItems !== null && count > field.maxItems;
    return (
      <div className="grid gap-1.5">
        {label}
        <textarea
          id={`param-${field.name}`}
          rows={3}
          value={raw}
          onChange={(e) => onChange(field.name, e.target.value)}
          placeholder={field.placeholder || "一行一个值"}
          required={field.required}
          className={TEXTAREA_CLASS}
        />
        <p className={`text-xs ${overLimit ? "text-[var(--state-danger)]" : "text-[var(--text-tertiary)]"}`}>
          一行一个值。当前 {count} 项
          {field.maxItems !== null && `，上限 ${field.maxItems} 项`}
        </p>
        {hint}
      </div>
    );
  }

  if (field.kind === "number") {
    return (
      <div className="grid gap-1.5">
        {label}
        <input
          id={`param-${field.name}`}
          type="number"
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(field.name, e.target.value)}
          placeholder={field.placeholder}
          required={field.required}
          step={field.integer ? 1 : "any"}
          min={field.minimum ?? undefined}
          max={field.maximum ?? undefined}
          className={INPUT_CLASS}
        />
        {(field.minimum !== null || field.maximum !== null) && (
          <p className="text-xs text-[var(--text-tertiary)]">
            范围 {field.minimum ?? "不限"} – {field.maximum ?? "不限"}
          </p>
        )}
        {hint}
      </div>
    );
  }

  // 文本。含无类型参数。无类型参数不设 type 属性。
  return (
    <div className="grid gap-1.5">
      {label}
      <input
        id={`param-${field.name}`}
        {...(field.typed ? { type: "text" } : {})}
        value={typeof value === "string" ? value : ""}
        onChange={(e) => onChange(field.name, e.target.value)}
        placeholder={field.placeholder}
        required={field.required}
        className={INPUT_CLASS}
      />
      {hint}
    </div>
  );
}

/* ── 抽屉 ── */
type Props = {
  endpoint: CollectorEndpoint;
  open: boolean;
  onClose: () => void;
  /** 终止批量。仅批量模式传入。 */
  onAbort?: () => void;
  /** 批量进度。仅批量模式传入。 */
  batchProgress?: { index: number; total: number } | null;
};

export function QuickCollectDrawer({ endpoint, open, onClose, onAbort, batchProgress }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  useFocusTrap(open, panelRef);

  const {
    data: tool,
    isLoading: toolLoading,
    isError: toolFailed,
  } = useQuery({
    queryKey: ["tool", endpoint.endpoint_type],
    queryFn: () => fetchTool(endpoint.endpoint_type),
    enabled: open,
    staleTime: 5 * 60 * 1000,
  });

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
    enabled: open,
  });

  const form = useMemo(
    () => buildForm(tool, endpoint.param_fields),
    [tool, endpoint.param_fields]
  );

  // 表单初始值。契约到达后由 form 派生。
  const initialValues = useMemo(() => buildInitialValues(form), [form]);

  // 用户编辑过的值。null 表示尚未编辑，此时用 initialValues。
  const [draft, setDraft] = useState<FormValues | null>(null);
  const values = draft ?? initialValues;

  // 项目选中值。用户未选时取列表首个。
  const [projectIdOverride, setProjectIdOverride] = useState<string | null>(null);
  const projectId = projectIdOverride ?? projects?.[0]?.id ?? "";

  /* Escape 关闭 */
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const mutation = useMutation({
    mutationFn: () =>
      postQuickCollect({
        project_id: projectId,
        endpoint_type: endpoint.endpoint_type,
        params: serializeParams(form, values),
        label: endpoint.label,
      }),
  });

  const blockReason = evaluateSubmit({
    projectId,
    endpointAllowed: canStartCollection(endpoint),
    endpointStatus: endpoint.status,
    availability: tool?.availability.availability,
    missingConfiguration: tool?.availability.missing_configuration,
    permanentlyBlocked: tool?.permanently_blocked === true,
    toolLoading,
    toolFailed,
    endpointRequiredCount: endpoint.required_params.length,
    form,
    values,
    isPending: mutation.isPending,
  });

  function handleChange(name: string, value: FormValue) {
    setDraft((prev) => ({ ...(prev ?? initialValues), [name]: value }));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (blockReason !== null) return;
    mutation.mutate();
  }

  function handleClose() {
    mutation.reset();
    onClose();
  }

  function handleRetry() {
    mutation.reset();
    // 清空草稿。回到契约默认值。
    setDraft(null);
  }

  if (!open) return null;

  const missingConfig = tool?.availability.missing_configuration ?? [];
  const blockMessage = submitBlockMessage(blockReason);
  const batchLabel =
    batchProgress && batchProgress.total > 1
      ? `批量 ${batchProgress.index + 1} / ${batchProgress.total}`
      : null;

  return (
    <>
      {/* 遮罩 */}
      <div
        className="fixed inset-0 z-40 bg-[var(--overlay-scrim)]"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* 抽屉面板 */}
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={`快速采集：${endpoint.label}`}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-[var(--border-subtle)] bg-[var(--surface-primary)] shadow-[var(--shadow-overlay)]"
      >
        {/* 标题栏 */}
        <div className="flex items-start justify-between border-b border-[var(--border-subtle)] px-6 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-[var(--text-primary)]">快速采集</h2>
              {batchLabel && (
                <span className="rounded-[var(--radius-1)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-xs text-[var(--text-tertiary)]">
                  {batchLabel}
                </span>
              )}
            </div>
            <p className="mt-0.5 truncate text-sm text-[var(--text-secondary)]">
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

        {/* 内容 */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {/* 元信息 */}
          <div className="mb-5 rounded-[var(--radius-2)] bg-[var(--surface-muted)] px-4 py-3 text-xs text-[var(--text-tertiary)]">
            <p>{endpoint.description}</p>
            {endpoint.cost_hint && (
              <p className="mt-1 text-[var(--state-info)]">预估费用：{endpoint.cost_hint}</p>
            )}
            {missingConfig.length > 0 && (
              <p className="mt-1 text-[var(--state-warning)]">
                需先配置：{missingConfig.join("、")}
              </p>
            )}
          </div>

          {endpoint.policy_block_reason && (
            <div
              role="alert"
              className="mb-4 rounded-[var(--radius-2)] border border-[var(--state-warning)] p-3 text-sm text-[var(--text-primary)]"
            >
              <p className="font-semibold">外访安全策略已阻止执行</p>
              <p>{endpoint.policy_block_reason}</p>
            </div>
          )}

          {mutation.isSuccess ? (
            <>
              <RunResult result={mutation.data} />
              <button
                type="button"
                onClick={handleRetry}
                className="mt-4 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              >
                再次采集
              </button>
            </>
          ) : (
            <form onSubmit={handleSubmit} className="grid gap-5">
              {/* 项目选择 */}
              <div className="grid gap-1.5">
                <label
                  htmlFor="quick-collect-project"
                  className="text-sm font-medium text-[var(--text-primary)]"
                >
                  所属项目 <span className="text-[var(--state-danger)]">*</span>
                </label>
                <select
                  id="quick-collect-project"
                  value={projectId}
                  onChange={(e) => setProjectIdOverride(e.target.value)}
                  required
                  className={INPUT_CLASS}
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

              {/* 参数区 */}
              {toolLoading ? (
                <div className="flex items-center gap-2 py-6 text-sm text-[var(--text-tertiary)]">
                  <Loader2 size={16} className="animate-spin" />
                  正在加载参数契约...
                </div>
              ) : toolFailed && endpoint.required_params.length > 0 ? (
                <div
                  role="alert"
                  className="rounded-[var(--radius-2)] border border-[var(--state-danger)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--state-danger)]"
                >
                  参数契约加载失败。无法安全提交。请关闭后重试。
                </div>
              ) : form.fields.length === 0 ? (
                <p className="py-4 text-sm text-[var(--text-tertiary)]">
                  该端点无需参数。可直接提交。
                </p>
              ) : (
                form.fields.map((field) => (
                  <ParamInput
                    key={field.name}
                    field={field}
                    value={values[field.name]}
                    onChange={handleChange}
                  />
                ))
              )}

              {/* 服务端固定目标地址。只读：随 presets 发送，改表单不生效。 */}
              {form.fixedTargetUrl && (
                <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-3 py-2">
                  <p className="text-xs font-medium text-[var(--text-tertiary)]">
                    固定采集地址（不可修改）
                  </p>
                  <p className="mt-1 break-all font-mono text-xs text-[var(--text-secondary)]">
                    {form.fixedTargetUrl}
                  </p>
                </div>
              )}

              {/* 提交阻断提示 */}
              {blockMessage && blockReason !== "pending" && (
                <p className="text-xs text-[var(--text-tertiary)]">{blockMessage}</p>
              )}

              {/* 错误横幅 */}
              {mutation.isError && (
                <div className="rounded-[var(--radius-2)] border border-[var(--state-danger)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--state-danger)]">
                  {mutation.error instanceof ApiError
                    ? mutation.error.message
                    : "采集失败，请稍后重试"}
                </div>
              )}

              {/* 操作区 */}
              <div className="flex flex-col gap-3 pt-2">
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={handleClose}
                    disabled={mutation.isPending}
                    className="flex-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-4 py-2.5 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)] disabled:opacity-50"
                  >
                    {batchProgress && batchProgress.total > 1 ? "跳过" : "取消"}
                  </button>
                  <button
                    type="submit"
                    disabled={blockReason !== null}
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
                {onAbort && (
                  <button
                    type="button"
                    onClick={onAbort}
                    disabled={mutation.isPending}
                    className="w-full rounded-[var(--radius-2)] px-4 py-2 text-xs font-medium text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--state-danger)] disabled:opacity-50"
                  >
                    终止批量采集
                  </button>
                )}
              </div>
            </form>
          )}
        </div>
      </div>
    </>
  );
}
