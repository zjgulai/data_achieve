"use client";

import { useMemo, useState } from "react";
import type { ChangeEvent, FormEvent, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Database,
  Download,
  FileDown,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  UploadCloud,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError } from "@/lib/api/client";
import {
  ABI_QUERY_OPS,
  ABI_QUERY_OP_LABELS,
  createAbiExport,
  createAbiGrant,
  deleteAbiGrant,
  downloadAbiExport,
  fetchAbiDataset,
  fetchAbiDatasets,
  fetchAbiExports,
  fetchAbiGrants,
  fetchAbiOverview,
  fetchAbiPolicy,
  queryAbiDataset,
  uploadAbiBatch,
} from "@/lib/api/abi";
import type {
  AbiAccessGrant,
  AbiDataset,
  AbiDatasetColumn,
  AbiExportFormat,
  AbiExportJob,
  AbiOverview,
  AbiPiiClass,
  AbiQueryFilter,
  AbiQueryOp,
  AbiQueryRequest,
  AbiQueryResult,
  AbiRole,
  AbiSourceKind,
  AbiUploadBatch,
  AbiUploadMode,
} from "@/lib/api/abi";

/* ─────────────────────────────────────────────────────────────
   常量
───────────────────────────────────────────────────────────── */

const TABS = [
  { key: "overview", label: "总览" },
  { key: "catalog", label: "目录" },
  { key: "query", label: "查询" },
  { key: "upload", label: "上传" },
  { key: "export", label: "导出" },
  { key: "admin", label: "管理" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

const SOURCE_KIND_LABELS: Record<AbiSourceKind, string> = {
  apify_platform: "Apify 平台",
  local_table: "本地表",
  upload: "用户上传",
};

const ROLE_LABELS: Record<AbiRole, string> = {
  viewer: "查看者",
  editor: "编辑者",
  publisher: "发布者",
  admin: "管理员",
};

const PII_LABELS: Record<AbiPiiClass, string> = {
  unknown: "未知（默认拒绝）",
  none: "无",
  quasi: "准标识",
  direct: "直接标识",
  secret: "机密（永不返回）",
};

const UPLOAD_STATUS_LABELS: Record<string, string> = {
  pending: "待上传",
  uploaded: "已上传",
  validating: "校验中",
  committed: "已提交",
  failed: "失败",
  expired: "已过期",
};

const EXPORT_STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  awaiting_approval: "待审批",
  running: "生成中",
  succeeded: "已完成",
  failed: "失败",
  expired: "已过期",
  rejected: "已驳回",
};

const EXPORT_FORMAT_LABELS: Record<AbiExportFormat, string> = {
  csv: "CSV",
  xlsx: "XLSX",
  jsonl: "JSONL",
};

const QUERY_LIMIT_OPTIONS = [50, 100, 200, 500] as const;

/** 稳定空数组，避免 useMemo 依赖每次渲染都变化。 */
const EMPTY_DATASETS: AbiDataset[] = [];

/* ─────────────────────────────────────────────────────────────
   格式化
───────────────────────────────────────────────────────────── */

const NUMBER_FORMATTER = new Intl.NumberFormat("zh-CN");

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return NUMBER_FORMATTER.format(value);
}

function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unit]}`;
}

function formatTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "string") return value === "" ? "(空串)" : value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return "[不可序列化]";
  }
}

function parseOptionalInteger(text: string): number | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  const value = Number(trimmed);
  return Number.isInteger(value) && value >= 0 ? value : null;
}

/** 403 按服务端 detail 区分：缺 grant、角色不足、PII 未知列拒绝。 */
function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "登录已失效，请重新登录后再试。";
    if (error.status === 403) {
      if (error.message === "dataset_forbidden") {
        return "服务端拒绝：当前账号对该数据集没有 access_grant（403）。ABI 不提供管理员旁路。";
      }
      if (error.message === "insufficient_role") {
        return "服务端拒绝：当前角色不足（403）。查看 < 编辑 < 发布 < 管理，按操作升级授权。";
      }
      if (error.message === "pii_unknown_denied" || error.message === "pii_policy_not_configured") {
        return "服务端拒绝：请求包含 unknown PII 列（403）。unknown 默认拒绝查询与导出。";
      }
      if (error.message === "export_unmasked_requires_admin") {
        return "服务端拒绝：关闭 PII 遮罩需要该数据集的 admin grant（403）。";
      }
      return `服务端拒绝（403）：${error.message}`;
    }
    if (error.status === 404) {
      return "资源不存在，或当前账号无权看到它（服务端统一按 404 处理）。";
    }
    if (error.status === 410) {
      return "资源已过期（410）。导出文件保留 7 天，请重新创建导出。";
    }
    if (error.status === 413) {
      return `超出限制（413）：${error.message}`;
    }
    if (error.status === 422) {
      return `校验失败（422）：${error.message}`;
    }
    return `请求失败（HTTP ${error.status}）：${error.message}`;
  }
  if (error instanceof Error) return error.message;
  return "未知错误";
}

/* ─────────────────────────────────────────────────────────────
   通用展示组件
───────────────────────────────────────────────────────────── */

function Panel({
  title,
  description,
  actions,
  children,
}: {
  readonly title: string;
  readonly description?: string;
  readonly actions?: ReactNode;
  readonly children: ReactNode;
}) {
  return (
    <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
          {description ? (
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[var(--text-tertiary)]">
              {description}
            </p>
          ) : null}
        </div>
        {actions}
      </header>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function StatCard({
  label,
  value,
  hint,
}: {
  readonly label: string;
  readonly value: string;
  readonly hint?: string;
}) {
  return (
    <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4">
      <p className="text-xs text-[var(--text-tertiary)]">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--text-primary)]">
        {value}
      </p>
      {hint ? <p className="mt-1 text-xs text-[var(--text-tertiary)]">{hint}</p> : null}
    </div>
  );
}

function LoadingBlock({ label = "加载中…" }: { readonly label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-[var(--text-tertiary)]">
      <Loader2 size={22} className="animate-spin" aria-hidden="true" />
      {label}
    </div>
  );
}

function ErrorBlock({
  error,
  onRetry,
  title = "加载失败",
}: {
  readonly error: unknown;
  readonly onRetry?: () => void;
  readonly title?: string;
}) {
  return (
    <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-5 text-sm text-[var(--state-danger)]">
      <div className="flex items-start gap-2">
        <AlertTriangle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="font-medium">{title}</p>
          <p className="mt-1 break-words">{describeError(error)}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--surface-muted)]"
            >
              重试
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function StateBlock({
  icon: Icon,
  title,
  hint,
  action,
}: {
  readonly icon: LucideIcon;
  readonly title: string;
  readonly hint: string;
  readonly action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-6 py-14 text-center">
      <Icon size={28} className="text-[var(--text-tertiary)]" aria-hidden="true" />
      <p className="mt-3 text-sm font-semibold text-[var(--text-primary)]">{title}</p>
      <p className="mt-1 max-w-md text-xs leading-relaxed text-[var(--text-tertiary)]">{hint}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

/** 统一的加载 / 错误 / 空态三态包装。就绪时才渲染 children。 */
function AsyncSection({
  isLoading,
  error,
  isEmpty,
  emptyIcon,
  emptyTitle,
  emptyHint,
  onRetry,
  children,
}: {
  readonly isLoading: boolean;
  readonly error: unknown;
  readonly isEmpty: boolean;
  readonly emptyIcon: LucideIcon;
  readonly emptyTitle: string;
  readonly emptyHint: string;
  readonly onRetry?: () => void;
  readonly children: ReactNode;
}) {
  if (isLoading) return <LoadingBlock />;
  if (error) return <ErrorBlock error={error} onRetry={onRetry} />;
  if (isEmpty) return <StateBlock icon={emptyIcon} title={emptyTitle} hint={emptyHint} />;
  return <>{children}</>;
}

function Table({
  caption,
  headers,
  rows,
}: {
  readonly caption: string;
  readonly headers: ReactNode[];
  readonly rows: ReactNode[][];
}) {
  return (
    <div className="overflow-x-auto rounded-[var(--radius-3)] border border-[var(--border-subtle)]">
      <table className="w-full min-w-[760px] border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-[var(--border-subtle)] bg-[var(--surface-muted)] text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
            {headers.map((header, index) => (
              <th key={index} scope="col" className="px-4 py-3">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className="border-b border-[var(--border-subtle)] last:border-b-0 hover:bg-[var(--surface-muted)]"
            >
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className="max-w-[28rem] px-4 py-3 align-top text-[var(--text-secondary)]"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RefreshButton({
  onClick,
  isFetching,
}: {
  readonly onClick: () => void;
  readonly isFetching: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isFetching}
      className="flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
    >
      {isFetching ? (
        <Loader2 size={13} className="animate-spin" aria-hidden="true" />
      ) : (
        <RefreshCw size={13} aria-hidden="true" />
      )}
      刷新
    </button>
  );
}

function DatasetSelect({
  datasets,
  value,
  onChange,
  label = "数据集",
}: {
  readonly datasets: AbiDataset[];
  readonly value: string;
  readonly onChange: (slug: string) => void;
  readonly label?: string;
}) {
  return (
    <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-w-60 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm text-[var(--text-primary)]"
      >
        <option value="">选择数据集</option>
        {datasets.map((dataset) => (
          <option key={dataset.slug} value={dataset.slug}>
            {dataset.name}（{dataset.slug}）
          </option>
        ))}
      </select>
    </label>
  );
}

function EmptyDatasetsHint() {
  return (
    <p className="text-xs text-[var(--text-tertiary)]">
      当前工作区没有可见数据集。ABI 按 workspace_id + access_grant 取数，
      没有显式 grant 时不会返回任何目录项。
    </p>
  );
}

/* ─────────────────────────────────────────────────────────────
   数据 hooks
───────────────────────────────────────────────────────────── */

function useAbiDatasets() {
  return useQuery({
    queryKey: ["abi", "datasets"],
    queryFn: () => fetchAbiDatasets({ limit: 200 }),
  });
}

/* ─────────────────────────────────────────────────────────────
   总览
───────────────────────────────────────────────────────────── */

function OverviewTab() {
  const query = useQuery({
    queryKey: ["abi", "overview"],
    queryFn: fetchAbiOverview,
  });
  const data: AbiOverview | undefined = query.data;

  return (
    <Panel
      title="数据总览"
      description="只统计当前用户有 grant 的数据集。行数来自目录汇总，不跑全表 count。"
      actions={<RefreshButton onClick={() => void query.refetch()} isFetching={query.isFetching} />}
    >
      <AsyncSection
        isLoading={query.isLoading}
        error={query.error}
        isEmpty={!data || data.dataset_count === 0}
        emptyIcon={Database}
        emptyTitle="还没有 ABI 数据集"
        emptyHint="数据集装载或登记后会出现在总览与目录中。当前工作区没有可见数据集时，请确认已有 access_grant。"
        onRetry={() => void query.refetch()}
      >
        {data ? (
          <div className="grid gap-5">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <StatCard label="数据集" value={formatNumber(data.dataset_count)} hint="有 grant 的目录项" />
              <StatCard label="总行数" value={formatNumber(data.row_count)} hint="目录汇总" />
              <StatCard
                label="PII 待分类数据集"
                value={formatNumber(data.pii_pending_datasets)}
                hint="unknown 字段默认拒绝查询与导出"
              />
              <StatCard label="待处理上传" value={formatNumber(data.uploads_pending)} />
              <StatCard
                label="导出排队 / 生成中"
                value={`${formatNumber(data.exports_queued)} / ${formatNumber(data.exports_running)}`}
              />
              <StatCard label="导出已完成" value={formatNumber(data.exports_succeeded)} />
            </div>
            <p className="text-xs text-[var(--text-tertiary)]">
              统计时间：{formatTime(data.generated_at)}
            </p>
          </div>
        ) : null}
      </AsyncSection>
    </Panel>
  );
}

/* ─────────────────────────────────────────────────────────────
   目录
───────────────────────────────────────────────────────────── */

function CatalogTab() {
  const query = useAbiDatasets();
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<"" | AbiSourceKind>("");
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  const datasets = query.data?.items ?? EMPTY_DATASETS;
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return datasets.filter((dataset) => {
      if (kind && dataset.source_kind !== kind) return false;
      if (!needle) return true;
      return [
        dataset.name,
        dataset.slug,
        dataset.platform ?? "",
        dataset.object_type ?? "",
        dataset.source_table ?? "",
      ].some((value) => value.toLowerCase().includes(needle));
    });
  }, [datasets, kind, search]);

  const detail = useQuery({
    queryKey: ["abi", "dataset", selectedSlug],
    queryFn: () => {
      if (!selectedSlug) throw new Error("未选择数据集");
      return fetchAbiDataset(selectedSlug);
    },
    enabled: selectedSlug !== null,
  });

  const policyByPath = new Map<string, AbiPiiClass>(
    (detail.data?.policy ?? []).map((policy) => [policy.field_path, policy.pii_class]),
  );

  return (
    <div className="grid gap-6">
      <Panel
        title="数据集目录"
        description="目录项只包含当前账号有 grant 的数据集。字段与 PII 策略来自服务端。"
        actions={<RefreshButton onClick={() => void query.refetch()} isFetching={query.isFetching} />}
      >
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
            <span>搜索</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="名称、slug、平台或表名"
              className="min-w-64 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
            />
          </label>
          <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
            <span>来源</span>
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value as "" | AbiSourceKind)}
              className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
            >
              <option value="">全部来源</option>
              <option value="apify_platform">Apify 平台</option>
              <option value="local_table">本地表</option>
              <option value="upload">用户上传</option>
            </select>
          </label>
          {datasets.length === 0 ? <EmptyDatasetsHint /> : null}
        </div>

        <AsyncSection
          isLoading={query.isLoading}
          error={query.error}
          isEmpty={filtered.length === 0}
          emptyIcon={Database}
          emptyTitle={datasets.length === 0 ? "没有可见数据集" : "没有匹配的数据集"}
          emptyHint={
            datasets.length === 0
              ? "ABI 按 workspace_id + access_grant 取数。没有显式 grant 时目录为空。"
              : "调整搜索词或来源筛选后重试。"
          }
          onRetry={() => void query.refetch()}
        >
          <Table
            caption="ABI 数据集目录"
            headers={[
              "数据集",
              "来源",
              "平台 / 类型",
              "行数",
              "版本",
              "PII 扫描",
              "质量",
              "最近装载",
              "字段",
            ]}
            rows={filtered.map((dataset) => [
              <div key={dataset.id}>
                <p className="font-medium text-[var(--text-primary)]">{dataset.name}</p>
                <p className="mt-0.5 break-all font-mono text-[11px] text-[var(--text-tertiary)]">
                  {dataset.slug}
                </p>
              </div>,
              SOURCE_KIND_LABELS[dataset.source_kind] ?? dataset.source_kind,
              [dataset.platform, dataset.object_type].filter(Boolean).join(" / ") || "—",
              formatNumber(dataset.row_count),
              `v${dataset.version}${dataset.is_current ? "" : "（非当前）"}`,
              dataset.pii_scanned ? "已扫描" : "未扫描",
              dataset.quality_status ?? "—",
              formatTime(dataset.last_loaded_at),
              <button
                key={`${dataset.id}-fields`}
                type="button"
                onClick={() => setSelectedSlug(dataset.slug)}
                className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--action-primary)] hover:bg-[var(--surface-muted)]"
              >
                查看
              </button>,
            ])}
          />
        </AsyncSection>
      </Panel>

      {selectedSlug ? (
        <Panel
          title={`字段与 PII 策略 · ${selectedSlug}`}
          description="列名来自服务端物理列登记表。unknown 与 secret 默认拒绝查询和导出。"
          actions={
            <RefreshButton
              onClick={() => void detail.refetch()}
              isFetching={detail.isFetching}
            />
          }
        >
          <AsyncSection
            isLoading={detail.isLoading}
            error={detail.error}
            isEmpty={!detail.data || detail.data.columns.length === 0}
            emptyIcon={FileText}
            emptyTitle="没有登记字段"
            emptyHint="该数据集还没有 dataset_column 记录，查询与导出都无法构造列清单。"
            onRetry={() => void detail.refetch()}
          >
            {detail.data ? (
              <div className="grid gap-5">
                <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
                  <span>{detail.data.columns.length} 列</span>
                  <span>{detail.data.policy.length} 条字段策略</span>
                  <span>{detail.data.dataset.pii_scanned ? "PII 已扫描" : "PII 未扫描"}</span>
                  <span>版本 v{detail.data.dataset.version}</span>
                </div>

                <Table
                  caption={`数据集 ${selectedSlug} 的物理列`}
                  headers={["列名", "类型", "序号", "可空", "可过滤", "可排序", "PII"]}
                  rows={detail.data.columns.map((column) => [
                    <span key={column.id} className="font-mono text-xs text-[var(--text-primary)]">
                      {column.column_name}
                    </span>,
                    column.data_type,
                    String(column.ordinal),
                    column.nullable ? "是" : "否",
                    column.filterable ? "是" : "否",
                    column.sortable ? "是" : "否",
                    PII_LABELS[policyByPath.get(column.column_name) ?? "unknown"],
                  ])}
                />

                {detail.data.policy.length === 0 ? (
                  <p className="rounded-[var(--radius-2)] bg-[var(--state-warning-soft)] px-3 py-2 text-xs text-[var(--state-warning)]">
                    暂无字段策略：所有字段按 unknown 处理，查询与导出默认拒绝。
                  </p>
                ) : (
                  <Table
                    caption="字段 PII 策略"
                    headers={["字段", "PII 等级", "遮罩规则", "决定方", "来源"]}
                    rows={detail.data.policy.map((policy) => [
                      <span key={policy.field_path} className="font-mono text-xs">
                        {policy.field_path}
                      </span>,
                      PII_LABELS[policy.pii_class],
                      policy.mask_rule ?? "—",
                      policy.decided_by,
                      policy.is_default ? "默认" : "已分类",
                    ])}
                  />
                )}
              </div>
            ) : null}
          </AsyncSection>
        </Panel>
      ) : null}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   查询
───────────────────────────────────────────────────────────── */

type FilterDraft = {
  column: string;
  op: AbiQueryOp;
  value: string;
};

function coerceFilterValue(
  column: AbiDatasetColumn | undefined,
  value: string,
): string | number | boolean {
  const dataType = column?.data_type.toLowerCase() ?? "";
  const trimmed = value.trim();
  if (dataType.includes("bool")) {
    if (trimmed.toLowerCase() === "true") return true;
    if (trimmed.toLowerCase() === "false") return false;
  }
  if (
    dataType.includes("int") ||
    dataType.includes("numeric") ||
    dataType.includes("decimal") ||
    dataType.includes("float") ||
    dataType.includes("double") ||
    dataType.includes("real")
  ) {
    const numberValue = Number(trimmed);
    if (trimmed !== "" && Number.isFinite(numberValue)) return numberValue;
  }
  return value;
}

function toFilterPayload(
  draft: FilterDraft,
  columnsByName: Map<string, AbiDatasetColumn>,
): AbiQueryFilter {
  const column = columnsByName.get(draft.column);
  if (draft.op === "is_null" || draft.op === "not_null") {
    return { column: draft.column, op: draft.op, value: null };
  }
  if (draft.op === "in") {
    const parts = draft.value
      .split(",")
      .map((part) => part.trim())
      .filter((part) => part.length > 0)
      .map((part) => coerceFilterValue(column, part));
    return { column: draft.column, op: draft.op, value: parts };
  }
  if (draft.op === "contains") {
    return { column: draft.column, op: draft.op, value: draft.value };
  }
  return {
    column: draft.column,
    op: draft.op,
    value: coerceFilterValue(column, draft.value),
  };
}

function QueryTab() {
  const datasetsQuery = useAbiDatasets();
  const datasets = datasetsQuery.data?.items ?? EMPTY_DATASETS;
  const [slug, setSlug] = useState("");
  const [selectionSlug, setSelectionSlug] = useState("");
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [filters, setFilters] = useState<FilterDraft[]>([{ column: "", op: "eq", value: "" }]);
  const [orderColumn, setOrderColumn] = useState("");
  const [orderDirection, setOrderDirection] = useState<"asc" | "desc">("desc");
  const [limit, setLimit] = useState<number>(100);

  const detail = useQuery({
    queryKey: ["abi", "dataset", slug],
    queryFn: () => {
      if (!slug) throw new Error("未选择数据集");
      return fetchAbiDataset(slug);
    },
    enabled: slug !== "",
  });

  const policyByPath = new Map<string, AbiPiiClass>(
    (detail.data?.policy ?? []).map((policy) => [policy.field_path, policy.pii_class]),
  );
  const piiOf = (columnName: string): AbiPiiClass =>
    policyByPath.get(columnName) ?? "unknown";

  const columns: AbiDatasetColumn[] = detail.data?.columns ?? [];
  const queryableColumns = columns.filter((column) => {
    const pii = piiOf(column.column_name);
    return pii === "none" || pii === "quasi" || pii === "direct";
  });
  const filterColumns = columns.filter((column) => {
    const pii = piiOf(column.column_name);
    return column.filterable && pii !== "secret";
  });
  const sortableColumns = columns.filter((column) => {
    const pii = piiOf(column.column_name);
    return column.sortable && (pii === "none" || pii === "quasi" || pii === "direct");
  });

  const defaultColumns = queryableColumns.map((column) => column.column_name);
  const effectiveColumns = selectionSlug === slug ? selectedColumns : defaultColumns;

  function toggleColumn(name: string, checked: boolean) {
    const next = checked
      ? Array.from(new Set([...effectiveColumns, name]))
      : effectiveColumns.filter((column) => column !== name);
    setSelectionSlug(slug);
    setSelectedColumns(next);
  }

  function updateFilter(index: number, patch: Partial<FilterDraft>) {
    setFilters((current) =>
      current.map((filter, filterIndex) =>
        filterIndex === index ? { ...filter, ...patch } : filter,
      ),
    );
  }

  const columnsByName = new Map<string, AbiDatasetColumn>(
    columns.map((column) => [column.column_name, column]),
  );

  function buildRequest(offset: number): AbiQueryRequest {
    return {
      columns: effectiveColumns,
      filters: filters
        .filter((filter) => filter.column !== "")
        .map((filter) => toFilterPayload(filter, columnsByName)),
      order_by: orderColumn ? [{ column: orderColumn, direction: orderDirection }] : [],
      limit,
      offset,
    };
  }

  const result = useMutation<AbiQueryResult, Error, number>({
    mutationFn: (offset) => {
      if (!slug) throw new Error("未选择数据集");
      return queryAbiDataset(slug, buildRequest(offset));
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slug || effectiveColumns.length === 0) return;
    result.mutate(0);
  }

  /** 换数据集时清空上一份列选择、过滤与结果，避免把旧列名发给新数据集。 */
  function onDatasetChange(next: string) {
    setSlug(next);
    setSelectionSlug("");
    setSelectedColumns([]);
    setFilters([{ column: "", op: "eq", value: "" }]);
    setOrderColumn("");
    setOrderDirection("desc");
    result.reset();
  }

  const allPiiBlocked = detail.data !== undefined && queryableColumns.length === 0;

  return (
    <div className="grid gap-6">
      <Panel
        title="结构化查询"
        description="只提交列名、操作符与值。服务端会从物理列 allowlist 取列、对标识符 quote_ident，并按 op 白名单构造 SQL。"
        actions={<RefreshButton onClick={() => void datasetsQuery.refetch()} isFetching={datasetsQuery.isFetching} />}
      >
        <AsyncSection
          isLoading={datasetsQuery.isLoading}
          error={datasetsQuery.error}
          isEmpty={datasets.length === 0}
          emptyIcon={Database}
          emptyTitle="没有可查询的数据集"
          emptyHint="当前工作区没有可见数据集，或尚未完成 PII 分类。"
          onRetry={() => void datasetsQuery.refetch()}
        >
          <form onSubmit={onSubmit} className="grid gap-5">
            <div className="flex flex-wrap items-end gap-3">
              <DatasetSelect datasets={datasets} value={slug} onChange={onDatasetChange} />
              <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
                <span>每页行数</span>
                <select
                  value={limit}
                  onChange={(event) => setLimit(Number(event.target.value))}
                  className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
                >
                  {QUERY_LIMIT_OPTIONS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {slug === "" ? (
              <p className="text-xs text-[var(--text-tertiary)]">先选择一个数据集。</p>
            ) : detail.isLoading ? (
              <LoadingBlock label="读取列与 PII 策略…" />
            ) : detail.error ? (
              <ErrorBlock error={detail.error} onRetry={() => void detail.refetch()} />
            ) : allPiiBlocked ? (
              <p className="rounded-[var(--radius-2)] bg-[var(--state-warning-soft)] px-3 py-2 text-xs text-[var(--state-warning)]">
                该数据集没有可查询列：所有列都是 unknown / secret，或尚未登记 dataset_column。
                unknown 默认拒绝查询与导出；请等待系统分类器写入字段策略，控制台不提供降级入口。
              </p>
            ) : (
              <>
                <fieldset className="grid gap-2">
                  <legend className="text-xs font-semibold text-[var(--text-secondary)]">
                    返回列（unknown / secret 已禁用）
                  </legend>
                  <div className="flex flex-wrap gap-2">
                    {columns.map((column) => {
                      const pii = piiOf(column.column_name);
                      const disabled = pii === "unknown" || pii === "secret";
                      return (
                        <label
                          key={column.id}
                          className={`flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-2 py-1 text-xs ${
                            disabled
                              ? "text-[var(--text-tertiary)] opacity-60"
                              : "text-[var(--text-secondary)]"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={!disabled && effectiveColumns.includes(column.column_name)}
                            disabled={disabled}
                            onChange={(event) =>
                              toggleColumn(column.column_name, event.target.checked)
                            }
                          />
                          <span className="font-mono">{column.column_name}</span>
                          <span className="text-[var(--text-tertiary)]">{PII_LABELS[pii]}</span>
                        </label>
                      );
                    })}
                  </div>
                </fieldset>

                <fieldset className="grid gap-2">
                  <legend className="text-xs font-semibold text-[var(--text-secondary)]">
                    过滤条件（全部为 AND）
                  </legend>
                  {filters.map((filter, index) => (
                    <div
                      key={index}
                      className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.2fr)_auto]"
                    >
                      <select
                        value={filter.column}
                        onChange={(event) =>
                          updateFilter(index, { column: event.target.value })
                        }
                        className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-2 py-2 text-sm"
                      >
                        <option value="">选择列</option>
                        {filterColumns.map((column) => {
                          const pii = piiOf(column.column_name);
                          return (
                            <option
                              key={column.id}
                              value={column.column_name}
                              disabled={pii === "unknown"}
                            >
                              {column.column_name}
                              {pii === "unknown" ? "（未知，默认拒绝）" : ""}
                            </option>
                          );
                        })}
                      </select>
                      <select
                        value={filter.op}
                        onChange={(event) =>
                          updateFilter(index, { op: event.target.value as AbiQueryOp })
                        }
                        className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-2 py-2 text-sm"
                      >
                        {ABI_QUERY_OPS.map((op) => (
                          <option key={op} value={op}>
                            {ABI_QUERY_OP_LABELS[op]}
                          </option>
                        ))}
                      </select>
                      <input
                        value={filter.value}
                        disabled={filter.op === "is_null" || filter.op === "not_null"}
                        onChange={(event) => updateFilter(index, { value: event.target.value })}
                        placeholder={
                          filter.op === "in"
                            ? "逗号分隔"
                            : filter.op === "is_null" || filter.op === "not_null"
                              ? "不需要值"
                              : "值"
                        }
                        className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm disabled:opacity-50"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setFilters((current) =>
                            current.length === 1
                              ? [{ column: "", op: "eq", value: "" }]
                              : current.filter((_, filterIndex) => filterIndex !== index),
                          )
                        }
                        className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                      >
                        删除
                      </button>
                    </div>
                  ))}
                  <div>
                    <button
                      type="button"
                      onClick={() =>
                        setFilters((current) => [
                          ...current,
                          { column: "", op: "eq", value: "" },
                        ])
                      }
                      className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                    >
                      添加条件
                    </button>
                  </div>
                </fieldset>

                <fieldset className="flex flex-wrap items-end gap-3">
                  <legend className="w-full text-xs font-semibold text-[var(--text-secondary)]">
                    排序
                  </legend>
                  <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
                    <span>排序列</span>
                    <select
                      value={orderColumn}
                      onChange={(event) => setOrderColumn(event.target.value)}
                      className="min-w-48 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
                    >
                      <option value="">不排序</option>
                      {sortableColumns.map((column) => (
                        <option key={column.id} value={column.column_name}>
                          {column.column_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
                    <span>方向</span>
                    <select
                      value={orderDirection}
                      onChange={(event) =>
                        setOrderDirection(event.target.value as "asc" | "desc")
                      }
                      className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
                    >
                      <option value="desc">降序</option>
                      <option value="asc">升序</option>
                    </select>
                  </label>
                </fieldset>

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="submit"
                    disabled={result.isPending || effectiveColumns.length === 0}
                    className="flex items-center gap-2 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] disabled:opacity-50"
                  >
                    {result.isPending ? (
                      <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                    ) : (
                      <Search size={15} aria-hidden="true" />
                    )}
                    执行查询
                  </button>
                  <span className="text-xs text-[var(--text-tertiary)]">
                    已选 {effectiveColumns.length} 列。PII 遮罩在 API 序列化层执行。
                  </span>
                </div>
              </>
            )}
          </form>
        </AsyncSection>
      </Panel>

      <Panel
        title="查询结果"
        description="服务端按结构化条件构造 SQL。分页用 offset，total 来自同条件 count。"
      >
        {result.isPending ? (
          <LoadingBlock label="查询中…" />
        ) : result.error ? (
          <ErrorBlock error={result.error} title="查询失败" onRetry={() => result.mutate(0)} />
        ) : !result.data ? (
          <StateBlock
            icon={Search}
            title="还没有查询结果"
            hint="选择数据集、返回列与过滤条件后执行查询。服务端只读事务有 15 秒超时。"
          />
        ) : result.data.rows.length === 0 ? (
          <StateBlock
            icon={Search}
            title="没有匹配的行"
            hint="当前过滤条件没有命中记录。可放宽条件或换一页。"
          />
        ) : (
          <div className="grid gap-3">
            <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
              <span>本页 {formatNumber(result.data.rows.length)} 行</span>
              <span>总计 {formatNumber(result.data.total)} 行</span>
              <span>
                第 {Math.floor(result.data.offset / result.data.limit) + 1} 页，共{" "}
                {Math.max(1, Math.ceil(result.data.total / result.data.limit))} 页
              </span>
              {result.data.masked_fields.length > 0 ? (
                <span className="rounded-full bg-[var(--state-warning-soft)] px-2 py-0.5 text-[var(--state-warning)]">
                  已遮罩：{result.data.masked_fields.join("、")}
                </span>
              ) : null}
            </div>
            <Table
              caption="ABI 查询结果"
              headers={[
                "#",
                ...result.data.columns.map((column) => (
                  <span key={column} className="font-mono">
                    {column}
                    {result.data?.masked_fields.includes(column) ? "（遮罩）" : ""}
                  </span>
                )),
              ]}
              rows={result.data.rows.map((row, rowIndex) => [
                String(rowIndex + 1),
                ...result.data.columns.map((column) => (
                  <span key={column} className="block max-w-[28rem] break-words">
                    {formatCell(row[column])}
                  </span>
                )),
              ])}
            />
            <div className="flex items-center gap-3">
              <button
                type="button"
                disabled={result.data.offset <= 0 || result.isPending}
                onClick={() =>
                  result.mutate(Math.max(0, (result.data?.offset ?? 0) - (result.data?.limit ?? 0)))
                }
                className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
              >
                上一页
              </button>
              <button
                type="button"
                disabled={
                  result.data.offset + result.data.rows.length >= result.data.total ||
                  result.isPending
                }
                onClick={() =>
                  result.mutate((result.data?.offset ?? 0) + (result.data?.limit ?? 0))
                }
                className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
              >
                下一页
              </button>
              <span className="text-xs text-[var(--text-tertiary)]">
                offset {formatNumber(result.data.offset)}
              </span>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   上传
───────────────────────────────────────────────────────────── */

function UploadTab() {
  const queryClient = useQueryClient();
  const datasetsQuery = useAbiDatasets();
  const datasets = datasetsQuery.data?.items ?? EMPTY_DATASETS;
  const [slug, setSlug] = useState("");
  const [mode, setMode] = useState<AbiUploadMode>("append");
  const [file, setFile] = useState<File | null>(null);
  const [expectedRows, setExpectedRows] = useState("");
  const [fileInputKey, setFileInputKey] = useState(0);

  // 当前路由的上传服务只接受 source_kind=upload 的数据集。
  const uploadTargets = datasets.filter((dataset) => dataset.source_kind === "upload");

  const upload = useMutation<AbiUploadBatch, Error, void>({
    mutationFn: () => {
      if (!slug || !file) throw new Error("未选择数据集或文件");
      return uploadAbiBatch({
        datasetSlug: slug,
        file,
        mode,
        expectedRows: parseOptionalInteger(expectedRows),
      });
    },
    onSuccess: () => {
      setFile(null);
      setFileInputKey((current) => current + 1);
      void queryClient.invalidateQueries({ queryKey: ["abi", "datasets"] });
      void queryClient.invalidateQueries({ queryKey: ["abi", "overview"] });
    },
  });

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slug || !file) return;
    upload.mutate();
  }

  return (
    <div className="grid gap-6">
      <Panel
        title="上传数据"
        description="三步提交：建批次 → PUT 二进制内容（X-Upload-Token）→ commit。服务端复核 sha256、行数与清单。"
        actions={<RefreshButton onClick={() => void datasetsQuery.refetch()} isFetching={datasetsQuery.isFetching} />}
      >
        <AsyncSection
          isLoading={datasetsQuery.isLoading}
          error={datasetsQuery.error}
          isEmpty={uploadTargets.length === 0}
          emptyIcon={UploadCloud}
          emptyTitle="没有可上传的数据集"
          emptyHint="上传目标必须是 source_kind=upload 的 ABI 数据集。请先在目录中登记上传数据集。"
          onRetry={() => void datasetsQuery.refetch()}
        >
          <form onSubmit={onSubmit} className="grid gap-4">
            <div className="flex flex-wrap items-end gap-3">
              <DatasetSelect
                datasets={uploadTargets}
                value={slug}
                onChange={setSlug}
                label="目标数据集"
              />
              <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
                <span>写入模式</span>
                <select
                  value={mode}
                  onChange={(event) => setMode(event.target.value as AbiUploadMode)}
                  className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
                >
                  <option value="append">追加（append）</option>
                  <option value="upsert">更新插入（upsert）</option>
                  <option value="replace">替换版本（replace）</option>
                </select>
              </label>
              <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
                <span>预计行数（可选）</span>
                <input
                  inputMode="numeric"
                  value={expectedRows}
                  onChange={(event) => setExpectedRows(event.target.value)}
                  placeholder="用于 commit 复核"
                  className="w-40 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
                />
              </label>
            </div>

            <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
              <span>文件（CSV，上限 200MB 或 50 万行）</span>
              <input
                key={fileInputKey}
                type="file"
                accept=".csv,text/csv"
                onChange={onFileChange}
                className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
              />
            </label>

            <p className="text-xs text-[var(--text-tertiary)]">
              append / upsert 需要 editor，replace 需要 publisher。控制台不缓存角色判断；
              服务端会重新校验 workspace + grant。commit 会复核 sha256、行数与表头。
            </p>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={upload.isPending || !slug || !file}
                className="flex items-center gap-2 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] disabled:opacity-50"
              >
                {upload.isPending ? (
                  <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                ) : (
                  <UploadCloud size={15} aria-hidden="true" />
                )}
                {upload.isPending ? "上传并校验中…" : "开始上传"}
              </button>
              {file ? (
                <span className="text-xs text-[var(--text-tertiary)]">
                  {file.name} · {formatBytes(file.size)}
                </span>
              ) : null}
            </div>

            {upload.error ? <ErrorBlock error={upload.error} title="上传失败" /> : null}
            {upload.data ? (
              <p className="rounded-[var(--radius-2)] bg-[var(--state-success-soft)] px-3 py-2 text-xs text-[var(--state-success)]">
                批次 {upload.data.id} 状态 {UPLOAD_STATUS_LABELS[upload.data.status] ?? upload.data.status}：
                载入 {formatNumber(upload.data.rows_loaded)} 行，拒绝{" "}
                {formatNumber(upload.data.rows_rejected)} 行。
              </p>
            ) : null}
          </form>
        </AsyncSection>
      </Panel>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   导出
───────────────────────────────────────────────────────────── */

function ExportTab() {
  const queryClient = useQueryClient();
  const datasetsQuery = useAbiDatasets();
  const datasets = datasetsQuery.data?.items ?? EMPTY_DATASETS;
  const [slug, setSlug] = useState("");
  const [format, setFormat] = useState<AbiExportFormat>("csv");
  const [maskPii, setMaskPii] = useState(true);
  const [reason, setReason] = useState("");
  const [columnsText, setColumnsText] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  const exportsQuery = useQuery({
    queryKey: ["abi", "exports"],
    queryFn: () => fetchAbiExports({ limit: 50 }),
  });

  const create = useMutation<AbiExportJob, Error, void>({
    mutationFn: () => {
      if (!slug) throw new Error("未选择数据集");
      return createAbiExport({
        dataset_slug: slug,
        format,
        mask_pii: maskPii,
        columns: columnsText.trim()
          ? columnsText
              .split(",")
              .map((column) => column.trim())
              .filter((column) => column.length > 0)
          : null,
        filters: [],
        order_by: [],
        reason: reason.trim() || null,
      });
    },
    onSuccess: () => {
      setActionError(null);
      setReason("");
      void queryClient.invalidateQueries({ queryKey: ["abi", "exports"] });
      void queryClient.invalidateQueries({ queryKey: ["abi", "overview"] });
    },
    onError: (error) => setActionError(describeError(error)),
  });

  const download = useMutation<void, Error, AbiExportJob>({
    mutationFn: (job) => downloadAbiExport(job),
    onError: (error) => setActionError(describeError(error)),
  });

  const maskOffInvalid = !maskPii && reason.trim().length < 10;

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slug || maskOffInvalid) return;
    create.mutate();
  }

  return (
    <div className="grid gap-6">
      <Panel
        title="创建导出"
        description="默认遮罩 PII。关闭遮罩需要 admin、至少 10 字原因。CSV 注入前缀由服务端处理。"
        actions={<RefreshButton onClick={() => void datasetsQuery.refetch()} isFetching={datasetsQuery.isFetching} />}
      >
        <AsyncSection
          isLoading={datasetsQuery.isLoading}
          error={datasetsQuery.error}
          isEmpty={datasets.length === 0}
          emptyIcon={FileDown}
          emptyTitle="没有可导出的数据集"
          emptyHint="当前工作区没有可见数据集，或尚未完成审计与 PII 分类。"
          onRetry={() => void datasetsQuery.refetch()}
        >
          <form onSubmit={onSubmit} className="grid gap-4">
            <div className="flex flex-wrap items-end gap-3">
              <DatasetSelect datasets={datasets} value={slug} onChange={setSlug} label="数据集" />
              <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
                <span>格式</span>
                <select
                  value={format}
                  onChange={(event) => setFormat(event.target.value as AbiExportFormat)}
                  className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
                >
                  <option value="csv">CSV</option>
                  <option value="jsonl">JSONL</option>
                </select>
              </label>
              <label className="flex items-center gap-2 pb-2 text-xs text-[var(--text-secondary)]">
                <input
                  type="checkbox"
                  checked={maskPii}
                  onChange={(event) => setMaskPii(event.target.checked)}
                />
                遮罩 PII
              </label>
            </div>

            <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
              <span>导出列（可选，逗号分隔；留空表示服务端允许的默认列）</span>
              <input
                value={columnsText}
                onChange={(event) => setColumnsText(event.target.value)}
                placeholder="例如 id,author_id,play_count"
                className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 font-mono text-sm"
              />
            </label>

            <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
              <span>原因{!maskPii ? "（关闭遮罩时必填，至少 10 字）" : "（可选）"}</span>
              <textarea
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                rows={2}
                className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
              />
            </label>

            {maskOffInvalid ? (
              <p className="rounded-[var(--radius-2)] bg-[var(--state-warning-soft)] px-3 py-2 text-xs text-[var(--state-warning)]">
                关闭 PII 遮罩需要至少 10 字原因，且服务端要求 admin grant。
              </p>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={create.isPending || !slug || maskOffInvalid}
                className="flex items-center gap-2 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] disabled:opacity-50"
              >
                {create.isPending ? (
                  <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                ) : (
                  <FileDown size={15} aria-hidden="true" />
                )}
                创建导出任务
              </button>
              <span className="text-xs text-[var(--text-tertiary)]">
                导出文件保留 7 天，过期后下载返回 410。
              </span>
            </div>
          </form>
        </AsyncSection>
      </Panel>

      {actionError ? <ErrorBlock error={new Error(actionError)} title="操作失败" /> : null}
      {create.data ? (
        <p className="rounded-[var(--radius-2)] bg-[var(--state-success-soft)] px-3 py-2 text-xs text-[var(--state-success)]">
          已创建导出任务 {create.data.id}，状态{" "}
          {EXPORT_STATUS_LABELS[create.data.status] ?? create.data.status}。
        </p>
      ) : null}

      <Panel
        title="导出任务"
        actions={<RefreshButton onClick={() => void exportsQuery.refetch()} isFetching={exportsQuery.isFetching} />}
      >
        <AsyncSection
          isLoading={exportsQuery.isLoading}
          error={exportsQuery.error}
          isEmpty={!exportsQuery.data || exportsQuery.data.items.length === 0}
          emptyIcon={FileDown}
          emptyTitle="还没有导出任务"
          emptyHint="创建导出后，任务会经历排队、待审批、生成中与完成。"
          onRetry={() => void exportsQuery.refetch()}
        >
          <Table
            caption="ABI 导出任务"
            headers={["创建时间", "数据集", "格式", "遮罩", "状态", "行数 / 大小", "过期时间", "操作"]}
            rows={(exportsQuery.data?.items ?? []).map((job) => [
              formatTime(job.created_at),
              <span key={`${job.id}-dataset`} className="break-all font-mono text-[11px]">
                {job.dataset_id}
              </span>,
              EXPORT_FORMAT_LABELS[job.format] ?? job.format,
              job.mask_pii ? "是" : "否（需 admin）",
              EXPORT_STATUS_LABELS[job.status] ?? job.status,
              `${formatNumber(job.rows_total)} / ${formatBytes(job.bytes_total)}`,
              formatTime(job.expires_at),
              <div key={`${job.id}-actions`} className="flex flex-wrap gap-2">
                {job.status === "succeeded" ? (
                  <button
                    type="button"
                    disabled={download.isPending}
                    onClick={() => download.mutate(job)}
                    className="flex items-center gap-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--action-primary)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
                  >
                    <Download size={12} aria-hidden="true" />
                    下载
                  </button>
                ) : null}
                {job.status === "expired" ? (
                  <span className="text-xs text-[var(--text-tertiary)]">已过期（410）</span>
                ) : null}
                {job.error ? (
                  <span className="max-w-56 break-words text-xs text-[var(--state-danger)]">
                    {job.error}
                  </span>
                ) : null}
              </div>,
            ])}
          />
        </AsyncSection>
      </Panel>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   管理
───────────────────────────────────────────────────────────── */

function AdminTab() {
  const queryClient = useQueryClient();
  const datasetsQuery = useAbiDatasets();
  const datasets = datasetsQuery.data?.items ?? EMPTY_DATASETS;
  const [slug, setSlug] = useState("");
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<AbiRole>("viewer");
  const [actionError, setActionError] = useState<string | null>(null);

  const grants = useQuery({
    queryKey: ["abi", "grants", slug],
    queryFn: () => {
      if (!slug) throw new Error("未选择数据集");
      return fetchAbiGrants(slug);
    },
    enabled: slug !== "",
  });

  const policies = useQuery({
    queryKey: ["abi", "policy", slug],
    queryFn: () => {
      if (!slug) throw new Error("未选择数据集");
      return fetchAbiPolicy(slug);
    },
    enabled: slug !== "",
  });

  const createGrant = useMutation<AbiAccessGrant, Error, void>({
    mutationFn: () => {
      if (!slug || !userId.trim()) throw new Error("缺少数据集或用户 ID");
      return createAbiGrant(slug, { user_id: userId.trim(), role });
    },
    onSuccess: () => {
      setUserId("");
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["abi", "grants", slug] });
    },
    onError: (error) => setActionError(describeError(error)),
  });

  const removeGrant = useMutation<
    { deleted: boolean; id: string },
    Error,
    string
  >({
    mutationFn: (grantId) => deleteAbiGrant(slug, grantId),
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["abi", "grants", slug] });
    },
    onError: (error) => setActionError(describeError(error)),
  });

  function onCreateGrant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slug || !userId.trim()) return;
    createGrant.mutate();
  }

  return (
    <div className="grid gap-6">
      <Panel
        title="授权与字段策略"
        description="ABI 按 workspace_id + access_grant 双条件取数。admin 不是万能旁路：没有 grant 仍无权访问数据集。"
        actions={<RefreshButton onClick={() => void datasetsQuery.refetch()} isFetching={datasetsQuery.isFetching} />}
      >
        <AsyncSection
          isLoading={datasetsQuery.isLoading}
          error={datasetsQuery.error}
          isEmpty={datasets.length === 0}
          emptyIcon={Users}
          emptyTitle="没有可管理的数据集"
          emptyHint="当前工作区没有可见数据集。"
          onRetry={() => void datasetsQuery.refetch()}
        >
          <div className="flex flex-wrap items-end gap-3">
            <DatasetSelect datasets={datasets} value={slug} onChange={setSlug} />
            <p className="pb-2 text-xs text-[var(--text-tertiary)]">
              管理操作需要该数据集的 admin grant；ABI 不提供 workspace 级旁路。
            </p>
          </div>
        </AsyncSection>
      </Panel>

      {slug ? (
        <>
          {actionError ? <ErrorBlock error={new Error(actionError)} title="操作失败" /> : null}

          <Panel title={`访问授权 · ${slug}`} description="授权只对当前数据集生效；没有显式 grant 的账号不会看到目录项。">
            <form onSubmit={onCreateGrant} className="mb-4 flex flex-wrap items-end gap-3">
              <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
                <span>用户 ID（UUID）</span>
                <input
                  value={userId}
                  onChange={(event) => setUserId(event.target.value)}
                  placeholder="users.id"
                  className="w-80 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 font-mono text-sm"
                />
              </label>
              <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
                <span>角色</span>
                <select
                  value={role}
                  onChange={(event) => setRole(event.target.value as AbiRole)}
                  className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm"
                >
                  {(["viewer", "editor", "publisher", "admin"] as const).map((value) => (
                    <option key={value} value={value}>
                      {ROLE_LABELS[value]}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="submit"
                disabled={createGrant.isPending || !userId.trim()}
                className="rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] disabled:opacity-50"
              >
                {createGrant.isPending ? "授予中…" : "授予"}
              </button>
            </form>

            <AsyncSection
              isLoading={grants.isLoading}
              error={grants.error}
              isEmpty={!grants.data || grants.data.items.length === 0}
              emptyIcon={Users}
              emptyTitle="还没有授权记录"
              emptyHint="没有 grant 时，即使是管理员也不能读取该数据集。"
              onRetry={() => void grants.refetch()}
            >
              <Table
                caption="ABI 数据集授权"
                headers={["用户 ID", "角色", "授予人", "创建时间", "操作"]}
                rows={(grants.data?.items ?? []).map((grant) => [
                  <span key={grant.id} className="break-all font-mono text-xs">
                    {grant.user_id}
                  </span>,
                  ROLE_LABELS[grant.role],
                  grant.granted_by ?? "—",
                  formatTime(grant.created_at),
                  <button
                    key={`${grant.id}-delete`}
                    type="button"
                    disabled={removeGrant.isPending}
                    onClick={() => {
                      if (window.confirm(`撤销 ${grant.user_id} 对该数据集的授权？`)) {
                        removeGrant.mutate(grant.id);
                      }
                    }}
                    className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--state-danger)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
                  >
                    撤销
                  </button>,
                ])}
              />
            </AsyncSection>
          </Panel>

          <Panel
            title={`字段策略 · ${slug}`}
            description="pii_class 由系统分类器写入，控制台不提供降级入口。unknown 默认拒绝查询与导出，secret 永不返回。"
            actions={<RefreshButton onClick={() => void policies.refetch()} isFetching={policies.isFetching} />}
          >
            <AsyncSection
              isLoading={policies.isLoading}
              error={policies.error}
              isEmpty={!policies.data || policies.data.items.length === 0}
              emptyIcon={ShieldAlert}
              emptyTitle="还没有字段策略"
              emptyHint="没有策略的字段按 unknown 处理，默认拒绝查询与导出。"
              onRetry={() => void policies.refetch()}
            >
              <Table
                caption="ABI 字段 PII 策略"
                headers={["字段", "PII 等级", "遮罩规则", "决定方", "来源"]}
                rows={(policies.data?.items ?? []).map((policy) => [
                  <span key={policy.field_path} className="break-all font-mono text-xs">
                    {policy.field_path}
                  </span>,
                  PII_LABELS[policy.pii_class],
                  policy.mask_rule ?? "—",
                  policy.decided_by,
                  policy.is_default ? "默认 unknown" : "已分类",
                ])}
              />
            </AsyncSection>
          </Panel>
        </>
      ) : null}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   页面
───────────────────────────────────────────────────────────── */

export default function AbiDashboardPage() {
  const [tab, setTab] = useState<TabKey>("overview");

  return (
    <AppShell
      title="ABI 看板"
      description="外部数据中心：Apify 与本地原始表的目录、结构化查询、上传、导出与授权管理。"
      breadcrumbs={[{ label: "ABI 看板" }]}
    >
      <div
        role="tablist"
        aria-label="ABI 功能页签"
        className="flex flex-wrap gap-1 border-b border-[var(--border-subtle)] pb-2"
      >
        {TABS.map((item) => {
          const active = item.key === tab;
          return (
            <button
              key={item.key}
              id={`abi-tab-${item.key}`}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls={`abi-panel-${item.key}`}
              onClick={() => setTab(item.key)}
              className={`rounded-[var(--radius-2)] px-3 py-2 text-sm font-medium ${
                active
                  ? "bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      <div
        id={`abi-panel-${tab}`}
        role="tabpanel"
        aria-labelledby={`abi-tab-${tab}`}
      >
        {tab === "overview" ? <OverviewTab /> : null}
        {tab === "catalog" ? <CatalogTab /> : null}
        {tab === "query" ? <QueryTab /> : null}
        {tab === "upload" ? <UploadTab /> : null}
        {tab === "export" ? <ExportTab /> : null}
        {tab === "admin" ? <AdminTab /> : null}
      </div>
    </AppShell>
  );
}
