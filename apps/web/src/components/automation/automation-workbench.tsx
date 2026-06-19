"use client";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Code2,
  Database,
  ExternalLink,
  Link2,
  Loader2,
  Search,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  analyzeAutomationSite,
  approveAutomationProductSchedule,
  checkAutomationProductDrift,
  createAutomationCleaningPlan,
  createAutomationProductFanout,
  discoverAutomationProducts,
  dryRunAutomationCleaningPlan,
  listAutomationPlatformPackages,
  listAutomationSiteAnalyses,
  listAutomationProductDriftEvents,
  previewAutomationProductDataset,
  previewAutomationProductFanout,
  runAutomationProductBatch,
  saveAutomationProductDriftEvent,
  saveAutomationProductDataset,
} from "@/lib/api/automation";
import { listProjects } from "@/lib/api/projects";
import { createSource, enableSource } from "@/lib/api/sources";
import { runTask } from "@/lib/api/tasks";
import { cn } from "@/lib/utils";
import type { Project } from "@/types/project";
import type { CollectionTask, Source, TaskRun } from "@/types/source-task";
import type {
  AutomationCleaningPlanCreate,
  AutomationCleaningPlanDryRun,
  AutomationCleaningRule,
  AutomationFieldCandidate,
  AutomationProductBatchRun,
  AutomationProductDatasetPreview,
  AutomationProductDatasetSave,
  AutomationProductDiscovery,
  AutomationProductDriftCheck,
  AutomationProductDriftEvent,
  AutomationProductFanoutCreate,
  AutomationProductFanoutPreview,
  AutomationPlatformPackage,
  AutomationProductScheduleApprove,
  AutomationSiteAnalysis,
  AutomationSiteAnalysisHistoryItem,
} from "@/types/automation";

const defaultFields = [
  "title",
  "price",
  "currency",
  "availability",
  "sku",
  "brand",
  "description",
  "image_url",
  "canonical_url",
];

const fieldLabels: Record<string, string> = {
  availability: "库存",
  brand: "品牌",
  canonical_url: "规范 URL",
  currency: "货币",
  description: "描述",
  image_url: "主图",
  price: "价格",
  sku: "SKU",
  title: "标题",
};

type GitHubTopicRunState = {
  source: Source;
  task: CollectionTask;
  run: TaskRun | null;
  topic: string;
  maxResults: number;
};

function defaultCleaningRulesForFields(fields: string[]): AutomationCleaningRule[] {
  const rules: AutomationCleaningRule[] = [];
  if (fields.includes("title")) {
    rules.push({
      field: "title",
      operation: "strip_text",
      description: "去除标题首尾空白并合并重复空格。",
    });
  }
  if (fields.includes("price")) {
    rules.push({
      field: "price",
      operation: "parse_decimal",
      description: "将价格转换为 decimal number。",
    });
  }
  if (fields.includes("currency")) {
    rules.push({
      field: "currency",
      operation: "uppercase",
      description: "货币代码转为大写。",
    });
  }
  if (fields.includes("availability")) {
    rules.push({
      field: "availability",
      operation: "normalize_availability",
      description: "库存状态归一为 in_stock/out_of_stock/unknown。",
    });
  }
  if (fields.includes("sku")) {
    rules.push({
      field: "sku",
      operation: "fill_default",
      value: "UNKNOWN-SKU",
      description: "缺失 SKU 时保留可审计默认值。",
    });
  }
  if (fields.includes("canonical_url")) {
    rules.push({
      field: "canonical_url",
      operation: "normalize_url",
      description: "规范 URL 字段格式。",
    });
  }
  return rules;
}

type AutomationMode = "product_page" | "product_discovery" | "github_topic_radar";

export function AutomationWorkbench() {
  const [mode, setMode] = useState<AutomationMode>("product_page");
  const [url, setUrl] = useState("https://shop.example/products/demo-bag");
  const [authorized, setAuthorized] = useState(false);
  const [maxProducts, setMaxProducts] = useState("50");
  const [githubTopic, setGithubTopic] = useState("web-scraping");
  const [githubMaxResults, setGithubMaxResults] = useState("20");
  const [githubRun, setGithubRun] = useState<GitHubTopicRunState | null>(null);
  const [fields, setFields] = useState<string[]>([
    "title",
    "price",
    "currency",
    "availability",
    "sku",
    "brand",
    "canonical_url",
  ]);
  const [analysis, setAnalysis] = useState<AutomationSiteAnalysis | null>(null);
  const [discovery, setDiscovery] = useState<AutomationProductDiscovery | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [analysisHistory, setAnalysisHistory] = useState<AutomationSiteAnalysisHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [platformPackages, setPlatformPackages] = useState<AutomationPlatformPackage[]>([]);
  const [platformPackageLoading, setPlatformPackageLoading] = useState(false);
  const [platformPackageError, setPlatformPackageError] = useState<string | null>(null);
  const [appliedPlatformPackage, setAppliedPlatformPackage] =
    useState<AutomationPlatformPackage | null>(null);

  useEffect(() => {
    let mounted = true;
    listProjects()
      .then((items) => {
        if (!mounted) {
          return;
        }
        setProjects(items);
        const ecommerceProject = items.find((project) => project.domain === "ecommerce");
        setSelectedProjectId(ecommerceProject?.id ?? items[0]?.id ?? "");
      })
      .catch(() => {
        if (mounted) {
          setProjects([]);
          setSelectedProjectId("");
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    setPlatformPackageLoading(true);
    setPlatformPackageError(null);
    listAutomationPlatformPackages()
      .then((result) => {
        if (!mounted) {
          return;
        }
        setPlatformPackages(result.items);
      })
      .catch((caught) => {
        if (!mounted) {
          return;
        }
        setPlatformPackageError(
          caught instanceof Error ? caught.message : "Platform package loading failed",
        );
      })
      .finally(() => {
        if (mounted) {
          setPlatformPackageLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedProjectId) {
      setAnalysisHistory([]);
      return;
    }
    void refreshAnalysisHistory(selectedProjectId);
  }, [selectedProjectId]);

  const selectedFieldCount = useMemo(
    () => analysis?.fieldCandidates.filter((field) => field.selected).length ?? fields.length,
    [analysis, fields.length],
  );

  async function runGitHubTopicRadar() {
    if (!selectedProjectId) {
      setError("请选择写入项目后再创建 GitHub Topic Radar。");
      return;
    }
    const topic = normalizeGitHubTopic(githubTopic);
    if (!topic) {
      setError("请填写 GitHub topic，例如 web-scraping。");
      return;
    }
    const maxResults = clampInteger(Number.parseInt(githubMaxResults, 10), 1, 100, 20);
    setLoading(true);
    try {
      const source = await createSource({
        projectId: selectedProjectId,
        name: `GitHub Topic Radar: ${topic}`,
        type: "github_topic",
        url: `https://github.com/topics/${topic}`,
        config: {
          topic,
          max_results: maxResults,
        },
      });
      const task = await enableSource(source.id);
      const run = await runTask(task.id);
      setGithubRun({ source, task, run, topic, maxResults });
      setAnalysis(null);
      setDiscovery(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "GitHub Topic Radar run failed");
    } finally {
      setLoading(false);
    }
  }

  async function submitAutomation() {
    setError(null);
    if (!authorized) {
      setError("请先确认目标为公开页面或公开 API，且你有权进行采集分析。");
      return;
    }
    if (mode === "github_topic_radar") {
      await runGitHubTopicRadar();
      return;
    }
    if (!url.trim()) {
      setError(mode === "product_discovery" ? "请填写待发现的集合页 URL。" : "请填写待分析的商品页 URL。");
      return;
    }
    setLoading(true);
    try {
      if (mode === "product_discovery") {
        const result = await discoverAutomationProducts({
          url: url.trim(),
          authorized,
          maxProducts: Number.parseInt(maxProducts, 10) || 50,
        });
        setDiscovery(result);
        setAnalysis(null);
        setGithubRun(null);
        return;
      }
      const result = await analyzeAutomationSite({
        projectId: selectedProjectId || undefined,
        url: url.trim(),
        authorized,
        fields,
      });
      setAnalysis(result);
      setDiscovery(null);
      setGithubRun(null);
      if (selectedProjectId) {
        void refreshAnalysisHistory(selectedProjectId);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Automation analysis failed");
    } finally {
      setLoading(false);
    }
  }

  async function refreshAnalysisHistory(projectId: string) {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const result = await listAutomationSiteAnalyses({
        projectId,
        target: "ecommerce_product",
        limit: 5,
      });
      setAnalysisHistory(result.items);
    } catch (caught) {
      setHistoryError(caught instanceof Error ? caught.message : "Analysis history failed");
    } finally {
      setHistoryLoading(false);
    }
  }

  function toggleField(field: string) {
    setFields((current) => {
      if (current.includes(field)) {
        return current.filter((item) => item !== field);
      }
      return [...current, field];
    });
  }

  function applyPlatformPackage(platformPackage: AutomationPlatformPackage) {
    const executableStrategy =
      platformPackage.strategyMatrix.find(
        (strategy) =>
          strategy.canStartFromAutomation &&
          strategy.entrypoint === platformPackage.defaultEntrypoint,
      ) ??
      platformPackage.strategyMatrix.find(
        (strategy) => strategy.canStartFromAutomation && strategy.entrypoint === "product-discovery",
      ) ??
      platformPackage.strategyMatrix.find(
        (strategy) => strategy.canStartFromAutomation && strategy.entrypoint === "site-analysis",
      ) ??
      platformPackage.strategyMatrix.find(
        (strategy) => strategy.canStartFromAutomation,
      );
    if (!executableStrategy) {
      return;
    }
    setFields(platformPackage.fieldSchema.map((field) => field.key));
    setAppliedPlatformPackage(platformPackage);
    setAnalysis(null);
    setDiscovery(null);
    setGithubRun(null);
    const sampleUrl = platformPackage.sampleUrls.find(
      (sample) => sample.entrypoint === executableStrategy.entrypoint,
    );
    if (executableStrategy.collectorType === "github_topic") {
      setMode("github_topic_radar");
      setGithubTopic(topicFromGitHubUrl(sampleUrl?.url) ?? "web-scraping");
      setGithubMaxResults("20");
      const osintProject = projects.find((project) => project.domain === "osint");
      if (osintProject) {
        setSelectedProjectId(osintProject.id);
      }
      return;
    }
    if (executableStrategy.entrypoint === "product-discovery") {
      setMode("product_discovery");
      setUrl(sampleUrl?.url ?? "https://shop.example/collections/summer-bags");
      return;
    }
    setMode("product_page");
    setUrl(sampleUrl?.url ?? "https://shop.example/products/demo-bag");
  }

  return (
    <div className="grid min-w-0 gap-5">
      <section className="overflow-hidden rounded-2xl border border-[#EDDCD3] bg-[#FFF8F4] shadow-[0_18px_60px_rgba(115,70,58,0.08)]">
        <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_400px]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <Search size={14} aria-hidden="true" />
              Automation Intake
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C] sm:text-3xl">
              URL 到结构化采集计划
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[#7A625A]">
              针对公开电商页面和 GitHub API-first topic 先做结构解析。商品发现用于提取候选 URL，Topic Radar 用于把公开仓库元数据写入采集源、任务和运行结果。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <MetricPill icon={ShieldCheck} label="授权边界" value={authorized ? "已确认" : "待确认"} />
              <MetricPill
                icon={SlidersHorizontal}
                label={
                  mode === "github_topic_radar"
                    ? "仓库上限"
                    : mode === "product_discovery"
                      ? "候选上限"
                      : "目标字段"
                }
                value={
                  mode === "github_topic_radar"
                    ? `${githubMaxResults || "20"} 条`
                    : mode === "product_discovery"
                      ? `${maxProducts || "50"} 条`
                      : `${fields.length} 个`
                }
              />
              <MetricPill
                icon={Database}
                label="结构保存"
                value={
                  mode === "github_topic_radar"
                    ? githubRun
                      ? `${githubRun.run?.recordsCount ?? 0} 条`
                      : "待运行"
                    : mode === "product_discovery"
                    ? discovery
                      ? `${discovery.productCandidates.length} URL`
                      : "待发现"
                    : analysis
                      ? `${selectedFieldCount} 字段`
                      : "待分析"
                }
              />
            </div>
          </div>

          <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void submitAutomation();
              }}
            >
              <div className="grid grid-cols-3 gap-2 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] p-1">
                {(
                  [
                    { mode: "product_page", label: "商品页分析" },
                    { mode: "product_discovery", label: "商品发现" },
                    { mode: "github_topic_radar", label: "Topic Radar" },
                  ] as const
                ).map((item) => (
                  <button
                    aria-pressed={mode === item.mode}
                    className={cn(
                      "h-9 rounded-lg px-2 text-xs font-semibold transition",
                      mode === item.mode
                        ? "bg-[#C96F5C] text-white shadow-[0_8px_18px_rgba(201,111,92,0.2)]"
                        : "text-[#7D4F43] hover:bg-[#FFF0EA]",
                    )}
                    key={item.mode}
                    onClick={() => {
                      setMode(item.mode);
                      setAnalysis(null);
                      setDiscovery(null);
                      setGithubRun(null);
                      if (item.mode === "github_topic_radar") {
                        const osintProject = projects.find((project) => project.domain === "osint");
                        if (osintProject) {
                          setSelectedProjectId(osintProject.id);
                        }
                        return;
                      }
                      setUrl(
                        item.mode === "product_discovery"
                          ? "https://shop.example/collections/summer-bags"
                          : "https://shop.example/products/demo-bag",
                      );
                    }}
                    type="button"
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {mode === "github_topic_radar" ? (
                <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
                  <span>GitHub topic</span>
                  <input
                    className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                    onChange={(event) => setGithubTopic(event.target.value)}
                    placeholder="web-scraping"
                    value={githubTopic}
                  />
                </label>
              ) : (
                <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
                  <span>{mode === "product_discovery" ? "集合页 / 列表页 URL" : "商品页 URL"}</span>
                  <input
                    className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                    onChange={(event) => setUrl(event.target.value)}
                    placeholder={
                      mode === "product_discovery"
                        ? "https://example.com/collections/category"
                        : "https://example.com/products/item"
                    }
                    value={url}
                  />
                </label>
              )}

              <label className="flex items-start gap-3 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] p-3 text-sm text-[#5F5757]">
                <input
                  checked={authorized}
                  className="mt-1 h-4 w-4 accent-[#C96F5C]"
                  onChange={(event) => setAuthorized(event.target.checked)}
                  type="checkbox"
                />
                <span>
                  我确认目标为公开可访问页面或公开 API，采集分析不涉及登录态、验证码绕过或未授权数据访问。
                </span>
              </label>

              {mode === "product_page" ? (
                <div className="grid gap-2">
                  <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
                    <span>归档项目</span>
                    <select
                      className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                      onChange={(event) => setSelectedProjectId(event.target.value)}
                      value={selectedProjectId}
                    >
                      {projects.map((project) => (
                        <option key={project.id} value={project.id}>
                          {project.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <span className="text-sm font-semibold text-[#3B2924]">字段目标</span>
                  <div className="flex flex-wrap gap-2">
                    {defaultFields.map((field) => (
                      <button
                        className={cn(
                          "inline-flex h-9 items-center rounded-full border px-3 text-xs font-semibold transition",
                          fields.includes(field)
                            ? "border-[#C96F5C] bg-[#C96F5C] text-white"
                            : "border-[#E8D4CB] bg-white text-[#7D4F43] hover:border-[#C96F5C]",
                        )}
                        key={field}
                        onClick={() => toggleField(field)}
                        type="button"
                      >
                        {fieldLabels[field]}
                      </button>
                    ))}
                  </div>
                </div>
              ) : mode === "product_discovery" ? (
                <div className="grid gap-3">
                  <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
                    <span>最多候选商品</span>
                    <input
                      className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                      max={200}
                      min={1}
                      onChange={(event) => setMaxProducts(event.target.value)}
                      type="number"
                      value={maxProducts}
                    />
                  </label>
                  <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
                    <span>写入项目</span>
                    <select
                      className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                      onChange={(event) => setSelectedProjectId(event.target.value)}
                      value={selectedProjectId}
                    >
                      {projects.map((project) => (
                        <option key={project.id} value={project.id}>
                          {project.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ) : (
                <div className="grid gap-3">
                  <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
                    <span>最多仓库</span>
                    <input
                      className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                      max={100}
                      min={1}
                      onChange={(event) => setGithubMaxResults(event.target.value)}
                      type="number"
                      value={githubMaxResults}
                    />
                  </label>
                  <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
                    <span>写入项目</span>
                    <select
                      className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                      onChange={(event) => setSelectedProjectId(event.target.value)}
                      value={selectedProjectId}
                    >
                      {projects.map((project) => (
                        <option key={project.id} value={project.id}>
                          {project.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}

              <button
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.24)] transition hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:bg-[#D8C8C0]"
                disabled={loading}
                type="submit"
              >
                {loading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Search size={16} aria-hidden="true" />}
                {loading
                  ? "处理中"
                  : mode === "github_topic_radar"
                    ? "创建并运行 Topic Radar"
                    : mode === "product_discovery"
                      ? "发现商品 URL"
                      : "开始分析"}
              </button>
            </form>
            {error ? (
              <p className="mt-4 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
                {error}
              </p>
            ) : null}
            {mode === "product_page" ? (
              <AnalysisHistoryPanel
                error={historyError}
                items={analysisHistory}
                loading={historyLoading}
              />
            ) : null}
          </div>
        </div>
      </section>

      <PlatformPackageMatrix
        appliedPackage={appliedPlatformPackage}
        error={platformPackageError}
        loading={platformPackageLoading}
        onApply={applyPlatformPackage}
        packages={platformPackages}
      />

      {mode === "github_topic_radar" ? (
        githubRun ? (
          <GitHubTopicRunResult result={githubRun} />
        ) : (
          <EmptyAnalysisState mode={mode} />
        )
      ) : mode === "product_discovery" ? (
        discovery ? (
          <DiscoveryResult
            key={discovery.analyzedAt}
            packageCleaningRules={appliedPlatformPackage?.cleaningRules ?? []}
            discovery={discovery}
            selectedProjectId={selectedProjectId}
            selectedFields={fields}
          />
        ) : (
          <EmptyAnalysisState mode={mode} />
        )
      ) : (
        analysis ? <AnalysisResult analysis={analysis} /> : <EmptyAnalysisState mode={mode} />
      )}
    </div>
  );
}

function AnalysisHistoryPanel({
  error,
  items,
  loading,
}: {
  error: string | null;
  items: AutomationSiteAnalysisHistoryItem[];
  loading: boolean;
}) {
  return (
    <div className="mt-4 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#2E201C]">历史分析</p>
          <p className="mt-1 text-xs leading-5 text-[#7A625A]">
            已保存的站点分析会在这里形成可复用采集计划。
          </p>
        </div>
        {loading ? <Loader2 className="animate-spin text-[#C96F5C]" size={16} aria-hidden="true" /> : null}
      </div>
      {error ? (
        <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-xs font-semibold text-[#B85F4F]">
          {error}
        </p>
      ) : null}
      {items.length > 0 ? (
        <div className="mt-3 grid gap-2">
          {items.map((item) => (
            <article className="rounded-xl border border-[#F0E1D9] bg-white p-3" key={item.id}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-[#2E201C]">
                    {item.latestPlan?.name ?? formatPageType(item.pageType)}
                  </p>
                  <p className="mt-1 truncate text-xs text-[#7A625A]">{item.requestedUrl}</p>
                </div>
                <span className="shrink-0 rounded-full border border-[#E8D4CB] px-2 py-1 text-xs font-semibold text-[#7D4F43]">
                  v{item.latestPlan?.versionNumber ?? 0}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold text-[#9E5C4D]">
                <span>{formatPlatform(item.platformType)}</span>
                <span>{formatRisk(item.riskLevel)}</span>
                <span>{formatShortDate(item.analyzedAt)}</span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-xl border border-dashed border-[#E8D4CB] px-3 py-3 text-xs leading-5 text-[#7A625A]">
          暂无历史分析。完成一次商品页分析后，系统会保存默认采集计划。
        </p>
      )}
    </div>
  );
}

function PlatformPackageMatrix({
  appliedPackage,
  error,
  loading,
  onApply,
  packages,
}: {
  appliedPackage: AutomationPlatformPackage | null;
  error: string | null;
  loading: boolean;
  onApply: (platformPackage: AutomationPlatformPackage) => void;
  packages: AutomationPlatformPackage[];
}) {
  return (
    <section className="rounded-2xl border border-[#EDDCD3] bg-white p-5 shadow-[0_12px_40px_rgba(115,70,58,0.06)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-[#FFF8F4] px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
            <ClipboardList size={14} aria-hidden="true" />
            Platform Packages
          </div>
          <h2 className="mt-3 text-xl font-semibold tracking-normal text-[#2E201C]">
            平台包矩阵
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#7A625A]">
            每个平台包绑定采集目标、字段 contract、工具策略、风险边界和 SOP 入口。
          </p>
        </div>
        {loading ? (
          <Loader2 className="animate-spin text-[#C96F5C]" size={18} aria-hidden="true" />
        ) : (
          <span className="rounded-full border border-[#E8D4CB] px-3 py-1 text-xs font-semibold text-[#7D4F43]">
            {packages.length} packages
          </span>
        )}
      </div>

      {appliedPackage ? (
        <div className="mt-4 grid gap-3 rounded-xl border border-[#D7E8D7] bg-[#F3FBF3] p-3 text-sm text-[#2F6B3A]">
          <p className="font-semibold">已应用平台包：{appliedPackage.name}</p>
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div>
              <p className="text-xs font-semibold uppercase text-[#4F7F56]">操作清单</p>
              <ul className="mt-2 grid gap-1 text-xs leading-5 text-[#4F7F56]">
                {appliedPackage.operatorChecklist.slice(0, 4).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-[#4F7F56]">默认清洗规则</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {appliedPackage.cleaningRules.slice(0, 6).map((rule) => (
                  <span
                    className="rounded-full border border-[#B9D9B8] bg-white px-2.5 py-1 text-xs font-semibold text-[#2F6B3A]"
                    key={`${rule.field}-${rule.operation}`}
                  >
                    {fieldLabels[rule.field] ?? rule.field}: {rule.operation}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : null}
      {error ? (
        <p className="mt-4 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-semibold text-[#B85F4F]">
          {error}
        </p>
      ) : null}

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        {packages.map((platformPackage) => {
          const executable = platformPackage.executionBoundary === "executable";
          return (
            <article
              className="grid min-w-0 gap-4 rounded-2xl border border-[#F0E1D9] bg-[#FFFDFC] p-4"
              key={platformPackage.id}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-words text-base font-semibold text-[#2E201C]">
                    {platformPackage.name}
                  </p>
                  <p className="mt-1 text-sm leading-6 text-[#7A625A]">
                    {platformPackage.summary}
                  </p>
                </div>
                <span
                  className={cn(
                    "shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold",
                    executable
                      ? "border-[#D7E8D7] bg-[#F3FBF3] text-[#2F6B3A]"
                      : "border-[#E8D4CB] bg-[#FFF8F4] text-[#7D4F43]",
                  )}
                >
                  {formatExecutionBoundary(platformPackage.executionBoundary)}
                </span>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase text-[#B47767]">Collectors</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {platformPackage.collectorTypes.map((collectorType) => (
                      <code
                        className="rounded-full bg-[#2E201C] px-2 py-1 text-xs font-semibold text-[#FFF8F4]"
                        key={collectorType}
                      >
                        {collectorType}
                      </code>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase text-[#B47767]">Targets</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {platformPackage.supportedTargets.map((target) => (
                      <span
                        className="rounded-full border border-[#E8D4CB] px-2 py-1 text-xs font-semibold text-[#7D4F43]"
                        key={target}
                      >
                        {target}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">Field Contract</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {platformPackage.fieldSchema.map((field) => (
                    <span
                      className="inline-flex h-8 items-center rounded-full border border-[#E8D4CB] bg-white px-3 text-xs font-semibold text-[#7D4F43]"
                      key={field.key}
                    >
                      {fieldLabels[field.key] ?? field.label}
                    </span>
                  ))}
                </div>
              </div>

              <div className="grid gap-2">
                {platformPackage.strategyMatrix.slice(0, 2).map((strategy) => (
                  <div className="rounded-xl border border-[#F0E1D9] bg-white p-3" key={strategy.id}>
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-[#2E201C]">{strategy.label}</p>
                      <span className="rounded-full bg-[#FFF0EA] px-2 py-1 text-xs font-semibold text-[#9E5C4D]">
                        {strategy.fit}
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-[#7A625A]">{strategy.description}</p>
                  </div>
                ))}
              </div>

              <div className="rounded-xl border border-[#F0E1D9] bg-white p-3">
                <p className="text-xs font-semibold uppercase text-[#B47767]">Risk Boundary</p>
                <p className="mt-2 text-sm leading-6 text-[#7A625A]">
                  {platformPackage.riskBoundaries[0]?.condition ?? "待补充边界"}：
                  {platformPackage.riskBoundaries[0]?.guidance ?? "需要人工确认。"}
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap gap-2">
                  {platformPackage.sopLinks.map((link) => (
                    <a
                      className="inline-flex h-9 items-center gap-2 rounded-full border border-[#E8D4CB] px-3 text-xs font-semibold text-[#7D4F43] hover:border-[#C96F5C]"
                      href={link.href}
                      key={link.href}
                    >
                      <ExternalLink size={13} aria-hidden="true" />
                      {link.label}
                    </a>
                  ))}
                </div>
                <button
                  className={cn(
                    "inline-flex h-9 items-center gap-2 rounded-full px-3 text-xs font-semibold transition",
                    executable
                      ? "bg-[#C96F5C] text-white hover:bg-[#B85F4F]"
                      : "cursor-not-allowed border border-[#E8D4CB] bg-[#FFF8F4] text-[#9E5C4D]",
                  )}
                  disabled={!executable}
                  onClick={() => onApply(platformPackage)}
                  type="button"
                >
                  <Link2 size={13} aria-hidden="true" />
                  {executable ? `应用${platformPackage.name}` : "SOP 审核后导入"}
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function GitHubTopicRunResult({ result }: { result: GitHubTopicRunState }) {
  const topicUrl = result.source.url ?? `https://github.com/topics/${result.topic}`;
  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Panel icon={Activity} label="GitHub Topic Radar" title="公开仓库情报采集结果">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Fact label="Topic" value={result.topic} />
          <Fact label="仓库上限" value={String(result.maxResults)} />
          <Fact label="采集状态" value={formatTaskRunStatus(result.run?.status ?? result.task.status)} />
          <Fact label="本次记录" value={String(result.run?.recordsCount ?? 0)} />
        </div>
        <div className="mt-4 rounded-xl border border-[#D7E8D7] bg-[#F3FBF3] p-3 text-sm text-[#2F6B3A]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="font-semibold">采集源与任务已创建</p>
              <p className="mt-1 text-xs leading-5 text-[#4F7F56]">
                系统已使用 GitHub 公开 API 创建 topic 采集源、启用任务，并完成一次手动运行。
              </p>
            </div>
            <a
              className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-full border border-[#B9D9B8] bg-white px-3 text-xs font-semibold text-[#2F6B3A] hover:border-[#4F7F56]"
              href={topicUrl}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink size={13} aria-hidden="true" />
              打开 topic
            </a>
          </div>
        </div>
      </Panel>

      <Panel icon={Database} label="Execution Trace" title="结构化保存状态">
        <div className="grid gap-3">
          <Fact label="采集源" value={result.source.name} />
          <Fact label="Collector" value={result.task.collectorType} />
          <Fact label="任务状态" value={formatTaskRunStatus(result.task.status)} />
          <Fact label="快照数量" value={String(result.run?.entitiesCount ?? 0)} />
          <p className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2 text-sm leading-6 text-[#7A625A]">
            后续可以在任务页查看运行历史，在数据集页继续做字段筛选、清洗计划和结构化保存。
          </p>
        </div>
      </Panel>
    </section>
  );
}

function AnalysisResult({ analysis }: { analysis: AutomationSiteAnalysis }) {
  return (
    <div className="grid min-w-0 gap-5">
      {analysis.blockedReasons.length > 0 ? (
        <section className="rounded-2xl border border-[#F0C8C0] bg-[#FFF2EF] p-4 text-sm text-[#B85F4F]">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle size={16} aria-hidden="true" />
            当前分析存在阻断项
          </div>
          <ul className="mt-2 grid gap-1">
            {analysis.blockedReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="grid min-w-0 gap-5">
          <Panel icon={Activity} label="Platform Profile" title="平台与页面结构">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Fact label="平台类型" value={formatPlatform(analysis.platformProfile.platformType)} />
              <Fact label="置信度" value={`${Math.round(analysis.platformProfile.confidence * 100)}%`} />
              <Fact label="风险级别" value={formatRisk(analysis.platformProfile.riskLevel)} />
              <Fact label="页面类型" value={formatPageType(analysis.pageStructure.pageType)} />
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Fact label="Product schema" value={String(analysis.pageStructure.productSchemaCount)} />
              <Fact label="脚本数" value={String(analysis.pageStructure.scriptCount)} />
              <Fact label="表单数" value={String(analysis.pageStructure.formCount)} />
              <Fact label="同源链接" value={String(analysis.pageStructure.sameOriginLinkCount)} />
            </div>
            <div className="mt-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
              <p className="text-xs font-semibold uppercase text-[#B47767]">识别依据</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {analysis.platformProfile.indicators.map((indicator) => (
                  <span
                    className="rounded-full border border-[#E8D4CB] bg-[#FFF8F4] px-2.5 py-1 text-xs font-semibold text-[#7D4F43]"
                    key={indicator}
                  >
                    {indicator}
                  </span>
                ))}
              </div>
            </div>
          </Panel>

          <Panel icon={ClipboardList} label="Field Schema" title="字段候选与保存质量">
            <div className="grid gap-3 md:grid-cols-2">
              {analysis.fieldCandidates.map((field) => (
                <FieldCandidateCard field={field} key={field.key} />
              ))}
            </div>
          </Panel>
        </div>

        <aside className="grid min-w-0 gap-5">
          <Panel icon={Search} label="Tool Router" title="采集工具推荐">
            <div className="grid gap-3">
              {analysis.toolRecommendations.map((recommendation) => (
                <div
                  className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3"
                  key={`${recommendation.tool}-${recommendation.fit}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="break-words text-sm font-semibold text-[#2E201C]">{recommendation.tool}</p>
                      <p className="mt-1 text-xs font-semibold uppercase text-[#B47767]">
                        {recommendation.fit} · {recommendation.collectorType}
                      </p>
                    </div>
                    <RiskBadge risk={recommendation.riskLevel} />
                  </div>
                  <p className="mt-2 text-sm leading-5 text-[#7A625A]">{recommendation.reason}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel icon={Code2} label="Cleaning Plan" title="清洗规则草稿">
            <div className="grid gap-2">
              {analysis.cleaningPlan.map((step) => (
                <div className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3" key={`${step.field}-${step.operation}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-[#2E201C]">{fieldLabels[step.field] ?? step.field}</p>
                    <code className="rounded-full bg-[#2E201C] px-2 py-1 text-xs font-semibold text-[#FFF8F4]">
                      {step.operation}
                    </code>
                  </div>
                  <p className="mt-2 text-sm leading-5 text-[#7A625A]">{step.description}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel icon={Database} label="采集源草稿" title="可入库数据源草稿">
            <div className="grid gap-3">
              {analysis.extractionPlan ? (
                <div className="rounded-xl border border-[#D7E8D7] bg-[#F3FBF3] p-3">
                  <p className="text-sm font-semibold text-[#2F6B3A]">
                    采集计划已保存：v{analysis.extractionPlan.versionNumber}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-[#4F7F56]">
                    {analysis.extractionPlan.name}；字段 {analysis.extractionPlan.selectedFields.join(", ")}。
                  </p>
                </div>
              ) : null}
              <Fact label="建议名称" value={analysis.sourceDraft.suggestedName} />
              <Fact label="Collector" value={analysis.sourceDraft.type} />
              <Fact label="调度" value={analysis.sourceDraft.scheduleCron ?? "手动确认后启用"} />
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-xl bg-[#2E201C] p-3 text-xs leading-5 text-[#FFF8F4]">
                {JSON.stringify(analysis.sourceDraft.config, null, 2)}
              </pre>
            </div>
          </Panel>
        </aside>
      </section>
    </div>
  );
}

function DiscoveryResult({
  discovery,
  packageCleaningRules,
  selectedProjectId,
  selectedFields,
}: {
  discovery: AutomationProductDiscovery;
  packageCleaningRules: AutomationCleaningRule[];
  selectedProjectId: string;
  selectedFields: string[];
}) {
  const [selectedUrls, setSelectedUrls] = useState<string[]>(
    discovery.productCandidates.slice(0, 5).map((candidate) => candidate.url),
  );
  const [fanoutPreview, setFanoutPreview] = useState<AutomationProductFanoutPreview | null>(null);
  const [fanoutCreate, setFanoutCreate] = useState<AutomationProductFanoutCreate | null>(null);
  const [fanoutError, setFanoutError] = useState<string | null>(null);
  const [fanoutCreateError, setFanoutCreateError] = useState<string | null>(null);
  const [fanoutLoading, setFanoutLoading] = useState(false);
  const [fanoutCreateLoading, setFanoutCreateLoading] = useState(false);
  const [batchRun, setBatchRun] = useState<AutomationProductBatchRun | null>(null);
  const [batchRunError, setBatchRunError] = useState<string | null>(null);
  const [batchRunLoading, setBatchRunLoading] = useState(false);
  const selectedCandidates = discovery.productCandidates.filter((candidate) =>
    selectedUrls.includes(candidate.url),
  );
  const effectiveFields = selectedFields.length > 0 ? selectedFields : defaultFields;

  function toggleCandidate(url: string) {
    setSelectedUrls((current) =>
      current.includes(url) ? current.filter((item) => item !== url) : [...current, url],
    );
    setFanoutPreview(null);
    setFanoutCreate(null);
    setFanoutError(null);
    setFanoutCreateError(null);
    setBatchRun(null);
    setBatchRunError(null);
  }

  async function previewFanout() {
    setFanoutError(null);
    if (selectedCandidates.length === 0) {
      setFanoutError("请至少选择一个候选商品 URL。");
      return;
    }
    setFanoutLoading(true);
    try {
      const preview = await previewAutomationProductFanout({
        parentUrl: discovery.requestedUrl,
        authorized: discovery.authorizationConfirmed,
        candidates: selectedCandidates.map((candidate) => ({
          url: candidate.url,
          title: candidate.title,
          source: candidate.source,
          confidence: candidate.confidence,
        })),
        fields: effectiveFields,
        maxSources: 20,
      });
      setFanoutPreview(preview);
      setFanoutCreate(null);
      setBatchRun(null);
      setBatchRunError(null);
    } catch (caught) {
      setFanoutError(caught instanceof Error ? caught.message : "Fan-out preview failed");
    } finally {
      setFanoutLoading(false);
    }
  }

  async function confirmFanoutCreate() {
    setFanoutCreateError(null);
    if (!fanoutPreview) {
      setFanoutCreateError("请先生成采集源预览。");
      return;
    }
    if (!selectedProjectId) {
      setFanoutCreateError("请选择写入项目后再创建。");
      return;
    }
    setFanoutCreateLoading(true);
    setBatchRun(null);
    setBatchRunError(null);
    try {
      const result = await createAutomationProductFanout({
        parentUrl: discovery.requestedUrl,
        projectId: selectedProjectId,
        authorized: discovery.authorizationConfirmed,
        candidates: selectedCandidates.map((candidate) => ({
          url: candidate.url,
          title: candidate.title,
          source: candidate.source,
          confidence: candidate.confidence,
        })),
        fields: fanoutPreview.batchPlan.fields,
        maxSources: fanoutPreview.batchPlan.maxSources,
        enableTasks: true,
      });
      setFanoutCreate(result);
    } catch (caught) {
      setFanoutCreateError(caught instanceof Error ? caught.message : "Fan-out create failed");
    } finally {
      setFanoutCreateLoading(false);
    }
  }

  async function runBatchQualityCheck() {
    setBatchRunError(null);
    if (!fanoutCreate) {
      setBatchRunError("请先确认创建采集源和任务。");
      return;
    }
    const taskIds = fanoutCreate.persistedSources
      .map((item) => item.task?.id)
      .filter((taskId): taskId is string => Boolean(taskId));
    if (taskIds.length === 0) {
      setBatchRunError("当前没有可运行的已启用任务。");
      return;
    }
    setBatchRunLoading(true);
    try {
      const result = await runAutomationProductBatch({
        authorized: discovery.authorizationConfirmed,
        taskIds,
        maxTasks: Math.min(taskIds.length, 20),
      });
      setBatchRun(result);
    } catch (caught) {
      setBatchRunError(caught instanceof Error ? caught.message : "Batch run failed");
    } finally {
      setBatchRunLoading(false);
    }
  }

  return (
    <div className="grid min-w-0 gap-5">
      {discovery.blockedReasons.length > 0 ? (
        <section className="rounded-2xl border border-[#F0C8C0] bg-[#FFF2EF] p-4 text-sm text-[#B85F4F]">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle size={16} aria-hidden="true" />
            当前发现存在阻断项
          </div>
          <ul className="mt-2 grid gap-1">
            {discovery.blockedReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="grid min-w-0 gap-5">
          <Panel icon={Activity} label="Discovery Profile" title="集合页结构与发现质量">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Fact label="平台类型" value={formatPlatform(discovery.platformProfile.platformType)} />
              <Fact label="置信度" value={`${Math.round(discovery.platformProfile.confidence * 100)}%`} />
              <Fact label="页面类型" value={formatPageType(discovery.pageStructure.pageType)} />
              <Fact label="候选 URL" value={String(discovery.productCandidates.length)} />
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Fact label="总链接" value={String(discovery.pageStructure.linkCount)} />
              <Fact label="商品链接" value={String(discovery.pageStructure.productLinkCount)} />
              <Fact label="JSON-LD URL" value={String(discovery.pageStructure.jsonldUrlCount)} />
              <Fact label="脚本数" value={String(discovery.pageStructure.scriptCount)} />
            </div>
            <div className="mt-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
              <p className="text-xs font-semibold uppercase text-[#B47767]">页面文本样本</p>
              <p className="mt-2 text-sm leading-6 text-[#7A625A]">
                {discovery.pageStructure.textSample || "未提取到稳定文本样本"}
              </p>
            </div>
          </Panel>

          <Panel icon={Link2} label="Product Candidates" title="候选商品 URL">
            <div className="mb-3 flex flex-col gap-2 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-[#2E201C]">
                  已选择 {selectedCandidates.length} / {discovery.productCandidates.length}
                </p>
                <p className="mt-1 text-xs leading-5 text-[#7A625A]">
                  预览只生成商品页采集源草稿，不创建真实采集源或任务。
                </p>
              </div>
              <button
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white transition hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:bg-[#D8C8C0]"
                disabled={fanoutLoading || selectedCandidates.length === 0}
                onClick={() => void previewFanout()}
                type="button"
              >
                {fanoutLoading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <ClipboardList size={16} aria-hidden="true" />}
                生成采集源预览
              </button>
            </div>
            {fanoutError ? (
              <p className="mb-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
                {fanoutError}
              </p>
            ) : null}
            <div className="grid gap-3">
              {discovery.productCandidates.map((candidate) => (
                <article
                  className="min-w-0 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3"
                  key={candidate.url}
                >
                  <div className="flex items-start justify-between gap-3">
                    <label className="flex min-w-0 flex-1 items-start gap-3">
                      <input
                        checked={selectedUrls.includes(candidate.url)}
                        className="mt-1 h-4 w-4 shrink-0 accent-[#C96F5C]"
                        onChange={() => toggleCandidate(candidate.url)}
                        type="checkbox"
                      />
                      <span className="min-w-0">
                        <span className="block break-words text-sm font-semibold text-[#2E201C]">
                          {candidate.title ?? "未识别标题"}
                        </span>
                        <span className="mt-1 block break-all text-xs leading-5 text-[#7A625A]">
                          {candidate.url}
                        </span>
                      </span>
                    </label>
                    <a
                      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#E8D4CB] text-[#9E5C4D] hover:border-[#C96F5C] hover:text-[#B85F4F]"
                      href={candidate.url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <ExternalLink size={15} aria-hidden="true" />
                      <span className="sr-only">打开候选商品</span>
                    </a>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-semibold text-[#7A625A]">
                    <span>{candidate.source}</span>
                    <span>{Math.round(candidate.confidence * 100)}%</span>
                    <span>{selectedUrls.includes(candidate.url) ? "已选择" : "未选择"}</span>
                  </div>
                </article>
              ))}
            </div>
          </Panel>
          {fanoutPreview ? (
            <FanoutPreviewPanel
              createError={fanoutCreateError}
              createLoading={fanoutCreateLoading}
              batchRun={batchRun}
              batchRunError={batchRunError}
              batchRunLoading={batchRunLoading}
              onConfirmCreate={() => void confirmFanoutCreate()}
              onRunBatch={() => void runBatchQualityCheck()}
              packageCleaningRules={packageCleaningRules}
              preview={fanoutPreview}
              result={fanoutCreate}
              selectedFields={effectiveFields}
            />
          ) : null}
        </div>

        <aside className="grid min-w-0 gap-5">
          <Panel icon={Search} label="Tool Router" title="采集工具推荐">
            <div className="grid gap-3">
              {discovery.toolRecommendations.map((recommendation) => (
                <div
                  className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3"
                  key={`${recommendation.tool}-${recommendation.fit}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="break-words text-sm font-semibold text-[#2E201C]">{recommendation.tool}</p>
                      <p className="mt-1 text-xs font-semibold uppercase text-[#B47767]">
                        {recommendation.fit} · {recommendation.collectorType}
                      </p>
                    </div>
                    <RiskBadge risk={recommendation.riskLevel} />
                  </div>
                  <p className="mt-2 text-sm leading-5 text-[#7A625A]">{recommendation.reason}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel icon={ClipboardList} label="Discovery Plan" title="下一步执行计划">
            <div className="grid gap-3">
              <Fact label="下一步 Collector" value={discovery.discoveryPlan.nextCollectorType} />
              <Fact label="候选数量" value={String(discovery.discoveryPlan.candidateCount)} />
              <Fact label="候选上限" value={String(discovery.discoveryPlan.maxProducts)} />
              <Fact
                label="批量展开"
                value={discovery.discoveryPlan.fanOutRequiresReview ? "需人工确认" : "可自动展开"}
              />
            </div>
          </Panel>

          <Panel icon={Database} label="采集源草稿" title="可入库数据源草稿">
            <div className="grid gap-3">
              <Fact label="建议名称" value={discovery.sourceDraft.suggestedName} />
              <Fact label="Collector" value={discovery.sourceDraft.type} />
              <Fact label="调度" value={discovery.sourceDraft.scheduleCron ?? "手动确认后启用"} />
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-xl bg-[#2E201C] p-3 text-xs leading-5 text-[#FFF8F4]">
                {JSON.stringify(discovery.sourceDraft.config, null, 2)}
              </pre>
            </div>
          </Panel>
        </aside>
      </section>
    </div>
  );
}

function FanoutPreviewPanel({
  preview,
  result,
  createLoading,
  createError,
  batchRun,
  batchRunLoading,
  batchRunError,
  onConfirmCreate,
  onRunBatch,
  packageCleaningRules,
  selectedFields,
}: {
  preview: AutomationProductFanoutPreview;
  result: AutomationProductFanoutCreate | null;
  createLoading: boolean;
  createError: string | null;
  batchRun: AutomationProductBatchRun | null;
  batchRunLoading: boolean;
  batchRunError: string | null;
  onConfirmCreate: () => void;
  onRunBatch: () => void;
  packageCleaningRules: AutomationCleaningRule[];
  selectedFields: string[];
}) {
  return (
    <Panel icon={ClipboardList} label="Fan-out Preview" title="子商品页采集源预览">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Fact label="运行模式" value={formatFanoutRunMode(preview.batchPlan.runMode)} />
        <Fact label="可创建草稿" value={String(preview.batchPlan.readyCount)} />
        <Fact label="阻断候选" value={String(preview.batchPlan.blockedCount)} />
        <Fact
          label="人工确认"
          value={preview.batchPlan.manualReviewRequired ? "必须确认" : "无需确认"}
        />
      </div>
      <div className="mt-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
        <p className="text-xs font-semibold uppercase text-[#B47767]">执行边界</p>
        <p className="mt-2 text-sm leading-6 text-[#7A625A]">
          {formatFanoutExecutionBoundary(preview.batchPlan.executionBoundary)}
        </p>
      </div>
      <div className="mt-4 flex flex-col gap-2 rounded-xl border border-[#E8D4CB] bg-[#FFF8F4] p-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-[#2E201C]">确认创建商品页采集源</p>
          <p className="mt-1 text-xs leading-5 text-[#7A625A]">
            该操作会创建或复用采集源，并启用对应任务，但不会启动采集运行。
          </p>
        </div>
        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white transition hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:bg-[#D8C8C0]"
          disabled={createLoading || preview.sourceDrafts.length === 0}
          onClick={onConfirmCreate}
          type="button"
        >
          {createLoading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
          确认创建采集源和任务
        </button>
      </div>
      {createError ? (
        <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
          {createError}
        </p>
      ) : null}
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="grid gap-2">
          <p className="text-sm font-semibold text-[#2E201C]">候选状态</p>
          {preview.candidateStatuses.map((candidate) => (
            <div
              className={cn(
                "rounded-xl border px-3 py-2 text-sm",
                candidate.status === "ready"
                  ? "border-[#CDE6C4] bg-[#F7FBF1]"
                  : "border-[#F0C8C0] bg-[#FFF2EF]",
              )}
              key={candidate.url}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-[#2E201C]">
                  {candidate.title ?? "未识别标题"}
                </span>
                <span
                  className={cn(
                    "rounded-full px-2 py-1 text-xs font-semibold",
                    candidate.status === "ready"
                      ? "bg-[#ECF7EA] text-[#4E7C45]"
                      : "bg-[#F6ECE8] text-[#9E5C4D]",
                  )}
                >
                  {candidate.status === "ready" ? "就绪" : "阻断"}
                </span>
              </div>
              <p className="mt-1 break-all text-xs leading-5 text-[#7A625A]">{candidate.url}</p>
              {candidate.reason ? (
                <p className="mt-1 text-xs font-semibold text-[#B85F4F]">{candidate.reason}</p>
              ) : null}
            </div>
          ))}
        </div>
        <div className="grid gap-2">
          <p className="text-sm font-semibold text-[#2E201C]">采集源草稿</p>
          {preview.sourceDrafts.map((draft) => (
            <div
              className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3"
              key={`${draft.type}-${String(draft.config.url)}`}
            >
              <p className="text-sm font-semibold text-[#2E201C]">{draft.suggestedName}</p>
              <p className="mt-1 text-xs font-semibold uppercase text-[#B47767]">{draft.type}</p>
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-xl bg-[#2E201C] p-3 text-xs leading-5 text-[#FFF8F4]">
                {JSON.stringify(draft.config, null, 2)}
              </pre>
            </div>
          ))}
          {preview.sourceDrafts.length === 0 ? (
            <p className="rounded-xl border border-dashed border-[#DDBEAF] bg-[#FFF8F4] p-4 text-sm text-[#7A625A]">
              当前没有可进入下一步的商品页采集源草稿。
            </p>
          ) : null}
        </div>
      </div>
      {preview.blockedReasons.length > 0 ? (
        <div className="mt-4 grid gap-2">
          {preview.blockedReasons.map((reason) => (
            <p
              className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2 text-xs font-semibold text-[#7A625A]"
              key={reason}
            >
              {reason}
            </p>
          ))}
        </div>
      ) : null}
      {result ? (
        <FanoutCreateResult
          batchRun={batchRun}
          batchRunError={batchRunError}
          batchRunLoading={batchRunLoading}
          onRunBatch={onRunBatch}
          packageCleaningRules={packageCleaningRules}
          result={result}
          selectedFields={selectedFields}
        />
      ) : null}
    </Panel>
  );
}

function FanoutCreateResult({
  result,
  batchRun,
  batchRunLoading,
  batchRunError,
  onRunBatch,
  packageCleaningRules,
  selectedFields,
}: {
  result: AutomationProductFanoutCreate;
  batchRun: AutomationProductBatchRun | null;
  batchRunLoading: boolean;
  batchRunError: string | null;
  onRunBatch: () => void;
  packageCleaningRules: AutomationCleaningRule[];
  selectedFields: string[];
}) {
  const runnableTasks = result.persistedSources.filter((item) => item.task).length;
  return (
    <div className="mt-5 rounded-2xl border border-[#CDE6C4] bg-[#F7FBF1] p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-[#4E7C45]">Persisted Result</p>
          <h3 className="mt-1 text-base font-semibold text-[#2E201C]">已创建或复用采集源</h3>
          <p className="mt-1 text-sm leading-6 text-[#5F5757]">
            已启用对应任务，下一步可以手动运行小批量采集并评估字段完整度。
          </p>
        </div>
        <RiskBadge risk={result.summary.runStarted ? "medium" : "low"} />
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Fact label="新建采集源" value={String(result.summary.createdSources)} />
        <Fact label="复用采集源" value={String(result.summary.reusedSources)} />
        <Fact label="启用任务" value={String(result.summary.enabledTasks)} />
        <Fact label="阻断候选" value={String(result.summary.blockedCandidates)} />
        <Fact label="启动运行" value={result.summary.runStarted ? "是" : "否"} />
      </div>
      <div className="mt-4 grid gap-3">
        {result.persistedSources.map((item) => (
          <div
            className="rounded-xl border border-[#D9E2CC] bg-white/80 p-3"
            key={`${item.action}-${item.source.id}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="break-words text-sm font-semibold text-[#2E201C]">
                  {item.source.name}
                </p>
                <p className="mt-1 break-all text-xs text-[#7A625A]">{item.url}</p>
              </div>
              <span className="rounded-full bg-[#ECF7EA] px-2.5 py-1 text-xs font-semibold text-[#4E7C45]">
                {item.action}
              </span>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              <Fact label="采集源 ID" value={item.source.id} />
              <Fact label="任务 ID" value={item.task?.id ?? "未启用"} />
              <Fact label="任务状态" value={item.task?.status ?? "无"} />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-2">
        {result.blockedReasons.map((reason) => (
          <p
            className="rounded-xl border border-[#D9E2CC] bg-white/80 px-3 py-2 text-xs font-semibold text-[#536B40]"
            key={reason}
          >
            {reason}
          </p>
        ))}
      </div>
      <div className="mt-4 flex flex-col gap-2 rounded-xl border border-[#D9E2CC] bg-white/80 p-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-[#2E201C]">运行小批量采集并评估质量</p>
          <p className="mt-1 text-xs leading-5 text-[#5F5757]">
            将运行 {runnableTasks} 个已启用商品页任务，并只统计本次运行产出的字段。
          </p>
        </div>
        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#4E7C45] px-3 text-sm font-semibold text-white transition hover:bg-[#416B39] disabled:cursor-not-allowed disabled:bg-[#B8C9B0]"
          disabled={batchRunLoading || runnableTasks === 0}
          onClick={onRunBatch}
          type="button"
        >
          {batchRunLoading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Activity size={16} aria-hidden="true" />}
          小批量运行
        </button>
      </div>
      {batchRunError ? (
        <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
          {batchRunError}
        </p>
      ) : null}
      {batchRun ? (
        <BatchRunResult
          packageCleaningRules={packageCleaningRules}
          result={batchRun}
          selectedFields={selectedFields}
        />
      ) : null}
    </div>
  );
}

function BatchRunResult({
  packageCleaningRules,
  result,
  selectedFields,
}: {
  packageCleaningRules: AutomationCleaningRule[];
  result: AutomationProductBatchRun;
  selectedFields: string[];
}) {
  const [datasetFields, setDatasetFields] = useState<string[]>(
    selectedFields.length > 0 ? selectedFields : ["title", "price", "sku", "canonical_url"],
  );
  const [datasetPreview, setDatasetPreview] = useState<AutomationProductDatasetPreview | null>(null);
  const [datasetError, setDatasetError] = useState<string | null>(null);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const runIds = result.items
    .map((item) => item.run?.id)
    .filter((runId): runId is string => Boolean(runId));
  const successfulTaskIds = result.items
    .filter((item) => item.status === "run_completed")
    .map((item) => item.taskId);

  function toggleDatasetField(field: string) {
    setDatasetFields((current) => {
      if (current.includes(field)) {
        return current.filter((item) => item !== field);
      }
      return [...current, field];
    });
    setDatasetPreview(null);
    setDatasetError(null);
  }

  async function generateDatasetPreview() {
    setDatasetError(null);
    if (runIds.length === 0) {
      setDatasetError("当前没有可进入数据集预览的成功运行。");
      return;
    }
    if (datasetFields.length === 0) {
      setDatasetError("请至少选择一个数据集字段。");
      return;
    }
    setDatasetLoading(true);
    try {
      const preview = await previewAutomationProductDataset({
        authorized: result.authorizationConfirmed,
        taskRunIds: runIds,
        fields: datasetFields,
        maxRows: 100,
      });
      setDatasetPreview(preview);
    } catch (caught) {
      setDatasetError(caught instanceof Error ? caught.message : "数据集预览生成失败");
    } finally {
      setDatasetLoading(false);
    }
  }

  return (
    <div className="mt-4 rounded-2xl border border-[#D9E2CC] bg-white/85 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-[#4E7C45]">Batch Quality</p>
          <h3 className="mt-1 text-base font-semibold text-[#2E201C]">字段完整度验收</h3>
        </div>
        <span className="rounded-full bg-[#ECF7EA] px-3 py-1 text-xs font-semibold text-[#4E7C45]">
          平均 {result.summary.averageCompletenessPercent}%
        </span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Fact label="已运行任务" value={String(result.summary.runTasks)} />
        <Fact label="阻断任务" value={String(result.summary.blockedTasks)} />
        <Fact label="成功运行" value={String(result.summary.successfulRuns)} />
        <Fact label="记录" value={String(result.summary.recordsCount)} />
        <Fact label="快照" value={String(result.summary.entitiesCount)} />
      </div>
      <div className="mt-4 grid gap-3">
        {result.items.map((item) => (
          <div
            className={cn(
              "rounded-xl border p-3",
              item.status === "blocked"
                ? "border-[#F0C8C0] bg-[#FFF2EF]"
                : "border-[#E0E8D5] bg-[#FAFCF7]",
            )}
            key={`${item.taskId}-${item.status}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="break-words text-sm font-semibold text-[#2E201C]">
                  {item.taskName ?? item.taskId}
                </p>
                <p className="mt-1 break-all text-xs text-[#7A625A]">
                  {item.sourceUrl ?? item.taskId}
                </p>
              </div>
              <span
                className={cn(
                  "rounded-full px-2.5 py-1 text-xs font-semibold",
                  item.status === "blocked"
                    ? "bg-[#F6ECE8] text-[#9E5C4D]"
                    : "bg-[#ECF7EA] text-[#4E7C45]",
                )}
              >
                {item.status === "blocked" ? item.blockedReason : item.run?.status}
              </span>
            </div>
            {item.fieldCompleteness ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-[120px_minmax(0,1fr)]">
                <div>
                  <p className="text-2xl font-semibold text-[#2E201C]">
                    {item.fieldCompleteness.completenessPercent}%
                  </p>
                  <p className="text-xs font-semibold text-[#7A625A]">完整度</p>
                </div>
                <div className="grid gap-2">
                  <p className="text-xs font-semibold text-[#536B40]">
                    已提取：{item.fieldCompleteness.extractedFields.join(" / ") || "无"}
                  </p>
                  <p className="text-xs font-semibold text-[#9E5C4D]">
                    缺失：{item.fieldCompleteness.missingFields.join(" / ") || "无"}
                  </p>
                </div>
              </div>
            ) : null}
          </div>
        ))}
      </div>
      {result.blockedReasons.length > 0 ? (
        <div className="mt-4 grid gap-2">
          {result.blockedReasons.map((reason) => (
            <p
              className="rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 py-2 text-xs font-semibold text-[#536B40]"
              key={reason}
            >
              {reason}
            </p>
          ))}
        </div>
      ) : null}
      <div className="mt-4 rounded-2xl border border-[#D9E2CC] bg-[#FAFCF7] p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase text-[#4E7C45]">数据集预览</p>
            <h3 className="mt-1 text-base font-semibold text-[#2E201C]">采集结果数据集预览</h3>
            <p className="mt-1 text-sm leading-6 text-[#5F5757]">
              从本次成功运行中生成只读表格和 JSON 导出草稿，不写入正式数据集。
            </p>
          </div>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#2E201C] px-3 text-sm font-semibold text-white transition hover:bg-[#46332C] disabled:cursor-not-allowed disabled:bg-[#B8C9B0]"
            disabled={datasetLoading || runIds.length === 0 || datasetFields.length === 0}
            onClick={() => void generateDatasetPreview()}
            type="button"
          >
            {datasetLoading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Database size={16} aria-hidden="true" />}
            生成数据集预览
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {defaultFields.map((field) => (
            <button
              className={cn(
                "inline-flex h-8 items-center rounded-full border px-3 text-xs font-semibold transition",
                datasetFields.includes(field)
                  ? "border-[#4E7C45] bg-[#4E7C45] text-white"
                  : "border-[#D9E2CC] bg-white text-[#536B40] hover:border-[#4E7C45]",
              )}
              key={field}
              onClick={() => toggleDatasetField(field)}
              type="button"
            >
              {fieldLabels[field]}
            </button>
          ))}
        </div>
        {datasetError ? (
          <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
            {datasetError}
          </p>
        ) : null}
        {datasetPreview ? (
          <DatasetPreviewResult
            packageCleaningRules={packageCleaningRules}
            result={datasetPreview}
            taskIds={successfulTaskIds}
          />
        ) : null}
      </div>
    </div>
  );
}

function DatasetPreviewResult({
  packageCleaningRules,
  result,
  taskIds,
}: {
  packageCleaningRules: AutomationCleaningRule[];
  result: AutomationProductDatasetPreview;
  taskIds: string[];
}) {
  const defaultDatasetName = `商品数据集 ${result.createdAt.slice(0, 10) || "草稿"}`;
  const [datasetName, setDatasetName] = useState(defaultDatasetName);
  const [saveResult, setSaveResult] = useState<AutomationProductDatasetSave | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [cleaningDryRun, setCleaningDryRun] = useState<AutomationCleaningPlanDryRun | null>(null);
  const [cleaningPlan, setCleaningPlan] = useState<AutomationCleaningPlanCreate | null>(null);
  const [cleaningLoading, setCleaningLoading] = useState(false);
  const [cleaningSaving, setCleaningSaving] = useState(false);
  const [cleaningError, setCleaningError] = useState<string | null>(null);
  const [useCleaningPlan, setUseCleaningPlan] = useState(true);
  const [schedulePolicy, setSchedulePolicy] = useState<"auto_freshness" | "manual_refresh_only">("auto_freshness");
  const [scheduleCron, setScheduleCron] = useState("");
  const [freshnessTargetHours, setFreshnessTargetHours] = useState("6");
  const [minimumCompletenessPercent, setMinimumCompletenessPercent] = useState("70");
  const [scheduleResult, setScheduleResult] = useState<AutomationProductScheduleApprove | null>(null);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [driftThresholdPercent, setDriftThresholdPercent] = useState("10");
  const [freshnessGraceHours, setFreshnessGraceHours] = useState("0");
  const [driftResult, setDriftResult] = useState<AutomationProductDriftCheck | null>(null);
  const [driftError, setDriftError] = useState<string | null>(null);
  const [driftLoading, setDriftLoading] = useState(false);
  const [driftEvents, setDriftEvents] = useState<AutomationProductDriftEvent[]>([]);
  const [driftHistoryLoading, setDriftHistoryLoading] = useState(false);
  const [driftEventSaving, setDriftEventSaving] = useState(false);
  const [driftEventMessage, setDriftEventMessage] = useState<string | null>(null);
  const taskRunIds = useMemo(
    () =>
      Array.from(new Set(result.rows.map((row) => row.taskRunId))).filter(
        (taskRunId): taskRunId is string => Boolean(taskRunId),
      ),
    [result.rows],
  );
  const cleaningRules = useMemo(() => {
    const packageRules = packageCleaningRules.filter((rule) =>
      result.summary.selectedFields.includes(rule.field),
    );
    return packageRules.length > 0
      ? packageRules
      : defaultCleaningRulesForFields(result.summary.selectedFields);
  }, [packageCleaningRules, result.summary.selectedFields]);

  useEffect(() => {
    setDatasetName(defaultDatasetName);
    setSaveResult(null);
    setSaveError(null);
    setCleaningDryRun(null);
    setCleaningPlan(null);
    setCleaningError(null);
    setUseCleaningPlan(true);
    setScheduleResult(null);
    setScheduleError(null);
    setDriftResult(null);
    setDriftError(null);
    setDriftEvents([]);
    setDriftEventMessage(null);
  }, [defaultDatasetName]);

  async function runCleaningDryRun() {
    setCleaningError(null);
    if (taskRunIds.length === 0) {
      setCleaningError("当前预览没有可试跑的数据来源运行记录。");
      return;
    }
    if (cleaningRules.length === 0) {
      setCleaningError("当前字段没有可用的默认清洗规则。");
      return;
    }
    setCleaningLoading(true);
    try {
      const dryRun = await dryRunAutomationCleaningPlan({
        authorized: result.authorizationConfirmed,
        taskRunIds,
        fields: result.summary.selectedFields,
        rules: cleaningRules,
        maxRows: Math.max(result.rows.length, 1),
      });
      setCleaningDryRun(dryRun);
      setCleaningPlan(null);
      setSaveResult(null);
    } catch (caught) {
      setCleaningError(caught instanceof Error ? caught.message : "清洗规则试跑失败");
    } finally {
      setCleaningLoading(false);
    }
  }

  async function saveCleaningPlan() {
    setCleaningError(null);
    if (taskRunIds.length === 0) {
      setCleaningError("当前预览没有可保存清洗计划的数据来源运行记录。");
      return;
    }
    if (cleaningRules.length === 0) {
      setCleaningError("当前字段没有可保存的默认清洗规则。");
      return;
    }
    setCleaningSaving(true);
    try {
      const created = await createAutomationCleaningPlan({
        authorized: result.authorizationConfirmed,
        name: `${datasetName.trim() || defaultDatasetName} 清洗计划`,
        taskRunIds,
        fields: result.summary.selectedFields,
        rules: cleaningRules,
        maxRows: Math.max(result.rows.length, 1),
      });
      setCleaningPlan(created);
      setCleaningDryRun(created.dryRun);
      setUseCleaningPlan(true);
      setSaveResult(null);
    } catch (caught) {
      setCleaningError(caught instanceof Error ? caught.message : "清洗计划保存失败");
    } finally {
      setCleaningSaving(false);
    }
  }

  async function loadDriftHistory(saved: AutomationProductDatasetSave) {
    setDriftHistoryLoading(true);
    try {
      const history = await listAutomationProductDriftEvents({
        datasetId: saved.dataset.id,
        datasetVersionId: saved.version.id,
        limit: 5,
      });
      setDriftEvents(history.items);
    } catch (caught) {
      setDriftEventMessage(caught instanceof Error ? caught.message : "漂移历史加载失败");
    } finally {
      setDriftHistoryLoading(false);
    }
  }

  async function saveDatasetVersion() {
    setSaveError(null);
    if (!datasetName.trim()) {
      setSaveError("请填写数据集名称。");
      return;
    }
    if (taskRunIds.length === 0) {
      setSaveError("当前预览没有可保存的数据来源运行记录。");
      return;
    }
    setSaveLoading(true);
    try {
      const saved = await saveAutomationProductDataset({
        authorized: result.authorizationConfirmed,
        name: datasetName.trim(),
        description: `来自 ${taskRunIds.length} 个小批量采集运行记录的商品数据集。`,
        taskRunIds,
        fields: result.summary.selectedFields,
        maxRows: Math.max(result.rows.length, 1),
        cleaningPlanId:
          useCleaningPlan && cleaningPlan ? cleaningPlan.cleaningPlan.id : undefined,
      });
      setSaveResult(saved);
      setScheduleResult(null);
      setScheduleError(null);
      setDriftResult(null);
      setDriftError(null);
      setDriftEvents([]);
      setDriftEventMessage(null);
      await loadDriftHistory(saved);
    } catch (caught) {
      setSaveError(caught instanceof Error ? caught.message : "数据集版本保存失败");
    } finally {
      setSaveLoading(false);
    }
  }

  async function approveSchedule() {
    setScheduleError(null);
    if (!saveResult) {
      setScheduleError("请先保存数据集版本。");
      return;
    }
    if (taskIds.length === 0) {
      setScheduleError("当前没有可审批调度的商品页任务。");
      return;
    }
    setScheduleLoading(true);
    try {
      const approved = await approveAutomationProductSchedule({
        authorized: result.authorizationConfirmed,
        datasetId: saveResult.dataset.id,
        datasetVersionId: saveResult.version.id,
        taskIds,
        schedulePolicy,
        scheduleCron: scheduleCron.trim() || null,
        freshnessTargetHours: Number.parseInt(freshnessTargetHours, 10) || 24,
        minimumCompletenessPercent: Number.parseInt(minimumCompletenessPercent, 10) || 80,
        note: "Approved from automation dataset review.",
      });
      setScheduleResult(approved);
      setDriftResult(null);
      setDriftError(null);
      setDriftEventMessage(null);
    } catch (caught) {
      setScheduleError(caught instanceof Error ? caught.message : "调度审批失败");
    } finally {
      setScheduleLoading(false);
    }
  }

  async function checkDrift() {
    setDriftError(null);
    if (!saveResult) {
      setDriftError("请先保存数据集版本。");
      return;
    }
    if (!scheduleResult || scheduleResult.summary.approvedTasks === 0) {
      setDriftError("请先审批至少一个商品页任务。");
      return;
    }
    const approvedTaskIds = scheduleResult.approvedTasks.map((task) => task.taskId);
    setDriftLoading(true);
    try {
      const checked = await checkAutomationProductDrift({
        authorized: result.authorizationConfirmed,
        datasetId: saveResult.dataset.id,
        datasetVersionId: saveResult.version.id,
        taskIds: approvedTaskIds,
        completenessDropThresholdPercent: Number.parseInt(driftThresholdPercent, 10) || 10,
        freshnessGraceHours: Number.parseInt(freshnessGraceHours, 10) || 0,
      });
      setDriftResult(checked);
    } catch (caught) {
      setDriftError(caught instanceof Error ? caught.message : "漂移检查失败");
    } finally {
      setDriftLoading(false);
    }
  }

  async function saveDriftSnapshot() {
    setDriftError(null);
    setDriftEventMessage(null);
    if (!saveResult) {
      setDriftError("请先保存数据集版本。");
      return;
    }
    if (!scheduleResult || scheduleResult.summary.approvedTasks === 0) {
      setDriftError("请先审批至少一个商品页任务。");
      return;
    }
    const approvedTaskIds = scheduleResult.approvedTasks.map((task) => task.taskId);
    setDriftEventSaving(true);
    try {
      await saveAutomationProductDriftEvent({
        authorized: result.authorizationConfirmed,
        datasetId: saveResult.dataset.id,
        datasetVersionId: saveResult.version.id,
        taskIds: approvedTaskIds,
        completenessDropThresholdPercent: Number.parseInt(driftThresholdPercent, 10) || 10,
        freshnessGraceHours: Number.parseInt(freshnessGraceHours, 10) || 0,
        note: "Saved from automation drift review.",
      });
      setDriftEventMessage("已保存漂移快照");
      await loadDriftHistory(saveResult);
    } catch (caught) {
      setDriftError(caught instanceof Error ? caught.message : "漂移快照保存失败");
    } finally {
      setDriftEventSaving(false);
    }
  }

  return (
    <div className="mt-4 grid gap-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Fact label="匹配运行" value={`${result.summary.matchedRuns}/${result.summary.requestedRuns}`} />
        <Fact label="行数" value={String(result.summary.rowsCount)} />
        <Fact label="字段数" value={String(result.summary.selectedFields.length)} />
        <Fact label="平均完整度" value={`${result.summary.averageCompletenessPercent}%`} />
        <Fact label="导出" value={result.summary.exportReady ? result.summary.exportFormat : "未就绪"} />
      </div>
      <div className="rounded-xl border border-[#D9E2CC] bg-white p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase text-[#4E7C45]">清洗计划</p>
            <h3 className="mt-1 text-base font-semibold text-[#2E201C]">清洗规则试跑</h3>
            <p className="mt-1 text-sm leading-6 text-[#5F5757]">
              先在样本行上预演清洗效果，确认后保存为可复用计划。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-sm font-semibold text-[#536B40] transition hover:border-[#4E7C45] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={cleaningLoading || cleaningRules.length === 0}
              onClick={() => void runCleaningDryRun()}
              type="button"
            >
              {cleaningLoading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <SlidersHorizontal size={16} aria-hidden="true" />}
              试跑清洗规则
            </button>
            <button
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#2E201C] px-3 text-sm font-semibold text-white transition hover:bg-[#46332C] disabled:cursor-not-allowed disabled:bg-[#B8C9B0]"
              disabled={cleaningSaving || cleaningRules.length === 0}
              onClick={() => void saveCleaningPlan()}
              type="button"
            >
              {cleaningSaving ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
              保存清洗计划
            </button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {cleaningRules.map((rule) => (
            <span
              className="rounded-full border border-[#D9E2CC] bg-[#FAFCF7] px-3 py-1 text-xs font-semibold text-[#536B40]"
              key={`${rule.field}-${rule.operation}`}
            >
              {fieldLabels[rule.field] ?? rule.field}: {rule.operation}
            </span>
          ))}
        </div>
        {cleaningError ? (
          <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
            {cleaningError}
          </p>
        ) : null}
        {cleaningDryRun ? (
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Fact label="样本行" value={String(cleaningDryRun.summary.rowsCount)} />
            <Fact label="变更行" value={String(cleaningDryRun.summary.rowsChanged)} />
            <Fact label="规则数" value={String(cleaningDryRun.summary.rulesCount)} />
            <Fact label="写入边界" value={cleaningDryRun.summary.datasetVersionCreated ? "已写入" : "只试跑"} />
          </div>
        ) : null}
        {cleaningDryRun?.rows.some((row) => row.changedFields.length > 0) ? (
          <div className="mt-3 grid gap-2">
            {cleaningDryRun.rows
              .filter((row) => row.changedFields.length > 0)
              .slice(0, 2)
              .map((row) => (
                <div
                  className="rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] p-3 text-xs text-[#536B40]"
                  key={row.rowId}
                >
                  <p className="font-semibold text-[#2E201C]">
                    变更字段：{row.changedFields.join(" / ")}
                  </p>
                  <p className="mt-1 break-words">
                    缺失字段：{row.missingFieldsAfter.join(" / ") || "无"}
                  </p>
                </div>
              ))}
          </div>
        ) : null}
        {cleaningPlan ? (
          <div className="mt-3 flex flex-col gap-3 rounded-xl border border-[#D9E2CC] bg-[#ECF7EA] p-3 text-sm text-[#2E201C] sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold">
                已保存：{cleaningPlan.cleaningPlan.name} v{cleaningPlan.cleaningPlan.versionNumber}
              </p>
              <p className="mt-1 break-all text-xs text-[#536B40]">
                清洗计划 ID: {cleaningPlan.cleaningPlan.id}
              </p>
            </div>
            <label className="inline-flex items-center gap-2 text-xs font-semibold text-[#536B40]">
              <input
                checked={useCleaningPlan}
                className="h-4 w-4 accent-[#4E7C45]"
                onChange={(event) => setUseCleaningPlan(event.target.checked)}
                type="checkbox"
              />
              保存数据集时使用
            </label>
          </div>
        ) : null}
      </div>
      <div className="rounded-xl border border-[#D9E2CC] bg-white p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <label className="grid min-w-0 flex-1 gap-2 text-sm font-semibold text-[#2E201C]">
            <span>数据集名称</span>
            <input
              className="h-10 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-sm text-[#2E201C] outline-none transition placeholder:text-[#8EA17D] focus:border-[#4E7C45] focus:ring-4 focus:ring-[#E0E8D5]"
              onChange={(event) => {
                setDatasetName(event.target.value);
                setSaveResult(null);
                setSaveError(null);
                setDriftEvents([]);
                setDriftEventMessage(null);
              }}
              value={datasetName}
            />
          </label>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#4E7C45] px-3 text-sm font-semibold text-white transition hover:bg-[#416B39] disabled:cursor-not-allowed disabled:bg-[#B8C9B0]"
            disabled={saveLoading || result.rows.length === 0}
            onClick={() => void saveDatasetVersion()}
            type="button"
          >
            {saveLoading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Database size={16} aria-hidden="true" />}
            保存数据集版本
          </button>
        </div>
        {saveError ? (
          <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
            {saveError}
          </p>
        ) : null}
        {saveResult ? (
          <div className="mt-3 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] p-3">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <Fact label="数据集" value={saveResult.dataset.name} />
              <Fact label="版本" value={`v${saveResult.version.versionNumber}`} />
              <Fact label="保存行数" value={String(saveResult.version.rowCount)} />
              <Fact
                label="完整度"
                value={`${saveResult.version.averageCompletenessPercent}%`}
              />
              <Fact label="状态" value={saveResult.version.status} />
            </div>
            <div className="mt-3 grid gap-2 text-xs font-semibold text-[#536B40]">
              <p className="break-all">数据集 ID: {saveResult.dataset.id}</p>
              <p className="break-all">版本 ID: {saveResult.version.id}</p>
              {saveResult.version.cleaningPlanId ? (
                <p className="break-all">
                  清洗计划 ID: {saveResult.version.cleaningPlanId}
                </p>
              ) : null}
              {saveResult.blockedReasons.map((reason) => (
                <p
                  className="rounded-xl border border-[#D9E2CC] bg-white px-3 py-2"
                  key={reason}
                >
                  {reason}
                </p>
              ))}
            </div>
            <div className="mt-4 rounded-xl border border-[#D9E2CC] bg-white p-3">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase text-[#4E7C45]">Schedule Approval</p>
                  <h3 className="mt-1 text-sm font-semibold text-[#2E201C]">质量通过后审批自动保鲜</h3>
                  <p className="mt-1 text-xs leading-5 text-[#5F5757]">
                    仅写入任务调度元数据，不会立即启动采集运行。
                  </p>
                </div>
                <span className="rounded-full bg-[#ECF7EA] px-3 py-1 text-xs font-semibold text-[#4E7C45]">
                  {taskIds.length} 个任务
                </span>
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-4">
                <label className="grid gap-2 text-xs font-semibold text-[#2E201C]">
                  <span>策略</span>
                  <select
                    className="h-10 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-sm text-[#2E201C] outline-none transition focus:border-[#4E7C45] focus:ring-4 focus:ring-[#E0E8D5]"
                    onChange={(event) => {
                      setSchedulePolicy(event.target.value as "auto_freshness" | "manual_refresh_only");
                      setScheduleResult(null);
                      setScheduleError(null);
                    }}
                    value={schedulePolicy}
                  >
                    <option value="auto_freshness">自动保鲜</option>
                    <option value="manual_refresh_only">只记录审批</option>
                  </select>
                </label>
                <label className="grid gap-2 text-xs font-semibold text-[#2E201C]">
                  <span>目标新鲜度小时</span>
                  <input
                    className="h-10 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-sm text-[#2E201C] outline-none transition focus:border-[#4E7C45] focus:ring-4 focus:ring-[#E0E8D5]"
                    min={1}
                    onChange={(event) => {
                      setFreshnessTargetHours(event.target.value);
                      setScheduleResult(null);
                      setScheduleError(null);
                    }}
                    type="number"
                    value={freshnessTargetHours}
                  />
                </label>
                <label className="grid gap-2 text-xs font-semibold text-[#2E201C]">
                  <span>最低完整度</span>
                  <input
                    className="h-10 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-sm text-[#2E201C] outline-none transition focus:border-[#4E7C45] focus:ring-4 focus:ring-[#E0E8D5]"
                    max={100}
                    min={0}
                    onChange={(event) => {
                      setMinimumCompletenessPercent(event.target.value);
                      setScheduleResult(null);
                      setScheduleError(null);
                    }}
                    type="number"
                    value={minimumCompletenessPercent}
                  />
                </label>
                <label className="grid gap-2 text-xs font-semibold text-[#2E201C]">
                  <span>可选 Cron</span>
                  <input
                    className="h-10 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-sm text-[#2E201C] outline-none transition placeholder:text-[#8EA17D] focus:border-[#4E7C45] focus:ring-4 focus:ring-[#E0E8D5]"
                    onChange={(event) => {
                      setScheduleCron(event.target.value);
                      setScheduleResult(null);
                      setScheduleError(null);
                    }}
                    placeholder="留空使用自动保鲜"
                    value={scheduleCron}
                  />
                </label>
              </div>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-[#5F5757]">
                  当前数据集版本完整度 {saveResult.version.averageCompletenessPercent}%。
                </p>
                <button
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#2E201C] px-3 text-sm font-semibold text-white transition hover:bg-[#46332C] disabled:cursor-not-allowed disabled:bg-[#B8C9B0]"
                  disabled={scheduleLoading || taskIds.length === 0}
                  onClick={() => void approveSchedule()}
                  type="button"
                >
                  {scheduleLoading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Activity size={16} aria-hidden="true" />}
                  审批调度
                </button>
              </div>
              {scheduleError ? (
                <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
                  {scheduleError}
                </p>
              ) : null}
              {scheduleResult ? (
                <div className="mt-3 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] p-3">
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <Fact label="审批任务" value={String(scheduleResult.summary.approvedTasks)} />
                    <Fact label="阻断任务" value={String(scheduleResult.summary.blockedTasks)} />
                    <Fact label="立即运行" value={scheduleResult.summary.runStarted ? "是" : "否"} />
                    <Fact
                      label="目标新鲜度"
                      value={`${scheduleResult.approvedTasks[0]?.freshnessTargetHours ?? 0}h`}
                    />
                  </div>
                  <div className="mt-3 grid gap-2">
                    {scheduleResult.approvedTasks.map((task) => (
                      <p
                        className="rounded-xl border border-[#D9E2CC] bg-white px-3 py-2 text-xs font-semibold text-[#536B40]"
                        key={task.taskId}
                      >
                        {task.taskName} · {task.schedulePolicy} · {task.scheduleCron ?? "auto freshness"}
                      </p>
                    ))}
                    {scheduleResult.blockedTasks.map((task) => (
                      <p
                        className="rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-xs font-semibold text-[#B85F4F]"
                        key={`${task.taskId}-${task.reason}`}
                      >
                        {task.taskId}: {task.reason}
                      </p>
                    ))}
                    {scheduleResult.blockedReasons.map((reason) => (
                      <p
                        className="rounded-xl border border-[#D9E2CC] bg-white px-3 py-2 text-xs font-semibold text-[#536B40]"
                        key={reason}
                      >
                        {reason}
                      </p>
                    ))}
                  </div>
                  <div className="mt-4 rounded-xl border border-[#D9E2CC] bg-white p-3">
                    <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <p className="text-xs font-semibold uppercase text-[#4E7C45]">Drift Check</p>
                        <h3 className="mt-1 text-sm font-semibold text-[#2E201C]">调度漂移检查</h3>
                        <p className="mt-1 text-xs leading-5 text-[#5F5757]">
                          对比最新运行、数据集版本基准和新鲜度目标；只读检查，不会启动采集。
                        </p>
                      </div>
                      <span className="rounded-full bg-[#ECF7EA] px-3 py-1 text-xs font-semibold text-[#4E7C45]">
                        {scheduleResult.summary.approvedTasks} 个已审批任务
                      </span>
                    </div>
                    <div className="mt-3 grid gap-3 lg:grid-cols-4">
                      <label className="grid gap-2 text-xs font-semibold text-[#2E201C]">
                        <span>完整度下降阈值</span>
                        <input
                          className="h-10 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-sm text-[#2E201C] outline-none transition focus:border-[#4E7C45] focus:ring-4 focus:ring-[#E0E8D5]"
                          max={100}
                          min={0}
                          onChange={(event) => {
                            setDriftThresholdPercent(event.target.value);
                            setDriftResult(null);
                            setDriftError(null);
                          }}
                          type="number"
                          value={driftThresholdPercent}
                        />
                      </label>
                      <label className="grid gap-2 text-xs font-semibold text-[#2E201C]">
                        <span>新鲜度宽限小时</span>
                        <input
                          className="h-10 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-sm text-[#2E201C] outline-none transition focus:border-[#4E7C45] focus:ring-4 focus:ring-[#E0E8D5]"
                          max={168}
                          min={0}
                          onChange={(event) => {
                            setFreshnessGraceHours(event.target.value);
                            setDriftResult(null);
                            setDriftError(null);
                          }}
                          type="number"
                          value={freshnessGraceHours}
                        />
                      </label>
                      <div className="flex items-end">
                        <button
                          className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-[#4E7C45] px-3 text-sm font-semibold text-white transition hover:bg-[#416B39] disabled:cursor-not-allowed disabled:bg-[#B8C9B0]"
                          disabled={driftLoading || scheduleResult.summary.approvedTasks === 0}
                          onClick={() => void checkDrift()}
                          type="button"
                        >
                          {driftLoading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <AlertTriangle size={16} aria-hidden="true" />}
                          检查漂移
                        </button>
                      </div>
                      <div className="flex items-end">
                        <button
                          className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-[#2E201C] px-3 text-sm font-semibold text-white transition hover:bg-[#46332C] disabled:cursor-not-allowed disabled:bg-[#B8C9B0]"
                          disabled={
                            driftEventSaving
                            || !driftResult
                            || scheduleResult.summary.approvedTasks === 0
                          }
                          onClick={() => void saveDriftSnapshot()}
                          type="button"
                        >
                          {driftEventSaving ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Database size={16} aria-hidden="true" />}
                          保存漂移快照
                        </button>
                      </div>
                    </div>
                    {driftError ? (
                      <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
                        {driftError}
                      </p>
                    ) : null}
                    {driftEventMessage ? (
                      <p className="mt-3 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 py-2 text-sm font-semibold text-[#4E7C45]">
                        {driftEventMessage}
                      </p>
                    ) : null}
                    {driftResult ? <DriftCheckResult result={driftResult} /> : null}
                    <DriftHistoryResult
                      events={driftEvents}
                      loading={driftHistoryLoading}
                    />
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
      <div className="overflow-x-auto rounded-xl border border-[#D9E2CC] bg-white">
        <table className="min-w-full border-collapse text-left text-sm">
          <thead className="bg-[#ECF7EA] text-xs font-semibold uppercase text-[#4E7C45]">
            <tr>
              <th className="px-3 py-2">完整度</th>
              {result.summary.selectedFields.map((field) => (
                <th className="px-3 py-2" key={field}>
                  {fieldLabels[field] ?? field}
                </th>
              ))}
              <th className="px-3 py-2">缺失字段</th>
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row) => (
              <tr className="border-t border-[#E0E8D5]" key={row.rowId}>
                <td className="px-3 py-2 text-xs font-semibold text-[#4E7C45]">
                  {row.completenessPercent}%
                </td>
                {result.summary.selectedFields.map((field) => (
                  <td className="max-w-[220px] px-3 py-2 text-[#2E201C]" key={`${row.rowId}-${field}`}>
                    <span className="line-clamp-2 break-words">
                      {formatDatasetValue(row.values[field])}
                    </span>
                  </td>
                ))}
                <td className="px-3 py-2 text-xs font-semibold text-[#9E5C4D]">
                  {row.missingFields.join(" / ") || "无"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-xl border border-[#D9E2CC] bg-white p-3">
          <p className="text-sm font-semibold text-[#2E201C]">清洗脚本草稿</p>
          <ul className="mt-2 grid gap-2 text-sm leading-5 text-[#5F5757]">
            {result.cleaningScriptDraft.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-[#D9E2CC] bg-white p-3">
          <p className="text-sm font-semibold text-[#2E201C]">JSON 导出预览</p>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-[#2E201C] p-3 text-xs leading-5 text-[#FFF8F4]">
            {JSON.stringify(result.exportPreview, null, 2)}
          </pre>
        </div>
      </div>
      {result.blockedReasons.length > 0 ? (
        <div className="grid gap-2">
          {result.blockedReasons.map((reason) => (
            <p
              className="rounded-xl border border-[#D9E2CC] bg-white px-3 py-2 text-xs font-semibold text-[#536B40]"
              key={reason}
            >
              {reason}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function DriftHistoryResult({
  events,
  loading,
}: {
  events: AutomationProductDriftEvent[];
  loading: boolean;
}) {
  return (
    <div className="mt-3 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-[#4E7C45]">Drift History</p>
          <h3 className="mt-1 text-sm font-semibold text-[#2E201C]">漂移历史</h3>
          <p className="mt-1 text-xs leading-5 text-[#5F5757]">
            保存后的快照用于追踪数据集版本后续质量变化，不会触发通知。
          </p>
        </div>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-[#536B40]">
          {loading ? "加载中" : `${events.length} 条`}
        </span>
      </div>
      <div className="mt-3 grid gap-2">
        {events.map((event) => (
          <article
            className="rounded-xl border border-[#D9E2CC] bg-white p-3"
            key={event.id}
          >
            <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-sm font-semibold text-[#2E201C]">
                  {event.status} · {new Date(event.createdAt).toLocaleString()}
                </p>
                <p className="mt-1 text-xs leading-5 text-[#5F5757]">
                  {event.note ?? "无备注"}
                </p>
              </div>
              <span
                className={cn(
                  "w-fit rounded-full px-3 py-1 text-xs font-semibold uppercase",
                  event.status === "critical"
                    ? "bg-[#FBE2DC] text-[#B85F4F]"
                    : event.status === "warning"
                      ? "bg-[#FFF1B8] text-[#8A6A12]"
                      : event.status === "blocked"
                        ? "bg-[#F2E1D9] text-[#8A5A4A]"
                        : "bg-[#ECF7EA] text-[#4E7C45]",
                )}
              >
                {event.eventType}
              </span>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <Fact label="关键漂移" value={String(event.summary.criticalTasks)} />
              <Fact label="轻度风险" value={String(event.summary.warningTasks)} />
              <Fact label="阻断" value={String(event.summary.blockedTasks)} />
              <Fact label="运行" value={event.runStarted ? "是" : "否"} />
              <Fact label="告警" value={event.alertCreated ? "已创建" : "未创建"} />
            </div>
          </article>
        ))}
        {!loading && events.length === 0 ? (
          <p className="rounded-xl border border-dashed border-[#D9E2CC] bg-white px-3 py-4 text-sm text-[#5F5757]">
            暂无漂移历史。完成检查后可保存快照。
          </p>
        ) : null}
      </div>
    </div>
  );
}

function DriftCheckResult({ result }: { result: AutomationProductDriftCheck }) {
  return (
    <div className="mt-3 grid gap-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Fact label="已检查" value={`${result.summary.checkedTasks}/${result.summary.requestedTasks}`} />
        <Fact label="关键漂移" value={String(result.summary.criticalTasks)} />
        <Fact label="轻度风险" value={String(result.summary.warningTasks)} />
        <Fact label="缺失字段" value={String(result.summary.missingFieldTasks)} />
        <Fact label="告警创建" value={result.summary.alertCreated ? "是" : "否"} />
      </div>
      <div className="grid gap-2">
        {result.items.map((item) => (
          <article
            className={cn(
              "rounded-xl border bg-[#FAFCF7] p-3",
              item.status === "critical"
                ? "border-[#F0C8C0] bg-[#FFF2EF]"
                : item.status === "warning"
                  ? "border-[#E3D19C] bg-[#FFF9E8]"
                  : item.status === "blocked"
                    ? "border-[#DDBEAF] bg-[#FFF8F4]"
                    : "border-[#D9E2CC] bg-[#FAFCF7]",
            )}
            key={item.taskId}
          >
            <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[#2E201C]">
                  {item.taskName ?? item.taskId}
                </p>
                <p className="mt-1 break-all text-xs leading-5 text-[#5F5757]">
                  {item.sourceUrl ?? "source url unavailable"}
                </p>
              </div>
              <span
                className={cn(
                  "w-fit rounded-full px-3 py-1 text-xs font-semibold uppercase",
                  item.status === "critical"
                    ? "bg-[#FBE2DC] text-[#B85F4F]"
                    : item.status === "warning"
                      ? "bg-[#FFF1B8] text-[#8A6A12]"
                      : item.status === "blocked"
                        ? "bg-[#F2E1D9] text-[#8A5A4A]"
                        : "bg-[#ECF7EA] text-[#4E7C45]",
                )}
              >
                {item.status}
              </span>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Fact
                label="基准完整度"
                value={`${item.datasetVersionCompletenessPercent}%`}
              />
              <Fact
                label="最新完整度"
                value={
                  item.latestCompletenessPercent === null
                    ? "n/a"
                    : `${item.latestCompletenessPercent}%`
                }
              />
              <Fact
                label="下降"
                value={
                  item.completenessDropPercent === null
                    ? "n/a"
                    : `${item.completenessDropPercent}%`
                }
              />
              <Fact
                label="超时"
                value={
                  item.staleHours === null || item.staleHours === 0
                    ? "0h"
                    : `${item.staleHours}h`
                }
              />
            </div>
            <div className="mt-3 grid gap-2 text-xs font-semibold text-[#536B40]">
              {item.blockedReason ? (
                <p className="rounded-xl border border-[#DDBEAF] bg-white px-3 py-2 text-[#8A5A4A]">
                  {item.blockedReason}
                </p>
              ) : null}
              <p className="rounded-xl border border-[#D9E2CC] bg-white px-3 py-2">
                缺失字段：{item.newMissingFields.join(" / ") || "无"}
              </p>
              <p className="rounded-xl border border-[#D9E2CC] bg-white px-3 py-2">
                问题码：{item.issues.join(" / ") || "无"}
              </p>
            </div>
          </article>
        ))}
      </div>
      {result.blockedReasons.map((reason) => (
        <p
          className="rounded-xl border border-[#D9E2CC] bg-white px-3 py-2 text-xs font-semibold text-[#536B40]"
          key={reason}
        >
          {reason}
        </p>
      ))}
    </div>
  );
}

function formatDatasetValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function EmptyAnalysisState({ mode }: { mode: AutomationMode }) {
  return (
    <section className="rounded-2xl border border-dashed border-[#DDBEAF] bg-white/70 p-8">
      <div className="mx-auto max-w-2xl text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#FFF0EA] text-[#C96F5C]">
          <Link2 size={22} aria-hidden="true" />
        </span>
        <h2 className="mt-4 text-lg font-semibold text-[#2E201C]">
          {mode === "product_discovery" ? "等待商品 URL 发现" : "等待 URL 分析"}
        </h2>
        <p className="mt-2 text-sm leading-6 text-[#7A625A]">
          {mode === "product_discovery"
            ? "从集合页、分类页或 sitemap 中提取候选商品 URL，确认后再进入商品详情页字段采集。"
            : "商品页分析会明确字段能否结构化保存，以及是否需要浏览器运行时复核。"}
        </p>
      </div>
    </section>
  );
}

function Panel({
  icon: Icon,
  label,
  title,
  children,
}: {
  icon: typeof Activity;
  label: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
            <Icon size={14} aria-hidden="true" />
            {label}
          </p>
          <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

function MetricPill({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 px-4 py-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
        <Icon size={14} aria-hidden="true" />
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2">
      <p className="text-xs font-semibold text-[#B47767]">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold leading-5 text-[#3B2924]">{value}</p>
    </div>
  );
}

function FieldCandidateCard({ field }: { field: AutomationFieldCandidate }) {
  return (
    <article
      className={cn(
        "min-w-0 rounded-xl border p-3",
        field.selected
          ? "border-[#CDE6C4] bg-[#F7FBF1]"
          : "border-[#F0E1D9] bg-[#FFFDFC]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-[#2E201C]">{field.label}</p>
          <p className="mt-1 text-xs font-semibold uppercase text-[#B47767]">
            {field.key} · {field.dataType}
          </p>
        </div>
        {field.selected ? (
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[#ECF7EA] px-2 py-1 text-xs font-semibold text-[#4E7C45]">
            <CheckCircle2 size={13} aria-hidden="true" />
            保存
          </span>
        ) : (
          <span className="shrink-0 rounded-full bg-[#F6ECE8] px-2 py-1 text-xs font-semibold text-[#9E5C4D]">
            跳过
          </span>
        )}
      </div>
      <p className="mt-3 min-h-10 break-words rounded-lg bg-white/75 px-3 py-2 text-sm leading-5 text-[#5F5757]">
        {field.value === null || field.value === undefined ? "未识别" : String(field.value)}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-semibold text-[#7A625A]">
        <span>{field.source}</span>
        <span>{Math.round(field.confidence * 100)}%</span>
        <span>{field.cleaningRule}</span>
      </div>
    </article>
  );
}

function RiskBadge({ risk }: { risk: string }) {
  const lowRisk = risk === "low";
  return (
    <span
      className={cn(
        "shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold",
        lowRisk ? "bg-[#ECF7EA] text-[#4E7C45]" : "bg-[#FFF3D6] text-[#8C6824]",
      )}
    >
      {formatRisk(risk)}
    </span>
  );
}

function formatPlatform(value: string) {
  const labels: Record<string, string> = {
    independent_ecommerce: "独立站电商",
    shopify: "Shopify",
  };
  return labels[value] ?? value;
}

function formatRisk(value: string) {
  const labels: Record<string, string> = {
    high: "高风险",
    low: "低风险",
    medium: "中风险",
  };
  return labels[value] ?? value;
}

function formatExecutionBoundary(value: AutomationPlatformPackage["executionBoundary"]) {
  const labels: Record<AutomationPlatformPackage["executionBoundary"], string> = {
    blocked: "阻断",
    executable: "可执行",
    sop_import_only: "仅导入 SOP",
  };
  return labels[value];
}

function formatTaskRunStatus(value: string) {
  const labels: Record<string, string> = {
    disabled: "已停用",
    draft: "草稿",
    enabled: "已启用",
    failed: "失败",
    paused: "已暂停",
    running: "运行中",
    success: "成功",
  };
  return labels[value] ?? value;
}

function formatFanoutRunMode(value: string) {
  const labels: Record<string, string> = {
    preview_only: "仅预览，不写入",
  };
  return labels[value] ?? value;
}

function formatFanoutExecutionBoundary(value: string) {
  const labels: Record<string, string> = {
    preview_only_no_database_write: "仅生成预览，不写入数据库",
  };
  return labels[value] ?? value;
}

function normalizeGitHubTopic(value: string) {
  return value
    .trim()
    .replace(/^https?:\/\/github\.com\/topics\//i, "")
    .replace(/^topics\//i, "")
    .replace(/^#/, "")
    .split(/[/?#]/)[0]
    .toLowerCase();
}

function topicFromGitHubUrl(value: string | undefined) {
  if (!value) {
    return null;
  }
  const topic = normalizeGitHubTopic(value);
  return topic || null;
}

function clampInteger(value: number, min: number, max: number, fallback: number) {
  if (!Number.isFinite(value)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.trunc(value)));
}

function formatPageType(value: string) {
  const labels: Record<string, string> = {
    collection_listing: "集合列表页",
    ecommerce_page: "电商页面",
    link_index: "链接索引页",
    product_detail: "商品详情页",
    product_listing: "商品列表页",
    sitemap: "Sitemap",
    unknown_listing: "未知列表页",
  };
  return labels[value] ?? value;
}

function formatShortDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  });
}
