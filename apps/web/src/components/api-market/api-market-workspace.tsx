"use client";

import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  Filter,
  Layers3,
  ListFilter,
  Loader2,
  Search,
  ScanSearch,
  TableProperties,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { CapabilityComparisonPanel } from "@/components/api-market/capability-comparison-panel";
import { CapabilityDetailDrawer } from "@/components/api-market/capability-detail-drawer";
import { CapabilityListView } from "@/components/api-market/capability-list-view";
import { CapabilityMatrixView } from "@/components/api-market/capability-matrix-view";
import { CapabilityScenarioView } from "@/components/api-market/capability-scenario-view";
import {
  WorkbenchFact,
  WorkbenchPanel,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import {
  getCapabilityImplementationDetail,
  getCapabilityMatrix,
  listCapabilityAssertions,
  listCapabilityImplementations,
} from "@/lib/api/capabilities";
import {
  buildImplementationComparison,
  capabilityAccessChannels,
  capabilityOperations,
  capabilityPlatforms,
  capabilityPlatformLabel,
  capabilityResourceTypes,
  capabilityStatuses,
  capabilityStatusLabel,
  filterCapabilityImplementations,
  filterCapabilityMatrixCells,
  parseCapabilityMarketFilters,
  updateCapabilityMarketQuery,
  type CapabilityImplementationComparison,
  type CapabilityMarketFilters,
  type CapabilityMarketQueryPatch,
  type CapabilityMarketView,
} from "@/lib/capability-market";
import type {
  CapabilityAssertion,
  CapabilityImplementation,
  CapabilityMatrix,
  CapabilityMatrixCell,
} from "@/types/capability";

type CapabilityMarketData = {
  matrix: CapabilityMatrix;
  implementations: CapabilityImplementation[];
  assertions: CapabilityAssertion[];
};

type ApiMarketWorkspaceProps = {
  initialView: CapabilityMarketView;
  initialFilters: CapabilityMarketFilters;
};

const viewTabs: ReadonlyArray<{
  icon: typeof Boxes;
  label: string;
  value: CapabilityMarketView;
}> = [
  { icon: Boxes, label: "场景视图", value: "scenarios" },
  { icon: TableProperties, label: "矩阵视图", value: "matrix" },
  { icon: ListFilter, label: "列表视图", value: "list" },
];

const accessChannelLabels = {
  authorized_browser: "授权浏览器",
  authorized_export_import: "授权导入导出",
  licensed_partner_data_service: "持牌合作数据服务",
  managed_opaque_collector: "托管黑盒采集器",
  official_authorized_api: "官方授权 API",
  public_web_feed: "公开 Web / Feed",
} as const;

const resourceTypeLabels = {
  commerce_ads: "商业与广告",
  content: "内容",
  conversation: "评论与对话",
  creator: "创作者",
  media_live: "直播媒体",
  metrics: "指标",
  relationship_graph: "关系图谱",
  topic: "主题",
} as const;

const operationLabels = {
  backfill_history: "历史回填",
  batch_parse: "批量解析",
  export_download: "导出下载",
  list_enumerate: "列表枚举",
  monitor_incremental: "增量监测",
  resolve_detail: "详情解析",
  search_discover: "搜索发现",
} as const;

export function ApiMarketWorkspace({
  initialFilters,
  initialView,
}: ApiMarketWorkspaceProps) {
  const [data, setData] = useState<CapabilityMarketData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [view, setView] = useState<CapabilityMarketView>(initialView);
  const [filters, setFilters] =
    useState<CapabilityMarketFilters>(initialFilters);
  const [selectedCell, setSelectedCell] =
    useState<CapabilityMatrixCell | null>(null);
  const [selectedImplementationId, setSelectedImplementationId] = useState<
    string | null
  >(null);
  const [returnFocusTo, setReturnFocusTo] = useState<HTMLElement | null>(null);
  const [comparison, setComparison] =
    useState<CapabilityImplementationComparison | null>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const comparisonRequestIdRef = useRef(0);
  const comparisonReturnFocusToRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    setData(null);
    setLoadError(null);
    void Promise.all([
      getCapabilityMatrix(),
      listCapabilityImplementations(),
      listCapabilityAssertions(),
    ])
      .then(([matrix, implementations, assertions]) => {
        if (!cancelled) {
          setData({ assertions, implementations, matrix });
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setLoadError(
            cause instanceof Error
              ? cause.message
              : "capability_market_unavailable",
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(
    () => () => {
      comparisonRequestIdRef.current += 1;
    },
    [],
  );

  useEffect(() => {
    setView(initialView);
  }, [initialView]);

  useEffect(() => {
    setFilters(initialFilters);
  }, [initialFilters]);

  const filteredImplementations = useMemo(
    () =>
      data
        ? filterCapabilityImplementations(
            data.implementations,
            data.assertions,
            filters,
          )
        : [],
    [data, filters],
  );
  const filteredImplementationIds = useMemo(
    () =>
      new Set(
        filteredImplementations.map(
          (implementation) => implementation.implementationId,
        ),
      ),
    [filteredImplementations],
  );
  const filteredAssertions = useMemo(() => {
    if (!data) {
      return [];
    }
    return data.assertions.filter(
      (assertion) =>
        filteredImplementationIds.has(assertion.implementation_id) &&
        (!filters.resourceType ||
          assertion.resource_type === filters.resourceType) &&
        (!filters.operation || assertion.operation === filters.operation) &&
        (!filters.status || assertion.support_status === filters.status),
    );
  }, [data, filteredImplementationIds, filters.operation, filters.resourceType, filters.status]);
  const filteredCells = useMemo(() => {
    if (!data) {
      return [];
    }
    const scopedCells = filterCapabilityMatrixCells(data.matrix.cells, filters);
    if (!filters.query && !filters.resourceType && !filters.operation) {
      return scopedCells;
    }
    return scopedCells.filter((cell) =>
      cell.implementationIds.some((implementationId) =>
        filteredImplementationIds.has(implementationId),
      ),
    );
  }, [data, filteredImplementationIds, filters]);

  function replaceQuery(patch: CapabilityMarketQueryPatch): string {
    const nextSearch = updateCapabilityMarketQuery(
      window.location.search.slice(1),
      patch,
    );
    const nextUrl = `${window.location.pathname}${
      nextSearch ? `?${nextSearch}` : ""
    }${window.location.hash}`;
    window.history.replaceState(window.history.state, "", nextUrl);
    return nextSearch;
  }

  function patchFilters(patch: CapabilityMarketQueryPatch) {
    const nextSearch = replaceQuery(patch);
    setFilters(parseCapabilityMarketFilters(nextSearch));
  }

  function selectView(nextView: CapabilityMarketView) {
    setView(nextView);
    replaceQuery({ view: nextView });
  }

  function selectCell(cell: CapabilityMatrixCell, trigger: HTMLElement) {
    setReturnFocusTo(trigger);
    setSelectedImplementationId(null);
    setSelectedCell(cell);
  }

  function selectImplementation(
    implementationId: string,
    trigger: HTMLElement,
  ) {
    setReturnFocusTo(trigger);
    setSelectedCell(null);
    setSelectedImplementationId(implementationId);
  }

  function closeDetail() {
    setSelectedCell(null);
    setSelectedImplementationId(null);
  }

  async function compareImplementations(implementationIds: string[]) {
    const requestId = comparisonRequestIdRef.current + 1;
    comparisonRequestIdRef.current = requestId;
    comparisonReturnFocusToRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setComparison(null);
    setComparisonError(null);
    try {
      const details = await Promise.all(
        implementationIds.map((implementationId) =>
          getCapabilityImplementationDetail(implementationId),
        ),
      );
      if (requestId !== comparisonRequestIdRef.current) {
        return;
      }
      setComparison(buildImplementationComparison(details));
    } catch {
      if (requestId !== comparisonRequestIdRef.current) {
        return;
      }
      setComparisonError("实现比较失败，请复核同平台与共享能力范围。");
    }
  }

  function closeComparison() {
    comparisonRequestIdRef.current += 1;
    setComparison(null);
    requestAnimationFrame(() => comparisonReturnFocusToRef.current?.focus());
  }

  if (loadError) {
    return (
      <WorkbenchPanel
        icon={AlertTriangle}
        label="Load error"
        title="能力事实加载失败"
      >
        <p
          className="rounded-xl border border-[#FFD0C8] bg-[#FFF1EC] p-4 text-sm font-semibold text-[#B85F4F]"
          role="alert"
        >
          {loadError} · 未使用静态能力事实回退
        </p>
      </WorkbenchPanel>
    );
  }

  if (!data) {
    return (
      <p
        className="inline-flex min-h-24 items-center justify-center gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-5 text-sm font-semibold text-[#7A625A]"
        role="status"
      >
        <Loader2 className="animate-spin" size={18} aria-hidden="true" />
        正在加载 7×6 能力事实矩阵…
      </p>
    );
  }

  return (
    <div className="grid min-w-0 gap-5">
      <WorkbenchPanel
        action={<WorkbenchTag tone="rose">Candidate 不可执行</WorkbenchTag>}
        icon={Layers3}
        label="Capability Market"
        subtitle="场景用于定位需求，矩阵用于审查覆盖，列表用于复核实现证据。"
        title="能力事实审查台"
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <WorkbenchFact label="matrix cells" value={String(data.matrix.summary.cellCount)} />
          <WorkbenchFact label="evidence level" value={data.matrix.evidenceLevel} />
          <WorkbenchFact label="provider_call" value={String(data.matrix.providerCall)} />
          <WorkbenchFact
            label="production_write_allowed"
            value={String(data.matrix.productionWriteAllowed)}
          />
        </div>
        <div className="mt-4 flex min-w-0 flex-col gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFF8F5] p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-[#7D4F43]">
              <ScanSearch size={16} aria-hidden="true" />
              从离线来源快照审查新的能力候选
            </p>
            <p className="mt-1 text-xs leading-5 text-[#7A625A]">
              Discovery 是独立 Preview，不改变当前三种 Catalog 视图与 42-cell 矩阵。
            </p>
          </div>
          <Link
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-[#C96F5C] bg-white px-4 text-sm font-semibold text-[#B85F4F] outline-none transition hover:bg-[#FFF1EC] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
            href="/api-market/discovery"
          >
            打开能力发现 Preview
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </div>
      </WorkbenchPanel>

      <section
        aria-label="能力市场视图"
        className="grid gap-4 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4 shadow-[0_16px_42px_rgba(72,45,38,0.05)]"
      >
        <div className="grid grid-cols-3 gap-2" role="group" aria-label="视图切换">
          {viewTabs.map((tab) => {
            const Icon = tab.icon;
            const active = view === tab.value;
            return (
              <button
                aria-pressed={active}
                className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border px-3 text-sm font-semibold outline-none transition focus-visible:ring-4 focus-visible:ring-[#F3D7CE] ${
                  active
                    ? "border-[#C96F5C] bg-[#C96F5C] text-white"
                    : "border-[#E8D4CB] bg-white text-[#7A625A] hover:border-[#C96F5C] hover:text-[#7D4F43]"
                }`}
                key={tab.value}
                onClick={() => selectView(tab.value)}
                type="button"
              >
                <Icon size={16} aria-hidden="true" />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="grid gap-3 border-t border-[#F0E1D9] pt-4 sm:grid-cols-2 xl:grid-cols-6">
          <FilterSelect
            label="平台"
            onChange={(value) =>
              patchFilters({
                platform:
                  (value || null) as CapabilityMarketQueryPatch["platform"],
              })
            }
            options={capabilityPlatforms.map((platform) => ({
              label: capabilityPlatformLabel(platform),
              value: platform,
            }))}
            testId="capability-filter-platform"
            value={filters.platform ?? ""}
          />
          <FilterSelect
            label="接入渠道"
            onChange={(value) =>
              patchFilters({
                accessChannel:
                  (value || null) as CapabilityMarketQueryPatch["accessChannel"],
              })
            }
            options={capabilityAccessChannels.map((accessChannel) => ({
              label: accessChannelLabels[accessChannel],
              value: accessChannel,
            }))}
            testId="capability-filter-channel"
            value={filters.accessChannel ?? ""}
          />
          <FilterSelect
            label="资源"
            onChange={(value) =>
              patchFilters({
                resourceType:
                  (value || null) as CapabilityMarketQueryPatch["resourceType"],
              })
            }
            options={capabilityResourceTypes.map((resourceType) => ({
              label: resourceTypeLabels[resourceType],
              value: resourceType,
            }))}
            testId="capability-filter-resource"
            value={filters.resourceType ?? ""}
          />
          <FilterSelect
            label="操作"
            onChange={(value) =>
              patchFilters({
                operation:
                  (value || null) as CapabilityMarketQueryPatch["operation"],
              })
            }
            options={capabilityOperations.map((operation) => ({
              label: operationLabels[operation],
              value: operation,
            }))}
            testId="capability-filter-operation"
            value={filters.operation ?? ""}
          />
          <FilterSelect
            label="状态"
            onChange={(value) =>
              patchFilters({
                status: (value || null) as CapabilityMarketQueryPatch["status"],
              })
            }
            options={capabilityStatuses.map((status) => ({
              label: capabilityStatusLabel(status),
              value: status,
            }))}
            testId="capability-filter-status"
            value={filters.status ?? ""}
          />
          <label className="grid min-w-0 gap-2 text-xs font-semibold uppercase text-[#B47767]">
            <span className="inline-flex items-center gap-2">
              <Search size={13} aria-hidden="true" />
              搜索
            </span>
            <input
              aria-label="搜索能力实现"
              className="h-10 min-w-0 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm normal-case text-[#3B2924] outline-none transition placeholder:text-[#B7A49C] focus-visible:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
              data-testid="capability-filter-query"
              onChange={(event) => patchFilters({ query: event.target.value })}
              placeholder="provider / capability"
              type="search"
              value={filters.query ?? ""}
            />
          </label>
        </div>
      </section>

      {view === "scenarios" ? (
        <CapabilityScenarioView
          assertions={filteredAssertions}
          evidenceLevel={data.matrix.evidenceLevel}
          implementations={filteredImplementations}
          onSelectImplementation={selectImplementation}
        />
      ) : null}
      {view === "matrix" ? (
        <CapabilityMatrixView
          cells={filteredCells}
          evidenceLevel={data.matrix.evidenceLevel}
          generatedAt={data.matrix.generatedAt}
          mobilePlatform={filters.platform ?? "youtube"}
          onMobilePlatformChange={(platform) => patchFilters({ platform })}
          onSelectCell={selectCell}
          summary={data.matrix.summary}
        />
      ) : null}
      {view === "list" ? (
        <CapabilityListView
          assertions={data.assertions}
          evidenceLevel={data.matrix.evidenceLevel}
          implementations={filteredImplementations}
          onCompare={compareImplementations}
          onSelectImplementation={selectImplementation}
        />
      ) : null}

      {comparisonError ? (
        <p
          className="rounded-xl border border-[#FFD0C8] bg-[#FFF1EC] p-4 text-sm font-semibold text-[#B85F4F]"
          role="alert"
        >
          {comparisonError}
        </p>
      ) : null}

      <CapabilityDetailDrawer
        cell={selectedCell}
        evidenceLevel={data.matrix.evidenceLevel}
        generatedAt={data.matrix.generatedAt}
        implementationId={selectedImplementationId}
        onClose={closeDetail}
        returnFocusTo={returnFocusTo}
      />
      {comparison ? (
        <CapabilityComparisonPanel
          comparison={comparison}
          onClose={closeComparison}
        />
      ) : null}
    </div>
  );
}

function FilterSelect({
  label,
  onChange,
  options,
  testId,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: ReadonlyArray<{ label: string; value: string }>;
  testId: string;
  value: string;
}) {
  return (
    <label className="grid min-w-0 gap-2 text-xs font-semibold uppercase text-[#B47767]">
      <span className="inline-flex items-center gap-2">
        <Filter size={13} aria-hidden="true" />
        {label}
      </span>
      <select
        className="h-10 min-w-0 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm normal-case text-[#3B2924] outline-none transition focus-visible:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
        data-testid={testId}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        <option value="">全部</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
