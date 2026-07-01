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
import { useEffect, useMemo, useRef, useState } from "react";

import {
  analyzeAutomationSite,
  approveAutomationProductSchedule,
  buildAutomationBrowserExecutorContract,
  buildAutomationBrowserProductionMetadataRunGate,
  checkAutomationGitHubToolDrift,
  checkAutomationProductDrift,
  cancelAutomationBrowserDiagnosticJob,
  createAutomationCleaningPlan,
  createAutomationBrowserDiagnosticJob,
  createAutomationGitHubToolReportAsset,
  createAutomationProductFanout,
  discoverAutomationProducts,
  dryRunAutomationBrowserExecutableSpec,
  dryRunAutomationBrowserPromotionExecution,
  dryRunAutomationCleaningPlan,
  executeAutomationBrowserPromotion,
  generateAutomationGitHubToolReport,
  listAutomationBrowserDiagnosticJobs,
  listAutomationBrowserDiagnosticJobRuns,
  listAutomationBrowserDiagnostics,
  listAutomationCapabilityProbes,
  listAutomationPlatformPackages,
  listAutomationSiteAnalyses,
  listAutomationProductDriftEvents,
  previewAutomationProductDataset,
  previewAutomationProductFanout,
  previewAutomationBrowserPromotion,
  previewAutomationGitHubToolDataset,
  runAutomationBrowserDiagnosticJobLocal,
  runAutomationProductBatch,
  saveAutomationBrowserAutomationPlan,
  saveAutomationGitHubToolDriftEvent,
  saveAutomationGitHubToolDataset,
  saveAutomationProductDriftEvent,
  saveAutomationProductDataset,
} from "@/lib/api/automation";
import { buildBrowserDiagnosticActionPlan } from "@/lib/browser-diagnostic";
import { listProjects } from "@/lib/api/projects";
import { createSource, enableSource } from "@/lib/api/sources";
import { runTask } from "@/lib/api/tasks";
import { runToolkitPreflight } from "@/lib/api/toolkit";
import { cn } from "@/lib/utils";
import { BrowserDiagnosticImportPanel } from "@/components/common/browser-diagnostic-import-panel";
import {
  WorkbenchFact as Fact,
  WorkbenchPanel as Panel,
  WorkbenchEmptyState,
  WorkbenchMetricPill,
  WorkflowLane,
  WorkflowLaneRail,
  type WorkflowLaneItem,
} from "@/components/common/workbench-ui";
import type {
  BrowserDiagnosticActionPlan,
  BrowserStructureDiagnostic,
} from "@/types/browser-diagnostic";
import type { Project } from "@/types/project";
import type { CollectionTask, Source, TaskRun } from "@/types/source-task";
import type { ToolkitPreflightReport } from "@/types/toolkit";
import type {
  AutomationCleaningPlanCreate,
  AutomationCleaningPlanDryRun,
  AutomationCleaningRule,
  AutomationFieldCandidate,
  AutomationGitHubToolReport,
  AutomationGitHubToolReportAsset,
  AutomationProductBatchRun,
  AutomationProductDatasetPreview,
  AutomationProductDatasetSave,
  AutomationProductDiscovery,
  AutomationProductDriftCheck,
  AutomationProductDriftEvent,
  AutomationProductFanoutCreate,
  AutomationProductFanoutPreview,
  AutomationCapabilityProbe,
  AutomationPlatformPackage,
  AutomationProductScheduleApprove,
  AutomationBrowserDiagnosticJob,
  AutomationBrowserExecutorContract,
  AutomationBrowserLocalRunnerResult,
  AutomationBrowserProductionMetadataRunGate,
  AutomationBrowserPromotionExecution,
  AutomationBrowserPromotionExecutionDryRun,
  AutomationBrowserPromotionPreview,
  AutomationBrowserDiagnosticRun,
  AutomationBrowserExecutableSpecDryRun,
  AutomationSiteAnalysis,
  AutomationSiteAnalysisHistoryItem,
} from "@/types/automation";

const defaultFields = [
  "title",
  "price",
  "price_min",
  "price_max",
  "currency",
  "availability",
  "availability_detail",
  "sku",
  "variant",
  "brand",
  "category",
  "description",
  "image_url",
  "canonical_url",
];

const automationWorkflowLanes: WorkflowLaneItem[] = [
  { id: "intake", title: "采集入口", caption: "目标与授权" },
  { id: "review", title: "复核", caption: "字段与策略" },
  { id: "persist", title: "持久化", caption: "资产写入" },
  { id: "monitor", title: "监控", caption: "质量与漂移" },
  { id: "diagnostics", title: "诊断", caption: "浏览器证据" },
];

const fieldLabels: Record<string, string> = {
  availability: "库存",
  availability_detail: "库存明细",
  brand: "品牌",
  category: "分类",
  canonical_url: "规范 URL",
  currency: "货币",
  default_branch: "默认分支",
  description: "描述",
  content_hash: "内容 Hash",
  feed_url: "Feed URL",
  headings: "标题层级",
  image_url: "主图",
  forks: "Forks",
  meta_description: "页面描述",
  html_url: "仓库 URL",
  issue_activity_open_count: "Issue 活跃数",
  issue_activity_status: "Issue 活跃度",
  language: "语言",
  latest_release_published_at: "Release 时间",
  latest_release_tag: "Release",
  license_spdx_id: "License",
  open_issues: "Open issues",
  page_title: "页面标题",
  published_at: "发布时间",
  link: "链接",
  price: "价格",
  price_max: "最高价",
  price_min: "最低价",
  readme_detected: "README",
  readme_html_url: "README URL",
  readme_size: "README 大小",
  repo_full_name: "仓库全名",
  same_origin_links: "同源链接",
  sku: "SKU",
  stars: "Stars",
  text_sample: "正文样本",
  title: "标题",
  topics: "Topics",
  variant: "变体",
  updated_at: "更新时间",
  pushed_at: "最近推送",
  commit_freshness_days: "推送距今天数",
  commit_freshness_status: "推送新鲜度",
};

const githubToolFields = [
  "repo_full_name",
  "stars",
  "forks",
  "open_issues",
  "language",
  "topics",
  "license_spdx_id",
  "default_branch",
  "latest_release_tag",
  "latest_release_published_at",
  "readme_detected",
  "issue_activity_open_count",
  "issue_activity_status",
  "commit_freshness_days",
  "commit_freshness_status",
  "html_url",
  "pushed_at",
  "updated_at",
];

const signalGroupLabels: Record<string, string> = {
  commit_freshness: "Commit 新鲜度",
  field_missingness: "字段缺失",
  issue_activity: "Issue 活跃",
  popularity: "热度",
  release_freshness: "Release 新鲜度",
  repository_coverage: "仓库覆盖",
};

type GitHubTopicRunState = {
  source: Source;
  task: CollectionTask;
  run: TaskRun | null;
  topic: string;
  maxResults: number;
};

type GenericWebRunState = {
  source: Source;
  task: CollectionTask;
  run: TaskRun | null;
  url: string;
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

type AutomationMode = "product_page" | "product_discovery" | "github_topic_radar" | "structure_preflight";

export function AutomationWorkbench() {
  const [mode, setMode] = useState<AutomationMode>("product_page");
  const [url, setUrl] = useState("https://shop.example/products/demo-bag");
  const [authorized, setAuthorized] = useState(false);
  const [maxProducts, setMaxProducts] = useState("50");
  const [githubTopic, setGithubTopic] = useState("web-scraping");
  const [githubMaxResults, setGithubMaxResults] = useState("20");
  const [githubRun, setGithubRun] = useState<GitHubTopicRunState | null>(null);
  const [preflightReport, setPreflightReport] = useState<ToolkitPreflightReport | null>(null);
  const [browserDiagnostic, setBrowserDiagnostic] = useState<BrowserStructureDiagnostic | null>(
    null,
  );
  const [browserActionPlan, setBrowserActionPlan] = useState<BrowserDiagnosticActionPlan | null>(
    null,
  );
  const [browserPlanSaveLoading, setBrowserPlanSaveLoading] = useState(false);
  const [browserPlanSaveMessage, setBrowserPlanSaveMessage] = useState<string | null>(null);
  const [browserSpecDryRun, setBrowserSpecDryRun] =
    useState<AutomationBrowserExecutableSpecDryRun | null>(null);
  const [browserSpecDryRunLoading, setBrowserSpecDryRunLoading] = useState(false);
  const [browserSpecDryRunError, setBrowserSpecDryRunError] = useState<string | null>(null);
  const [browserDiagnosticJobs, setBrowserDiagnosticJobs] = useState<
    AutomationBrowserDiagnosticJob[]
  >([]);
  const [browserJobLoading, setBrowserJobLoading] = useState(false);
  const [browserJobError, setBrowserJobError] = useState<string | null>(null);
  const [browserExecutorContract, setBrowserExecutorContract] =
    useState<AutomationBrowserExecutorContract | null>(null);
  const [browserExecutorLoading, setBrowserExecutorLoading] = useState(false);
  const [browserExecutorError, setBrowserExecutorError] = useState<string | null>(null);
  const [browserProductionMetadataGate, setBrowserProductionMetadataGate] =
    useState<AutomationBrowserProductionMetadataRunGate | null>(null);
  const [browserProductionMetadataLoading, setBrowserProductionMetadataLoading] =
    useState(false);
  const [browserProductionMetadataError, setBrowserProductionMetadataError] =
    useState<string | null>(null);
  const [browserLocalRuns, setBrowserLocalRuns] = useState<
    AutomationBrowserLocalRunnerResult[]
  >([]);
  const [browserLocalRunResult, setBrowserLocalRunResult] =
    useState<AutomationBrowserLocalRunnerResult | null>(null);
  const [browserLocalRunLoading, setBrowserLocalRunLoading] = useState(false);
  const [browserLocalRunError, setBrowserLocalRunError] = useState<string | null>(null);
  const [browserPromotionPreview, setBrowserPromotionPreview] =
    useState<AutomationBrowserPromotionPreview | null>(null);
  const [browserPromotionPreviewLoading, setBrowserPromotionPreviewLoading] = useState(false);
  const [browserPromotionPreviewError, setBrowserPromotionPreviewError] =
    useState<string | null>(null);
  const [browserPromotionExecutionDryRun, setBrowserPromotionExecutionDryRun] =
    useState<AutomationBrowserPromotionExecutionDryRun | null>(null);
  const [browserPromotionExecution, setBrowserPromotionExecution] =
    useState<AutomationBrowserPromotionExecution | null>(null);
  const [browserPromotionExecutionLoading, setBrowserPromotionExecutionLoading] =
    useState(false);
  const [browserPromotionExecutionError, setBrowserPromotionExecutionError] =
    useState<string | null>(null);
  const [browserPromotionWriteLoading, setBrowserPromotionWriteLoading] = useState(false);
  const [browserPromotionWriteError, setBrowserPromotionWriteError] =
    useState<string | null>(null);
  const [genericWebRun, setGenericWebRun] = useState<GenericWebRunState | null>(null);
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
  const [submitAction, setSubmitAction] = useState<AutomationMode | null>(null);
  const submitInFlightRef = useRef(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [analysisHistory, setAnalysisHistory] = useState<AutomationSiteAnalysisHistoryItem[]>([]);
  const [browserDiagnosticHistory, setBrowserDiagnosticHistory] = useState<
    AutomationBrowserDiagnosticRun[]
  >([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [platformPackages, setPlatformPackages] = useState<AutomationPlatformPackage[]>([]);
  const [platformPackageLoading, setPlatformPackageLoading] = useState(false);
  const [platformPackageError, setPlatformPackageError] = useState<string | null>(null);
  const [appliedPlatformPackage, setAppliedPlatformPackage] =
    useState<AutomationPlatformPackage | null>(null);
  const [capabilityProbes, setCapabilityProbes] = useState<AutomationCapabilityProbe[]>([]);
  const [capabilityProbeLoading, setCapabilityProbeLoading] = useState(false);
  const [capabilityProbeError, setCapabilityProbeError] = useState<string | null>(null);

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
    setCapabilityProbeLoading(true);
    setCapabilityProbeError(null);
    listAutomationCapabilityProbes()
      .then((result) => {
        if (!mounted) {
          return;
        }
        setCapabilityProbes(result.items);
      })
      .catch((caught) => {
        if (!mounted) {
          return;
        }
        setCapabilityProbeError(
          caught instanceof Error ? caught.message : "Capability probe loading failed",
        );
      })
      .finally(() => {
        if (mounted) {
          setCapabilityProbeLoading(false);
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
      setBrowserDiagnosticHistory([]);
      setBrowserDiagnosticJobs([]);
      setBrowserExecutorContract(null);
      setBrowserLocalRuns([]);
      setBrowserLocalRunResult(null);
      setBrowserPromotionPreview(null);
      setBrowserPromotionExecutionDryRun(null);
      setBrowserPromotionExecution(null);
      setBrowserPromotionWriteError(null);
      return;
    }
    void refreshAnalysisHistory(
      selectedProjectId,
      mode === "structure_preflight" ? "browser_automation" : "ecommerce_product",
    );
    if (mode === "structure_preflight") {
      setBrowserLocalRuns([]);
      setBrowserLocalRunResult(null);
      setBrowserPromotionPreview(null);
      setBrowserPromotionExecutionDryRun(null);
      setBrowserPromotionExecution(null);
      setBrowserPromotionWriteError(null);
      void refreshBrowserDiagnosticHistory(selectedProjectId);
      void refreshBrowserDiagnosticJobs(selectedProjectId);
      void refreshBrowserDiagnosticJobRuns(selectedProjectId);
    } else {
      setBrowserDiagnosticHistory([]);
      setBrowserDiagnosticJobs([]);
      setBrowserExecutorContract(null);
      setBrowserLocalRuns([]);
      setBrowserLocalRunResult(null);
      setBrowserPromotionPreview(null);
      setBrowserPromotionExecutionDryRun(null);
      setBrowserPromotionExecution(null);
      setBrowserPromotionWriteError(null);
    }
  }, [mode, selectedProjectId]);

  const selectedFieldCount = useMemo(
    () => analysis?.fieldCandidates.filter((field) => field.selected).length ?? fields.length,
    [analysis, fields.length],
  );
  const isPrimarySubmitting = loading || submitAction !== null;

  async function runGitHubTopicRadar() {
    if (!selectedProjectId) {
      setError("请选择写入项目后再创建 GitHub 主题雷达。");
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
      setPreflightReport(null);
      setGenericWebRun(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "GitHub 主题雷达运行暂不可用");
    } finally {
      setLoading(false);
    }
  }

  async function runStructurePreflight() {
    if (!url.trim()) {
      setError("请填写待预检的公开网页 URL。");
      return;
    }
    setLoading(true);
    try {
      const report = await runToolkitPreflight(url.trim(), authorized);
      setPreflightReport(report);
      setBrowserDiagnostic(null);
      setBrowserActionPlan(null);
      setBrowserPlanSaveMessage(null);
      setGenericWebRun(null);
      setAnalysis(null);
      setDiscovery(null);
      setGithubRun(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "公开网页结构预检失败");
    } finally {
      setLoading(false);
    }
  }

  async function createGenericWebSourceFromPreflight() {
    if (!preflightReport) {
      setError("请先生成结构预检报告。");
      return;
    }
    if (!preflightReport.authorizationGate.allowedToContinue) {
      setError("当前预检存在阻断项，不能自动创建 generic_web 采集源。");
      return;
    }
    if (!selectedProjectId) {
      setError("请选择写入项目后再创建 generic_web 采集源。");
      return;
    }
    const diagnosticPlan = browserActionPlan ?? (browserDiagnostic
      ? buildBrowserDiagnosticActionPlan(browserDiagnostic)
      : null);
    if (diagnosticPlan && !diagnosticPlan.canCreateGenericWebSource) {
      setError(
        diagnosticPlan.blockingReasons[0] ??
          "浏览器诊断不建议直接创建 generic_web，请先复核推荐工具。",
      );
      return;
    }
    const sourceDraft = diagnosticPlan?.sourceDraft;
    setLoading(true);
    try {
      const source = await createSource({
        projectId: selectedProjectId,
        name:
          sourceDraft?.suggestedName ?? `Generic Web: ${hostLabelFromUrl(preflightReport.finalUrl)}`,
        type: "generic_web",
        url: sourceDraft?.url ?? preflightReport.finalUrl,
        config: sourceDraft?.config ?? {
          url: preflightReport.finalUrl,
          extract_mode: "main_content",
        },
      });
      const task = await enableSource(source.id);
      const run = await runTask(task.id);
      setGenericWebRun({ source, task, run, url: preflightReport.finalUrl });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "generic_web 采集源创建或运行失败");
    } finally {
      setLoading(false);
    }
  }

  async function saveBrowserAutomationPlanFromDiagnostic(
    actionPlan: BrowserDiagnosticActionPlan,
    diagnostic: BrowserStructureDiagnostic,
  ) {
    const draft = actionPlan.browserAutomationDraft;
    if (!draft) {
      setError("当前浏览器诊断没有生成 browser automation 方案。");
      return;
    }
    if (!selectedProjectId) {
      setError("请选择写入项目后再保存 browser automation 方案。");
      return;
    }
    if (!authorized) {
      setError("请先确认目标为公开页面或公开 API，且你有权进行采集分析。");
      return;
    }
    setError(null);
    setBrowserPlanSaveMessage(null);
    setBrowserPlanSaveLoading(true);
    try {
      const result = await saveAutomationBrowserAutomationPlan({
        projectId: selectedProjectId,
        requestedUrl: diagnostic.requestedUrl || diagnostic.finalUrl,
        authorized,
        name: draft.suggestedName,
        runner: draft.runner,
        executionMode: draft.config.execution_mode,
        riskLevel: actionPlan.primaryRecommendation.riskLevel,
        fieldContract: {
          fields: draft.config.field_contract.fields.map((field) => ({
            key: field.key,
            label: field.label,
            source: field.source,
            required: field.required,
            selected: field.selected,
            selectorHint: field.selector_hint,
          })),
          cleaningRules: draft.config.field_contract.cleaning_rules,
        },
        browserDiagnostic: {
          schemaVersion: "browser_structure_diagnostic.v1",
          finalUrl: diagnostic.finalUrl,
          recommendedPath: diagnostic.extractionStrategy.recommendedPath,
          confidence: diagnostic.extractionStrategy.confidence,
          fieldStability: diagnostic.extractionStrategy.fieldStability,
          evidenceSource: diagnostic.evidence.source,
          screenshotPath: diagnostic.evidence.screenshotPath,
        },
        diagnosticPayload: serializeBrowserDiagnosticPayload(diagnostic),
        apiCandidates: draft.config.api_candidates,
        guardrails: draft.guardrails,
      });
      setBrowserPlanSaveMessage(
        `已保存 ${result.extractionPlan.name} v${result.extractionPlan.versionNumber}，诊断资产 ${result.browserDiagnostic.id.slice(0, 8)} 已归档，未启动采集运行。`,
      );
      setAnalysisHistory([result.siteAnalysis]);
      setBrowserDiagnosticHistory([result.browserDiagnostic]);
      void refreshAnalysisHistory(selectedProjectId, "browser_automation");
      void refreshBrowserDiagnosticHistory(selectedProjectId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "browser automation 方案保存失败");
    } finally {
      setBrowserPlanSaveLoading(false);
    }
  }

  async function submitAutomation() {
    if (submitInFlightRef.current) {
      return;
    }
    setError(null);
    if (!authorized) {
      setError("请先确认目标为公开页面或公开 API，且你有权进行采集分析。");
      return;
    }
    if (mode === "github_topic_radar") {
      submitInFlightRef.current = true;
      setSubmitAction(mode);
      try {
        await runGitHubTopicRadar();
      } finally {
        submitInFlightRef.current = false;
        setSubmitAction(null);
      }
      return;
    }
    if (mode === "structure_preflight") {
      submitInFlightRef.current = true;
      setSubmitAction(mode);
      try {
        await runStructurePreflight();
      } finally {
        submitInFlightRef.current = false;
        setSubmitAction(null);
      }
      return;
    }
    if (!url.trim()) {
      setError(mode === "product_discovery" ? "请填写待发现的集合页 URL。" : "请填写待分析的商品页 URL。");
      return;
    }
    submitInFlightRef.current = true;
    setSubmitAction(mode);
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
        setPreflightReport(null);
        setGenericWebRun(null);
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
      setPreflightReport(null);
      setGenericWebRun(null);
      if (selectedProjectId) {
        void refreshAnalysisHistory(selectedProjectId, "ecommerce_product");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Automation analysis failed");
    } finally {
      setLoading(false);
      submitInFlightRef.current = false;
      setSubmitAction(null);
    }
  }

  async function refreshAnalysisHistory(
    projectId: string,
    target: "ecommerce_product" | "browser_automation",
  ) {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const result = await listAutomationSiteAnalyses({
        projectId,
        target,
        limit: 5,
      });
      setAnalysisHistory(result.items);
    } catch (caught) {
      setHistoryError(caught instanceof Error ? caught.message : "Analysis history failed");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function refreshBrowserDiagnosticHistory(projectId: string) {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const result = await listAutomationBrowserDiagnostics({
        projectId,
        limit: 5,
      });
      setBrowserDiagnosticHistory(result.items);
    } catch (caught) {
      setHistoryError(caught instanceof Error ? caught.message : "Browser diagnostic history failed");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function refreshBrowserDiagnosticJobs(projectId: string) {
    setBrowserJobLoading(true);
    setBrowserJobError(null);
    try {
      const result = await listAutomationBrowserDiagnosticJobs({
        projectId,
        limit: 5,
      });
      setBrowserDiagnosticJobs(result.items);
    } catch (caught) {
      setBrowserJobError(caught instanceof Error ? caught.message : "Browser diagnostic job list failed");
    } finally {
      setBrowserJobLoading(false);
    }
  }

  async function refreshBrowserDiagnosticJobRuns(projectId: string) {
    setBrowserLocalRunError(null);
    try {
      const result = await listAutomationBrowserDiagnosticJobRuns({
        projectId,
        limit: 5,
      });
      setBrowserLocalRuns(result.items);
      setBrowserLocalRunResult((current) => current ?? result.items[0] ?? null);
    } catch (caught) {
      setBrowserLocalRunError(
        caught instanceof Error ? caught.message : "本地回放证据加载未完成",
      );
    }
  }

  async function validateBrowserExecutableSpec(item: AutomationSiteAnalysisHistoryItem) {
    const plan = item.latestPlan;
    if (!plan) {
      setBrowserSpecDryRunError("当前历史项没有可校验的执行规格。");
      return;
    }
    if (!authorized) {
      setBrowserSpecDryRunError("请先确认授权边界后再校验执行规格。");
      return;
    }
    const config = plan.sourceDraft.config;
    const diagnosticRunId = readString(config.browser_diagnostic_run_id);
    setBrowserSpecDryRunLoading(true);
    setBrowserSpecDryRunError(null);
    setBrowserSpecDryRun(null);
    try {
      const result = await dryRunAutomationBrowserExecutableSpec({
        authorized,
        confirmReview: true,
        siteAnalysisId: item.id,
        extractionPlanId: plan.id,
        browserDiagnosticRunId: diagnosticRunId,
      });
      setBrowserSpecDryRun(result);
    } catch (caught) {
      setBrowserSpecDryRunError(
        caught instanceof Error ? caught.message : "执行规格校验未完成",
      );
    } finally {
      setBrowserSpecDryRunLoading(false);
    }
  }

  async function createBrowserDiagnosticJob(result: AutomationBrowserExecutableSpecDryRun) {
    if (!authorized) {
      setBrowserJobError("请先确认授权边界后再创建诊断任务。");
      return;
    }
    if (result.summary.blockedChecks > 0 || !result.summary.canDryRunAfterReview) {
      setBrowserJobError("当前执行规格仍存在阻断项，不能创建诊断任务。");
      return;
    }
    setBrowserJobLoading(true);
    setBrowserJobError(null);
    try {
      const job = await createAutomationBrowserDiagnosticJob({
        authorized,
        confirmCreate: true,
        siteAnalysisId: result.siteAnalysis.id,
        extractionPlanId: result.extractionPlan.id,
        browserDiagnosticRunId: result.browserDiagnostic?.id ?? null,
        networkObservationMode: "metadata_only",
        artifactMode: "screenshot_reference_only",
        note: "Created from reviewed browser executable spec in automation workbench.",
      });
      setBrowserDiagnosticJobs((current) => [
        job,
        ...current.filter((item) => item.id !== job.id),
      ]);
    } catch (caught) {
      setBrowserJobError(caught instanceof Error ? caught.message : "浏览器诊断任务创建未完成");
    } finally {
      setBrowserJobLoading(false);
    }
  }

  async function cancelBrowserDiagnosticJob(jobId: string) {
    setBrowserJobLoading(true);
    setBrowserJobError(null);
    try {
      const job = await cancelAutomationBrowserDiagnosticJob(jobId);
      setBrowserDiagnosticJobs((current) =>
        current.map((item) => (item.id === job.id ? job : item)),
      );
    } catch (caught) {
      setBrowserJobError(caught instanceof Error ? caught.message : "浏览器诊断任务取消未完成");
    } finally {
      setBrowserJobLoading(false);
    }
  }

  async function buildBrowserExecutorContract(jobId: string) {
    if (!authorized) {
      setBrowserExecutorError("请先确认授权边界后再生成执行器合同。");
      return;
    }
    setBrowserExecutorLoading(true);
    setBrowserExecutorError(null);
    setBrowserProductionMetadataGate(null);
    setBrowserProductionMetadataError(null);
    try {
      const contract = await buildAutomationBrowserExecutorContract(jobId, {
        authorized,
        confirmReview: true,
        artifactRetentionDays: 7,
        maxPreviewRows: 20,
        includeScreenshot: true,
        includeTraceSummary: false,
        includeHarSummary: true,
        note: "Build no-run executor contract from automation workbench.",
      });
      setBrowserExecutorContract(contract);
    } catch (caught) {
      setBrowserExecutorError(
        caught instanceof Error ? caught.message : "执行器合同生成未完成",
      );
    } finally {
      setBrowserExecutorLoading(false);
    }
  }

  async function buildBrowserProductionMetadataGate(jobId: string) {
    if (!authorized) {
      setBrowserProductionMetadataError("请先确认授权边界后再生成生产只读预检。");
      return;
    }
    setBrowserProductionMetadataLoading(true);
    setBrowserProductionMetadataError(null);
    try {
      const gate = await buildAutomationBrowserProductionMetadataRunGate(jobId, {
        authorized,
        confirmReview: true,
        confirmProductionReadonly: true,
        confirmMetadataOnly: true,
        confirmNoFileWrite: true,
        confirmNoCollectionWrite: true,
        targetEnvironment: "production",
        maxMetadataEvents: 100,
        note: "Build production metadata-only gate from automation workbench.",
      });
      setBrowserProductionMetadataGate(gate);
    } catch (caught) {
      setBrowserProductionMetadataError(
        caught instanceof Error ? caught.message : "生产只读预检生成未完成",
      );
    } finally {
      setBrowserProductionMetadataLoading(false);
    }
  }

  async function runBrowserLocalRunner(
    jobId: string,
    runMode: "diagnostic_snapshot_replay" | "ephemeral_browser_harness_probe" =
      "diagnostic_snapshot_replay",
  ) {
    if (!authorized) {
      setBrowserLocalRunError("请先确认授权边界后再生成本地回放证据。");
      return;
    }
    setBrowserLocalRunLoading(true);
    setBrowserLocalRunError(null);
    setBrowserPromotionPreview(null);
    setBrowserPromotionPreviewError(null);
    setBrowserPromotionExecutionDryRun(null);
    setBrowserPromotionExecution(null);
    setBrowserPromotionExecutionError(null);
    setBrowserPromotionWriteError(null);
    setBrowserProductionMetadataGate(null);
    setBrowserProductionMetadataError(null);
    try {
      const result = await runAutomationBrowserDiagnosticJobLocal(jobId, {
        authorized,
        confirmExecute: true,
        runMode,
        confirmRealBrowserProbe: runMode === "ephemeral_browser_harness_probe",
        artifactRetentionDays: 7,
        maxPreviewRows: 20,
        includeScreenshot: true,
        includeTraceSummary: false,
        includeHarSummary: true,
        note:
          runMode === "ephemeral_browser_harness_probe"
            ? "Run ephemeral browser-harness probe from automation workbench."
            : "Run diagnostic snapshot replay from automation workbench.",
      });
      setBrowserLocalRunResult(result);
      setBrowserLocalRuns((current) => [
        result,
        ...current.filter((item) => item.id !== result.id),
      ]);
    } catch (caught) {
      setBrowserLocalRunError(
        caught instanceof Error ? caught.message : "本地回放证据生成未完成",
      );
    } finally {
      setBrowserLocalRunLoading(false);
    }
  }

  async function previewBrowserPromotion(runId: string) {
    if (!authorized) {
      setBrowserPromotionPreviewError("请先确认授权边界后再生成候选包。");
      return;
    }
    setBrowserPromotionPreviewLoading(true);
    setBrowserPromotionPreviewError(null);
    setBrowserPromotionExecutionDryRun(null);
    setBrowserPromotionExecution(null);
    setBrowserPromotionExecutionError(null);
    setBrowserPromotionWriteError(null);
    try {
      const result = await previewAutomationBrowserPromotion(runId, {
        authorized,
        confirmReview: true,
        targetSourceType: "generic_web",
        enableTaskPreview: true,
        note: "Build local browser promotion preview from automation workbench.",
      });
      setBrowserPromotionPreview(result);
    } catch (caught) {
      setBrowserPromotionPreviewError(
        caught instanceof Error ? caught.message : "候选包预览生成未完成",
      );
    } finally {
      setBrowserPromotionPreviewLoading(false);
    }
  }

  async function dryRunBrowserPromotionExecution(runId: string) {
    if (!authorized) {
      setBrowserPromotionExecutionError("请先确认授权边界后再执行预检。");
      return;
    }
    setBrowserPromotionExecutionLoading(true);
    setBrowserPromotionExecutionError(null);
    setBrowserPromotionExecution(null);
    setBrowserPromotionWriteError(null);
    try {
      const result = await dryRunAutomationBrowserPromotionExecution(runId, {
        authorized,
        confirmReview: true,
        confirmNoWrite: true,
        targetSourceType: "generic_web",
        sourceName: browserPromotionPreview?.sourceDraft.suggestedName ?? null,
        scheduleCron: null,
        enableTaskPreview: true,
        note: "Dry-run browser promotion execution from automation workbench.",
      });
      setBrowserPromotionExecutionDryRun(result);
    } catch (caught) {
      setBrowserPromotionExecutionError(
        caught instanceof Error ? caught.message : "执行前预检未完成",
      );
    } finally {
      setBrowserPromotionExecutionLoading(false);
    }
  }

  async function executeBrowserPromotion(runId: string) {
    if (!authorized) {
      setBrowserPromotionWriteError("请先确认授权边界后再创建采集资源。");
      return;
    }
    setBrowserPromotionWriteLoading(true);
    setBrowserPromotionWriteError(null);
    try {
      const result = await executeAutomationBrowserPromotion(runId, {
        authorized,
        confirmReview: true,
        confirmWrite: true,
        confirmCreateCollectionResources: true,
        confirmNoTaskRun: true,
        targetSourceType: "generic_web",
        sourceName: browserPromotionPreview?.sourceDraft.suggestedName ?? null,
        scheduleCron: null,
        confirmSchedule: false,
        idempotencyKey: `browser-promotion:${runId}:generic_web`,
        note: "Create local source and task from automation workbench; do not start task run.",
      });
      setBrowserPromotionExecution(result);
    } catch (caught) {
      setBrowserPromotionWriteError(
        caught instanceof Error ? caught.message : "授权创建未完成",
      );
    } finally {
      setBrowserPromotionWriteLoading(false);
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
    setError(null);
    setAnalysis(null);
    setDiscovery(null);
    setGithubRun(null);
    setPreflightReport(null);
    setGenericWebRun(null);
    const sampleUrl = platformPackage.sampleUrls.find(
      (sample) => sample.entrypoint === executableStrategy.entrypoint,
    );
    if (executableStrategy.entrypoint === "preflight" || executableStrategy.collectorType === "toolkit_preflight") {
      setMode("structure_preflight");
      setUrl(sampleUrl?.url ?? "https://example.com");
      return;
    }
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
    if (executableStrategy.collectorType === "public_feed") {
      setMode("structure_preflight");
      setUrl(sampleUrl?.url ?? "https://example.com/feed.xml");
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
      <WorkflowLaneRail
        activeLane={activeWorkflowLane(mode, {
          analysis,
          discovery,
          githubRun,
          preflightReport,
        })}
        lanes={automationWorkflowLanes}
      />

      <WorkflowLane
        description="选择目标平台、确认公开授权边界，并启动结构分析或 API-first 采集。"
        icon={Search}
        label="01 采集入口"
        title="采集入口与授权边界"
      >
        <section className="max-w-full overflow-hidden rounded-2xl border border-[#EDDCD3] bg-[#FFF8F4] shadow-[0_18px_60px_rgba(115,70,58,0.08)]">
        <div className="grid min-w-0 max-w-full gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_400px]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <Search size={14} aria-hidden="true" />
              采集入口
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C] sm:text-3xl">
              URL 到结构化采集计划
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[#7A625A]">
              针对公开网页、电商页面和 GitHub API-first 主题先做结构解析。结构预检用于判断授权与 DOM 基础字段，商品发现用于提取候选 URL，GitHub 主题雷达用于把公开仓库元数据写入采集源、任务和运行结果。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <WorkbenchMetricPill
                icon={ShieldCheck}
                label="授权边界"
                value={authorized ? "已确认" : "待确认"}
                valueSize="large"
              />
              <WorkbenchMetricPill
                icon={SlidersHorizontal}
                label={
                  mode === "github_topic_radar"
                    ? "仓库上限"
                    : mode === "structure_preflight"
                      ? "预检范围"
                    : mode === "product_discovery"
                      ? "候选上限"
                      : "目标字段"
                }
                value={
                  mode === "github_topic_radar"
                    ? `${githubMaxResults || "20"} 条`
                    : mode === "structure_preflight"
                      ? "DOM/robots"
                    : mode === "product_discovery"
                      ? `${maxProducts || "50"} 条`
                      : `${fields.length} 个`
                }
                valueSize="large"
              />
              <WorkbenchMetricPill
                icon={Database}
                label="结构保存"
                value={
                  mode === "github_topic_radar"
                    ? githubRun
                      ? `${githubRun.run?.recordsCount ?? 0} 条`
                      : "待运行"
                    : mode === "structure_preflight"
                      ? preflightReport
                        ? preflightReport.authorizationGate.allowedToContinue
                          ? "可继续"
                          : "需复核"
                        : "待预检"
                    : mode === "product_discovery"
                    ? discovery
                      ? `${discovery.productCandidates.length} URL`
                      : "待发现"
                    : analysis
                      ? `${selectedFieldCount} 字段`
                      : "待分析"
                }
                valueSize="large"
              />
            </div>
          </div>

          <div className="min-w-0 max-w-full rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
            <form
              className="grid min-w-0 gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void submitAutomation();
              }}
            >
              <div className="grid min-w-0 grid-cols-2 gap-2 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] p-1 sm:grid-cols-4">
                {(
                  [
                    { mode: "product_page", label: "商品页分析" },
                    { mode: "product_discovery", label: "商品发现" },
                    { mode: "github_topic_radar", label: "GitHub 主题" },
                    { mode: "structure_preflight", label: "结构预检" },
                  ] as const
                ).map((item) => (
                  <button
                    aria-pressed={mode === item.mode}
                    className={cn(
                      "min-h-11 min-w-0 whitespace-normal rounded-lg px-2 text-xs font-semibold leading-tight transition",
                      mode === item.mode
                        ? "bg-[#C96F5C] text-white shadow-[0_8px_18px_rgba(201,111,92,0.2)]"
                        : "text-[#7D4F43] hover:bg-[#FFF0EA]",
                    )}
                    key={item.mode}
                    onClick={() => {
                      setMode(item.mode);
                      setError(null);
                      setAnalysis(null);
                      setDiscovery(null);
                      setGithubRun(null);
                      setPreflightReport(null);
                      setGenericWebRun(null);
                      setBrowserDiagnostic(null);
                      setBrowserActionPlan(null);
                      setBrowserPlanSaveMessage(null);
                      if (item.mode === "github_topic_radar") {
                        const osintProject = projects.find((project) => project.domain === "osint");
                        if (osintProject) {
                          setSelectedProjectId(osintProject.id);
                        }
                        return;
                      }
                      if (item.mode === "structure_preflight") {
                        setUrl("https://example.com");
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
                  <span>
                    {mode === "product_discovery"
                      ? "集合页 / 列表页 URL"
                      : mode === "structure_preflight"
                        ? "公开网页 URL"
                        : "商品页 URL"}
                  </span>
                  <input
                    className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                    onChange={(event) => setUrl(event.target.value)}
                    placeholder={
                      mode === "product_discovery"
                        ? "https://example.com/collections/category"
                        : mode === "structure_preflight"
                          ? "https://example.com"
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
              ) : mode === "structure_preflight" ? (
                <div className="grid gap-3">
                  <div className="rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] p-3">
                    <p className="text-sm font-semibold text-[#3B2924]">预检范围</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {["HTTP 状态", "robots/sitemap", "DOM 摘要", "链接与表单"].map((item) => (
                        <span
                          className="rounded-full border border-[#E8D4CB] bg-white px-2.5 py-1 text-xs font-semibold text-[#7D4F43]"
                          key={item}
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                  <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
                    <span>后续采集写入项目</span>
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
                disabled={isPrimarySubmitting}
                type="submit"
              >
                {isPrimarySubmitting ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Search size={16} aria-hidden="true" />}
                {isPrimarySubmitting
                  ? "处理中"
                  : mode === "github_topic_radar"
                    ? "创建并运行 GitHub 主题雷达"
                    : mode === "structure_preflight"
                      ? "生成结构预检"
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
          </div>
        </div>
      </section>
      </WorkflowLane>

      <WorkflowLane
        description="先看能力边界和平台包，再决定当前目标应走结构预检、商品发现、GitHub API 或后续浏览器诊断。"
        icon={SlidersHorizontal}
        label="02 复核"
        title="能力评估与平台包选择"
      >
        <CapabilityProbePanel
          error={capabilityProbeError}
          items={capabilityProbes}
          loading={capabilityProbeLoading}
        />

        <PlatformPackageMatrix
          appliedPackage={appliedPlatformPackage}
          error={platformPackageError}
          loading={platformPackageLoading}
          onApply={applyPlatformPackage}
          packages={platformPackages}
        />
      </WorkflowLane>

      {mode === "product_page" ? (
        <WorkflowLane
          description="回看已保存的站点分析与采集计划，避免重复创建低质量草稿。"
          icon={ClipboardList}
          label="02 复核"
          title="历史采集方案"
        >
          <AnalysisHistoryPanel
            error={historyError}
            items={analysisHistory}
            loading={historyLoading}
          />
        </WorkflowLane>
      ) : null}

      {mode === "structure_preflight" ? (
        <WorkflowLane
          description="把 browser-harness 诊断、执行规格校验、只读诊断任务和本地回放证据集中在独立诊断 lane。"
          icon={ShieldCheck}
          label="05 诊断证据"
          title="浏览器诊断与执行器边界"
        >
          <div className="grid gap-3">
            <BrowserDiagnosticHistoryPanel
              error={historyError}
              items={browserDiagnosticHistory}
              loading={historyLoading}
            />
            <AnalysisHistoryPanel
              description="已保存的 browser automation 方案会显示 selector、等待条件和 API 候选等执行规格。"
              emptyText="暂无自动化方案历史。保存只读自动化方案后，执行规格会出现在这里。"
              error={historyError}
              items={analysisHistory}
              loading={historyLoading}
              browserJobLoading={browserJobLoading}
              onBrowserJobCreate={(result) => void createBrowserDiagnosticJob(result)}
              onBrowserSpecDryRun={(item) => void validateBrowserExecutableSpec(item)}
              specDryRunError={browserSpecDryRunError}
              specDryRunLoading={browserSpecDryRunLoading}
              specDryRunResult={browserSpecDryRun}
              title="自动化方案历史"
            />
            <BrowserDiagnosticJobHistoryPanel
              error={browserJobError}
              items={browserDiagnosticJobs}
              loading={browserJobLoading}
              onCancel={(jobId) => void cancelBrowserDiagnosticJob(jobId)}
              onBuildContract={(jobId) => void buildBrowserExecutorContract(jobId)}
              contractLoading={browserExecutorLoading}
            />
            <BrowserExecutorContractPanel
              contract={browserExecutorContract}
              error={browserExecutorError}
              productionGate={browserProductionMetadataGate}
              productionGateError={browserProductionMetadataError}
              productionGateLoading={browserProductionMetadataLoading}
              loading={browserExecutorLoading}
              onBuildProductionGate={(jobId) =>
                void buildBrowserProductionMetadataGate(jobId)
              }
              onRunHarnessProbe={(jobId) =>
                void runBrowserLocalRunner(jobId, "ephemeral_browser_harness_probe")
              }
              onRunLocal={(jobId) =>
                void runBrowserLocalRunner(jobId, "diagnostic_snapshot_replay")
              }
              runLoading={browserLocalRunLoading}
            />
            <BrowserLocalRunnerResultPanel
              error={browserLocalRunError}
              items={browserLocalRuns}
              loading={browserLocalRunLoading}
              onExecutePromotion={(runId) => void executeBrowserPromotion(runId)}
              onDryRunPromotionExecution={(runId) =>
                void dryRunBrowserPromotionExecution(runId)
              }
              onPreviewPromotion={(runId) => void previewBrowserPromotion(runId)}
              promotionExecution={browserPromotionExecution}
              promotionExecutionDryRun={browserPromotionExecutionDryRun}
              promotionExecutionError={browserPromotionExecutionError}
              promotionExecutionLoading={browserPromotionExecutionLoading}
              promotionWriteError={browserPromotionWriteError}
              promotionWriteLoading={browserPromotionWriteLoading}
              promotionPreview={browserPromotionPreview}
              promotionPreviewError={browserPromotionPreviewError}
              promotionPreviewLoading={browserPromotionPreviewLoading}
              result={browserLocalRunResult}
            />
          </div>
        </WorkflowLane>
      ) : null}

      <WorkflowLane
        description={workflowResultDescription(mode)}
        icon={workflowResultIcon(mode)}
        label={workflowResultLabel(mode)}
        title={workflowResultTitle(mode)}
      >
        {mode === "github_topic_radar" ? (
          githubRun ? (
            <GitHubTopicRunResult result={githubRun} />
          ) : (
            <EmptyAnalysisState mode={mode} />
          )
        ) : mode === "structure_preflight" ? (
          preflightReport ? (
            <StructurePreflightResult
              authorized={authorized}
              browserActionPlan={browserActionPlan}
              browserPlanSaveLoading={browserPlanSaveLoading}
              browserPlanSaveMessage={browserPlanSaveMessage}
              genericWebRun={genericWebRun}
              loading={loading}
              onBrowserActionPlanChange={setBrowserActionPlan}
              onBrowserDiagnosticChange={setBrowserDiagnostic}
              onCreateGenericWebSource={() => void createGenericWebSourceFromPreflight()}
              onSaveBrowserAutomationPlan={saveBrowserAutomationPlanFromDiagnostic}
              report={preflightReport}
              selectedProjectId={selectedProjectId}
            />
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
      </WorkflowLane>
    </div>
  );
}

function AnalysisHistoryPanel({
  browserJobLoading = false,
  description = "已保存的站点分析会在这里形成可复用采集计划。",
  emptyText = "暂无历史分析。完成一次商品页分析后，系统会保存默认采集计划。",
  error,
  items,
  loading,
  onBrowserJobCreate,
  onBrowserSpecDryRun,
  specDryRunError = null,
  specDryRunLoading = false,
  specDryRunResult = null,
  title = "历史分析",
}: {
  description?: string;
  emptyText?: string;
  error: string | null;
  items: AutomationSiteAnalysisHistoryItem[];
  loading: boolean;
  browserJobLoading?: boolean;
  onBrowserJobCreate?: (result: AutomationBrowserExecutableSpecDryRun) => void;
  onBrowserSpecDryRun?: (item: AutomationSiteAnalysisHistoryItem) => void;
  specDryRunError?: string | null;
  specDryRunLoading?: boolean;
  specDryRunResult?: AutomationBrowserExecutableSpecDryRun | null;
  title?: string;
}) {
  return (
    <div className="mt-4 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#2E201C]">{title}</p>
          <p className="mt-1 text-xs leading-5 text-[#7A625A]">
            {description}
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
              {item.latestPlan?.collectorType === "browser_automation" ? (
                <div className="mt-3 grid gap-2">
                  <ExecutableSpecSummary config={item.latestPlan.sourceDraft.config} />
                  {onBrowserSpecDryRun ? (
                    <button
                      className="inline-flex w-fit items-center gap-2 rounded-lg border border-[#E8D4CB] bg-[#FFF8F4] px-3 py-1.5 text-xs font-semibold text-[#7D4F43] transition hover:border-[#C96F5C] hover:text-[#9E5C4D] disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={specDryRunLoading}
                      onClick={() => onBrowserSpecDryRun(item)}
                      type="button"
                    >
                      {specDryRunLoading ? (
                        <Loader2 className="animate-spin" size={14} aria-hidden="true" />
                      ) : (
                        <ShieldCheck size={14} aria-hidden="true" />
                      )}
                      校验执行规格
                    </button>
                  ) : null}
                  {specDryRunError ? (
                    <p className="rounded-lg border border-[#F0C8C0] bg-[#FFF2EF] px-2.5 py-2 text-xs font-semibold text-[#B85F4F]">
                      {specDryRunError}
                    </p>
                  ) : null}
                  {specDryRunResult?.extractionPlan.id === item.latestPlan.id ? (
                    <BrowserSpecDryRunResult
                      jobLoading={browserJobLoading}
                      onCreateJob={onBrowserJobCreate}
                      result={specDryRunResult}
                    />
                  ) : null}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-xl border border-dashed border-[#E8D4CB] px-3 py-3 text-xs leading-5 text-[#7A625A]">
          {emptyText}
        </p>
      )}
    </div>
  );
}

function BrowserDiagnosticHistoryPanel({
  error,
  items,
  loading,
}: {
  error: string | null;
  items: AutomationBrowserDiagnosticRun[];
  loading: boolean;
}) {
  return (
    <div className="mt-4 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#2E201C]">浏览器诊断资产</p>
          <p className="mt-1 text-xs leading-5 text-[#7A625A]">
            已保存的真实浏览器结构诊断会在这里沉淀为后续采集规格证据。
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
                    {formatRecommendedPath(item.recommendedPath as ToolkitPreflightReport["collectionStrategy"]["recommendedPath"])}
                    {" · "}
                    {Math.round(item.confidence * 100)}%
                  </p>
                  <p className="mt-1 truncate text-xs text-[#7A625A]">{item.finalUrl}</p>
                </div>
                <span className="shrink-0 rounded-full border border-[#E8D4CB] px-2 py-1 text-xs font-semibold text-[#7D4F43]">
                  {item.runStarted ? "已运行" : "只读资产"}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold text-[#9E5C4D]">
                <span>字段稳定性 {item.fieldStability ?? "unknown"}</span>
                <span>{item.evidenceSource}</span>
                <span>{formatShortDate(item.createdAt)}</span>
              </div>
              {item.evidenceAsset ? (
                <p className="mt-2 truncate text-xs font-semibold text-[#6F7F52]">
                  Evidence {item.evidenceAsset.assetId}
                </p>
              ) : null}
              {item.blockedReasons.length > 0 ? (
                <p className="mt-2 rounded-lg bg-[#FFF8F4] px-2 py-1 text-xs leading-5 text-[#7A625A]">
                  {item.blockedReasons[0]}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-xl border border-dashed border-[#E8D4CB] px-3 py-3 text-xs leading-5 text-[#7A625A]">
          暂无浏览器诊断资产。导入 browser-harness 诊断 JSON 并保存方案后会出现在这里。
        </p>
      )}
    </div>
  );
}

function BrowserDiagnosticJobHistoryPanel({
  contractLoading,
  error,
  items,
  loading,
  onBuildContract,
  onCancel,
}: {
  contractLoading: boolean;
  error: string | null;
  items: AutomationBrowserDiagnosticJob[];
  loading: boolean;
  onBuildContract: (jobId: string) => void;
  onCancel: (jobId: string) => void;
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#2E201C]">浏览器诊断任务</p>
          <p className="mt-1 text-xs leading-5 text-[#7A625A]">
            这里只保存已审核的只读任务意图，真实浏览器执行器尚未接入。
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
                    {formatBrowserJobStatus(item.status)}
                  </p>
                  <p className="mt-1 truncate text-xs text-[#7A625A]">{item.finalUrl}</p>
                </div>
                <span className="shrink-0 rounded-full border border-[#E8D4CB] px-2 py-1 text-xs font-semibold text-[#7D4F43]">
                  {item.runStarted ? "已运行" : "未运行"}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold text-[#9E5C4D]">
                <span>{item.selectorScope.length} selector</span>
                <span>{item.waitPolicy.length} 等待条件</span>
                <span>{formatShortDate(item.createdAt)}</span>
              </div>
              {item.evidenceAsset ? (
                <p className="mt-2 truncate text-xs font-semibold text-[#6F7F52]">
                  Evidence {item.evidenceAsset.assetId}
                </p>
              ) : null}
              {item.blockedReasons.length > 0 ? (
                <p className="mt-2 rounded-lg bg-[#FFF8F4] px-2 py-1 text-xs leading-5 text-[#7A625A]">
                  {formatBrowserJobReason(item.blockedReasons[0])}
                </p>
              ) : null}
              {item.status !== "cancelled" ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    className="inline-flex w-fit items-center gap-2 rounded-lg border border-[#B8D8BA] bg-white px-3 py-1.5 text-xs font-semibold text-[#2F6B3A] transition hover:border-[#6AA772] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={contractLoading}
                    onClick={() => onBuildContract(item.id)}
                    type="button"
                  >
                    {contractLoading ? (
                      <Loader2 className="animate-spin" size={14} aria-hidden="true" />
                    ) : (
                      <ShieldCheck size={14} aria-hidden="true" />
                    )}
                    生成执行器合同
                  </button>
                  <button
                    className="inline-flex w-fit items-center gap-2 rounded-lg border border-[#E8D4CB] bg-[#FFF8F4] px-3 py-1.5 text-xs font-semibold text-[#7D4F43] transition hover:border-[#C96F5C] hover:text-[#9E5C4D] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={loading}
                    onClick={() => onCancel(item.id)}
                    type="button"
                  >
                    {loading ? (
                      <Loader2 className="animate-spin" size={14} aria-hidden="true" />
                    ) : (
                      <CheckCircle2 size={14} aria-hidden="true" />
                    )}
                    取消任务
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-xl border border-dashed border-[#E8D4CB] px-3 py-3 text-xs leading-5 text-[#7A625A]">
          暂无浏览器诊断任务。先校验执行规格，再显式创建只读任务。
        </p>
      )}
    </div>
  );
}

function BrowserExecutorContractPanel({
  contract,
  error,
  loading,
  productionGate,
  productionGateError,
  productionGateLoading,
  onBuildProductionGate,
  onRunHarnessProbe,
  onRunLocal,
  runLoading,
}: {
  contract: AutomationBrowserExecutorContract | null;
  error: string | null;
  loading: boolean;
  productionGate: AutomationBrowserProductionMetadataRunGate | null;
  productionGateError: string | null;
  productionGateLoading: boolean;
  onBuildProductionGate: (jobId: string) => void;
  onRunHarnessProbe: (jobId: string) => void;
  onRunLocal: (jobId: string) => void;
  runLoading: boolean;
}) {
  if (!contract && !error && !loading && !productionGateError && !productionGateLoading) {
    return null;
  }
  const adapterName = readString(contract?.adapter.adapter_name) ?? "browser_harness_read_only_local";
  const isolationMode = readString(contract?.runtimeIsolation.mode) ?? "local_ephemeral_browser_context";
  const retentionDays = String(contract?.artifactRetentionPolicy.retention_days ?? "-");
  const passedChecks = contract?.readinessChecks.filter((item) => item.status === "passed").length ?? 0;
  const reviewChecks = contract?.readinessChecks.filter((item) => item.status === "review").length ?? 0;
  const blockedChecks = contract?.readinessChecks.filter((item) => item.status === "blocked").length ?? 0;
  const gateRecord = readRecord(productionGate?.gate);
  const executionPolicy = readRecord(productionGate?.executionPolicy);
  const metadataPlan = readRecord(productionGate?.metadataPlan);
  const networkObservation = readRecord(metadataPlan?.network_observation);
  const artifactCapture = readRecord(metadataPlan?.artifact_capture);
  const collectionSideEffects = readRecord(metadataPlan?.collection_side_effects);
  const gateStatus = readString(gateRecord?.status) ?? "pending";
  const metadataEventLimit =
    typeof metadataPlan?.max_metadata_events === "number"
      ? metadataPlan.max_metadata_events
      : "-";
  return (
    <div className="rounded-2xl border border-[#D7E8D7] bg-[#F3FBF3] p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#2F6B3A]">执行器合同</p>
          <p className="mt-1 text-xs leading-5 text-[#4F7F56]">
            合同限定本地隔离执行器输入、产物保留和禁止动作；本机探测只打开临时 tab 读取页面元信息。
          </p>
        </div>
        {loading ? <Loader2 className="animate-spin text-[#2F6B3A]" size={16} aria-hidden="true" /> : null}
      </div>
      {error ? (
        <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-xs font-semibold text-[#B85F4F]">
          {error}
        </p>
      ) : null}
      {contract ? (
        <div className="mt-3 grid gap-2 text-xs leading-5 text-[#4F7F56]">
          <div className="rounded-xl border border-[#B8D8BA] bg-white p-3">
            <p className="font-semibold text-[#2F6B3A]">
              {adapterName} · {isolationMode}
            </p>
            <div className="mt-2 flex flex-wrap gap-2 font-semibold">
              <span>{passedChecks} 通过</span>
              <span>{reviewChecks} 复核</span>
              <span>{blockedChecks} 阻断</span>
              <span>保留 {retentionDays} 天</span>
            </div>
          </div>
          <div className="rounded-xl border border-[#B8D8BA] bg-white p-3">
            <p className="font-semibold text-[#2F6B3A]">允许动作</p>
            <p className="mt-1">{contract.allowedActions.slice(0, 4).join(" / ")}</p>
          </div>
          <div className="rounded-xl border border-[#B8D8BA] bg-white p-3">
            <p className="font-semibold text-[#2F6B3A]">禁止动作</p>
            <p className="mt-1">{contract.deniedActions.slice(0, 5).join(" / ")}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="inline-flex w-fit items-center gap-2 rounded-lg border border-[#B8D8BA] bg-white px-3 py-1.5 text-xs font-semibold text-[#2F6B3A] transition hover:border-[#6AA772] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={runLoading || blockedChecks > 0}
              onClick={() => onRunLocal(contract.job.id)}
              type="button"
            >
              {runLoading ? (
                <Loader2 className="animate-spin" size={14} aria-hidden="true" />
              ) : (
                <Activity size={14} aria-hidden="true" />
              )}
              生成本地回放证据
            </button>
            <button
              className="inline-flex w-fit items-center gap-2 rounded-lg border border-[#AFC9E8] bg-white px-3 py-1.5 text-xs font-semibold text-[#284E7A] transition hover:border-[#6A91BE] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={productionGateLoading || blockedChecks > 0}
              onClick={() => onBuildProductionGate(contract.job.id)}
              type="button"
            >
              {productionGateLoading ? (
                <Loader2 className="animate-spin" size={14} aria-hidden="true" />
              ) : (
                <ShieldCheck size={14} aria-hidden="true" />
              )}
              生产只读预检
            </button>
            <button
              className="inline-flex w-fit items-center gap-2 rounded-lg border border-[#AFC9E8] bg-white px-3 py-1.5 text-xs font-semibold text-[#284E7A] transition hover:border-[#6A91BE] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={runLoading || blockedChecks > 0}
              onClick={() => onRunHarnessProbe(contract.job.id)}
              type="button"
            >
              {runLoading ? (
                <Loader2 className="animate-spin" size={14} aria-hidden="true" />
              ) : (
                <Activity size={14} aria-hidden="true" />
              )}
              运行本机浏览器探测
            </button>
          </div>
          {productionGateError ? (
            <p className="rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-xs font-semibold text-[#B85F4F]">
              {productionGateError}
            </p>
          ) : null}
          {productionGate ? (
            <div className="rounded-xl border border-[#AFC9E8] bg-white p-3 text-[#284E7A]">
              <div className="flex flex-wrap items-center gap-2 font-semibold">
                <span>生产只读预检</span>
                <span>{productionGate.evidenceGrade}</span>
                <span>{gateStatus}</span>
                <span>上限 {metadataEventLimit} 条元数据事件</span>
              </div>
              <div className="mt-2 grid gap-1 text-xs leading-5 sm:grid-cols-2">
                <span>自动 worker: {String(executionPolicy?.automatic_api_worker_start)}</span>
                <span>浏览器启动: {String(productionGate.browserStarted)}</span>
                <span>运行启动: {String(productionGate.runStarted)}</span>
                <span>文件写入: {String(productionGate.filesWritten)}</span>
                <span>采集资源写入: {String(productionGate.collectionResourcesWritten)}</span>
                <span>provider 调用: {String(productionGate.providerCalled)}</span>
                <span>网络范围: metadata-only {String(networkObservation?.metadata_only)}</span>
                <span>headers/body: {String(networkObservation?.capture_headers)} / {String(networkObservation?.capture_body)}</span>
                <span>截图/trace/HAR: {String(artifactCapture?.screenshot)} / {String(artifactCapture?.trace)} / {String(artifactCapture?.har)}</span>
                <span>采集对象创建: {String(collectionSideEffects?.source_created)} / {String(collectionSideEffects?.task_created)} / {String(collectionSideEffects?.dataset_created)}</span>
              </div>
              {productionGate.blockedReasons.length ? (
                <p className="mt-2 text-xs font-semibold text-[#B85F4F]">
                  {productionGate.blockedReasons.join(" / ")}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function BrowserLocalRunnerResultPanel({
  error,
  items,
  loading,
  onDryRunPromotionExecution,
  onExecutePromotion,
  onPreviewPromotion,
  promotionExecution,
  promotionExecutionDryRun,
  promotionExecutionError,
  promotionExecutionLoading,
  promotionWriteError,
  promotionWriteLoading,
  promotionPreview,
  promotionPreviewError,
  promotionPreviewLoading,
  result,
}: {
  error: string | null;
  items: AutomationBrowserLocalRunnerResult[];
  loading: boolean;
  onDryRunPromotionExecution?: (runId: string) => void;
  onExecutePromotion?: (runId: string) => void;
  onPreviewPromotion?: (runId: string) => void;
  promotionExecution: AutomationBrowserPromotionExecution | null;
  promotionExecutionDryRun: AutomationBrowserPromotionExecutionDryRun | null;
  promotionExecutionError: string | null;
  promotionExecutionLoading: boolean;
  promotionWriteError: string | null;
  promotionWriteLoading: boolean;
  promotionPreview: AutomationBrowserPromotionPreview | null;
  promotionPreviewError: string | null;
  promotionPreviewLoading: boolean;
  result: AutomationBrowserLocalRunnerResult | null;
}) {
  const visibleResult = result ?? items[0] ?? null;
  if (!visibleResult && !error && !loading) {
    return null;
  }
  const firstPreviewRow = readRecord(visibleResult?.previewRows[0]);
  const previewValues = readRecord(firstPreviewRow?.values);
  const visibleValues = previewValues ? Object.entries(previewValues).slice(0, 4) : [];
  const selectorEvaluations =
    visibleResult?.selectorEvaluations.length
      ? visibleResult.selectorEvaluations.slice(0, 4)
      : visibleResult?.selectorResults.slice(0, 4) ?? [];
  const networkMetadataSummary = readRecord(visibleResult?.networkMetadataSummary);
  const promotionGate = readRecord(visibleResult?.promotionGate);
  const redactionSummary = readRecord(visibleResult?.redactionSummary);
  const apiCandidateCount =
    typeof networkMetadataSummary?.api_candidate_count === "number"
      ? networkMetadataSummary.api_candidate_count
      : null;
  const resourceCount =
    typeof networkMetadataSummary?.resource_count === "number"
      ? networkMetadataSummary.resource_count
      : null;
  const canPromote = promotionGate?.can_create_collection_resources === true;
  const promotionReasons = readArray(promotionGate?.reasons)
    .map((item) => (typeof item === "string" ? item : null))
    .filter((item): item is string => item !== null)
    .slice(0, 3);
  const previewCount = String(visibleResult?.previewRows.length ?? 0);
  const isHarnessProbe =
    visibleResult?.runMode === "ephemeral_browser_harness_probe";
  const browserStatusLabel = visibleResult?.browserStarted
    ? isHarnessProbe
      ? "已完成浏览器只读探测"
      : "已启动浏览器"
    : "未启动真实浏览器";
  const previewGate = readRecord(promotionPreview?.promotionGate);
  const previewReasons = readArray(previewGate?.reasons)
    .map((item) => (typeof item === "string" ? item : null))
    .filter((item): item is string => item !== null)
    .slice(0, 4);
  const executionGate = readRecord(promotionExecutionDryRun?.promotionGate);
  const executionReasons = readArray(executionGate?.reasons)
    .map((item) => (typeof item === "string" ? item : null))
    .filter((item): item is string => item !== null)
    .slice(0, 4);
  const visibleExecutionChecks = promotionExecutionDryRun?.validationChecks.slice(0, 5) ?? [];
  const dryRunHasBlockedCheck =
    promotionExecutionDryRun?.validationChecks.some((check) => check.status === "blocked") ??
    true;
  return (
    <div className="rounded-2xl border border-[#D7E0EF] bg-[#F7FAFF] p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#284E7A]">本地回放证据</p>
          <p className="mt-1 text-xs leading-5 text-[#506B8D]">
            {isHarnessProbe
              ? "基于 browser-harness 临时 tab 读取页面元信息；不写文件，不创建采集资源。"
              : "基于已保存诊断快照生成字段预览；未启动真实浏览器，不写文件，不创建采集资源。"}
          </p>
        </div>
        {loading ? <Loader2 className="animate-spin text-[#284E7A]" size={16} aria-hidden="true" /> : null}
      </div>
      {error ? (
        <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-xs font-semibold text-[#B85F4F]">
          {error}
        </p>
      ) : null}
      {visibleResult ? (
        <div className="mt-3 grid gap-2 text-xs leading-5 text-[#506B8D]">
          <div className="rounded-xl border border-[#C5D6ED] bg-white p-3">
            <p className="font-semibold text-[#284E7A]">
              {formatBrowserLocalRunStatus(visibleResult.status)} · {visibleResult.runMode}
            </p>
            <div className="mt-2 flex flex-wrap gap-2 font-semibold">
              <span>{previewCount} 行预览</span>
              <span>{browserStatusLabel}</span>
              <span>{visibleResult.filesWritten ? "已写文件" : "未写文件"}</span>
              <span>
                {visibleResult.collectionResourcesWritten ? "已写采集资源" : "未写采集资源"}
              </span>
            </div>
          </div>
          {visibleValues.length > 0 ? (
            <div className="rounded-xl border border-[#C5D6ED] bg-white p-3">
              <p className="font-semibold text-[#284E7A]">字段预览</p>
              <div className="mt-1 grid gap-1">
                {visibleValues.map(([key, value]) => (
                  <p key={key}>
                    <span className="font-semibold">{key}：</span>
                    {String(value)}
                  </p>
                ))}
              </div>
            </div>
          ) : null}
          {selectorEvaluations.length > 0 ? (
            <div className="rounded-xl border border-[#C5D6ED] bg-white p-3">
              <p className="font-semibold text-[#284E7A]">selector 求值</p>
              <div className="mt-1 grid gap-1">
                {selectorEvaluations.map((item) => {
                  const field = readString(item.field) ?? "unknown";
                  const status = readString(item.status) ?? "unknown";
                  const matchCount =
                    typeof item.match_count === "number" ? item.match_count : null;
                  return (
                    <p key={field}>
                      <span className="font-semibold">{field}：</span>
                      {formatBrowserLocalSelectorStatus(status)}
                      {matchCount !== null ? `，${matchCount} 个匹配` : ""}
                    </p>
                  );
                })}
              </div>
            </div>
          ) : null}
          {networkMetadataSummary ? (
            <div className="rounded-xl border border-[#C5D6ED] bg-white p-3">
              <p className="font-semibold text-[#284E7A]">network metadata</p>
              <div className="mt-1 grid gap-1">
                <p>
                  API 候选：
                  {apiCandidateCount ?? "未统计"}
                  {resourceCount !== null ? `；资源数：${resourceCount}` : ""}
                </p>
                <p>
                  {networkMetadataSummary.capture_headers === true
                    ? "已采集 headers"
                    : "未采集 headers"}
                  ；
                  {networkMetadataSummary.capture_body === true
                    ? "已采集正文"
                    : "未采集正文"}
                </p>
              </div>
            </div>
          ) : null}
          {promotionGate ? (
            <div className="rounded-xl border border-[#C5D6ED] bg-white p-3">
              <p className="font-semibold text-[#284E7A]">
                晋级门禁：{canPromote ? "可进入采集资源创建" : "不能直接创建采集资源"}
              </p>
              {promotionReasons.length > 0 ? (
                <div className="mt-1 grid gap-1">
                  {promotionReasons.map((reason) => (
                    <p key={reason}>{formatBrowserJobReason(reason)}</p>
                  ))}
                </div>
              ) : null}
              {redactionSummary ? (
                <p className="mt-1">
                  {redactionSummary.cookies_captured === true
                    ? "已采集 cookie"
                    : "未采集 cookie"}
                  ；
                  {redactionSummary.headers_captured === true
                    ? "已采集 headers"
                    : "未采集 headers"}
                  ；
                  {redactionSummary.bodies_captured === true
                    ? "已采集正文"
                    : "未采集正文"}
                </p>
              ) : null}
            </div>
          ) : null}
          <div className="rounded-xl border border-[#C5D6ED] bg-white p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold text-[#284E7A]">采集候选预览</p>
                <p className="mt-1">
                  仅生成候选包和阻断原因；不创建采集源、任务或任务运行。
                </p>
              </div>
              {onPreviewPromotion ? (
                <button
                  className="inline-flex w-fit items-center gap-2 rounded-lg border border-[#AFC9E8] bg-white px-3 py-1.5 text-xs font-semibold text-[#284E7A] transition hover:border-[#6A91BE] disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={promotionPreviewLoading}
                  onClick={() => onPreviewPromotion(visibleResult.id)}
                  type="button"
                >
                  {promotionPreviewLoading ? (
                    <Loader2 className="animate-spin" size={14} aria-hidden="true" />
                  ) : (
                    <ClipboardList size={14} aria-hidden="true" />
                  )}
                  生成候选包
                </button>
              ) : null}
            </div>
            {promotionPreviewError ? (
              <p className="mt-2 rounded-lg border border-[#F0C8C0] bg-[#FFF2EF] px-2.5 py-2 font-semibold text-[#B85F4F]">
                {promotionPreviewError}
              </p>
            ) : null}
            {promotionPreview ? (
              <div className="mt-2 grid gap-2">
                <div className="grid gap-1">
                  <p>
                    <span className="font-semibold">采集源候选：</span>
                    {promotionPreview.sourceDraft.suggestedName} · {promotionPreview.sourceDraft.type}
                  </p>
                  <p>
                    <span className="font-semibold">任务候选：</span>
                    {promotionPreview.taskDraft
                      ? `${promotionPreview.taskDraft.status} · ${promotionPreview.taskDraft.schedulePolicy}`
                      : "未生成"}
                  </p>
                  <p>
                    <span className="font-semibold">证据：</span>
                    {promotionPreview.evidenceAsset.assetId}
                  </p>
                </div>
                {previewReasons.length > 0 ? (
                  <div className="grid gap-1">
                    {previewReasons.map((reason) => (
                      <p key={reason}>{formatBrowserJobReason(reason)}</p>
                    ))}
                  </div>
                ) : null}
                <div className="flex flex-wrap gap-2 font-semibold">
                  <span>{promotionPreview.sourceCreated ? "已创建采集源" : "未创建采集源"}</span>
                  <span>{promotionPreview.taskCreated ? "已创建任务" : "未创建任务"}</span>
                  <span>
                    {promotionPreview.taskRunStarted ? "已启动任务运行" : "未启动任务运行"}
                  </span>
                </div>
                <div className="rounded-lg border border-[#D7E0EF] bg-[#F7FAFF] p-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold text-[#284E7A]">执行前预检</p>
                    {onDryRunPromotionExecution ? (
                      <button
                        className="inline-flex w-fit items-center gap-2 rounded-lg border border-[#AFC9E8] bg-white px-3 py-1.5 text-xs font-semibold text-[#284E7A] transition hover:border-[#6A91BE] disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={promotionExecutionLoading}
                        onClick={() => onDryRunPromotionExecution(visibleResult.id)}
                        type="button"
                      >
                        {promotionExecutionLoading ? (
                          <Loader2 className="animate-spin" size={14} aria-hidden="true" />
                        ) : (
                          <ShieldCheck size={14} aria-hidden="true" />
                        )}
                        运行预检
                      </button>
                    ) : null}
                  </div>
                  <p className="mt-1">复用正式配置校验，但仍不写入采集源、任务或任务运行。</p>
                  {promotionExecutionError ? (
                    <p className="mt-2 rounded-lg border border-[#F0C8C0] bg-[#FFF2EF] px-2.5 py-2 font-semibold text-[#B85F4F]">
                      {promotionExecutionError}
                    </p>
                  ) : null}
                  {promotionExecutionDryRun ? (
                    <div className="mt-2 grid gap-2">
                      <div className="flex flex-wrap gap-2 font-semibold">
                        <span>{promotionExecutionDryRun.writeAllowed ? "允许写入" : "不允许写入"}</span>
                        <span>{promotionExecutionDryRun.canExecute ? "可执行" : "不可直接执行"}</span>
                        <span>
                          {promotionExecutionDryRun.collectionResourcesWritten
                            ? "已写采集资源"
                            : "未写采集资源"}
                        </span>
                      </div>
                      {visibleExecutionChecks.length > 0 ? (
                        <div className="grid gap-1">
                          {visibleExecutionChecks.map((check) => (
                            <p key={check.key}>
                              <span className="font-semibold">
                                {formatBrowserPromotionCheckStatus(check.status)}：
                              </span>
                              {formatBrowserJobReason(check.message)}
                            </p>
                          ))}
                        </div>
                      ) : null}
                      {executionReasons.length > 0 ? (
                        <div className="grid gap-1">
                          {executionReasons.map((reason) => (
                            <p key={reason}>{formatBrowserJobReason(reason)}</p>
                          ))}
                        </div>
                      ) : null}
                      <div className="flex flex-wrap items-center gap-2 pt-1">
                        {onExecutePromotion ? (
                          <button
                            className="inline-flex w-fit items-center gap-2 rounded-lg border border-[#B8D8BA] bg-white px-3 py-1.5 text-xs font-semibold text-[#2F6B3A] transition hover:border-[#6AA772] disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={promotionWriteLoading || dryRunHasBlockedCheck}
                            onClick={() => onExecutePromotion(visibleResult.id)}
                            type="button"
                          >
                            {promotionWriteLoading ? (
                              <Loader2 className="animate-spin" size={14} aria-hidden="true" />
                            ) : (
                              <Database size={14} aria-hidden="true" />
                            )}
                            授权创建采集资源
                          </button>
                        ) : null}
                        <span>
                          {dryRunHasBlockedCheck
                            ? "仍有阻断项，不能创建。"
                            : "可创建采集源和任务，但不会启动任务运行。"}
                        </span>
                      </div>
                    </div>
                  ) : null}
                  {promotionWriteError ? (
                    <p className="mt-2 rounded-lg border border-[#F0C8C0] bg-[#FFF2EF] px-2.5 py-2 font-semibold text-[#B85F4F]">
                      {promotionWriteError}
                    </p>
                  ) : null}
                  {promotionExecution ? (
                    <div className="mt-2 grid gap-1 border-t border-[#D7E0EF] pt-2">
                      <p className="font-semibold text-[#2F6B3A]">
                        {promotionExecution.idempotencyReplayed
                          ? "已复用上次创建结果"
                          : "已创建采集资源"}
                      </p>
                      <p>
                        <span className="font-semibold">采集源：</span>
                        {promotionExecution.source?.name ?? "未返回"} ·{" "}
                        {promotionExecution.source?.type ?? "未知类型"}
                      </p>
                      <p>
                        <span className="font-semibold">任务：</span>
                        {promotionExecution.task?.status ?? "未返回"} · 未启动任务运行
                      </p>
                      <p>
                        <span className="font-semibold">幂等：</span>
                        {promotionExecution.idempotencyScope}
                      </p>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ExecutableSpecSummary({ config }: { config: Record<string, unknown> }) {
  const spec = readRecord(config.executable_spec);
  if (!spec) {
    return null;
  }
  const selectorCount = readArray(spec.selector_contract).length;
  const waitCount = readArray(spec.wait_conditions).length;
  const apiCandidateCount = readArray(spec.api_candidates).length;
  const reviewRequired = spec.manual_review_required === true;
  return (
    <div className="mt-3 rounded-lg border border-[#E8D4CB] bg-[#FFF8F4] px-2.5 py-2 text-xs leading-5 text-[#7A625A]">
      <span className="font-semibold text-[#7D4F43]">执行规格：</span>
      {selectorCount} 个 selector、{waitCount} 个等待条件、{apiCandidateCount} 个 API 候选；
      {reviewRequired ? "需要人工复核后再运行。" : "低风险字段可进入后续 dry-run 审核。"}
    </div>
  );
}

function BrowserSpecDryRunResult({
  jobLoading = false,
  onCreateJob,
  result,
}: {
  jobLoading?: boolean;
  onCreateJob?: (result: AutomationBrowserExecutableSpecDryRun) => void;
  result: AutomationBrowserExecutableSpecDryRun;
}) {
  const visibleChecks = result.checks.slice(0, 4);
  const canCreateJob = result.summary.blockedChecks === 0 && result.summary.canDryRunAfterReview;
  return (
    <div className="rounded-lg border border-[#D7E8D7] bg-[#F3FBF3] px-2.5 py-2 text-xs leading-5 text-[#2F6B3A]">
      <div className="flex flex-wrap items-center gap-2 font-semibold">
        <span>规格校验：{formatSpecDryRunStatus(result.summary.status)}</span>
        <span>{result.summary.passedChecks}/{result.summary.totalChecks} 通过</span>
        <span>{result.summary.reviewChecks} 项需复核</span>
        <span>{result.summary.blockedChecks} 项阻断</span>
      </div>
      <p className="mt-1 text-[#4F7F56]">
        {result.summary.selectorCount} 个 selector、{result.summary.waitConditionCount} 个等待条件、
        {result.summary.apiCandidateCount} 个 API 候选；未启动浏览器运行，未允许写入。
      </p>
      <div className="mt-2 grid gap-1">
        {visibleChecks.map((check) => (
          <p className="text-[#4F7F56]" key={check.key}>
            <span className="font-semibold">{formatSpecCheckStatus(check.status)}</span>
            {" · "}
            {check.label}：{check.message}
          </p>
        ))}
      </div>
      {canCreateJob && onCreateJob ? (
        <button
          className="mt-3 inline-flex w-fit items-center gap-2 rounded-lg border border-[#B8D8BA] bg-white px-3 py-1.5 text-xs font-semibold text-[#2F6B3A] transition hover:border-[#6AA772] disabled:cursor-not-allowed disabled:opacity-60"
          disabled={jobLoading}
          onClick={() => onCreateJob(result)}
          type="button"
        >
          {jobLoading ? (
            <Loader2 className="animate-spin" size={14} aria-hidden="true" />
          ) : (
            <ShieldCheck size={14} aria-hidden="true" />
          )}
          创建浏览器诊断任务
        </button>
      ) : null}
    </div>
  );
}

function CapabilityProbePanel({
  error,
  items,
  loading,
}: {
  error: string | null;
  items: AutomationCapabilityProbe[];
  loading: boolean;
}) {
  const agentReach = items.find((item) => item.agentReach)?.agentReach ?? null;
  return (
    <section className="rounded-2xl border border-[#EDDCD3] bg-white p-5 shadow-[0_12px_40px_rgba(115,70,58,0.06)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-[#FFF8F4] px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
            <Activity size={14} aria-hidden="true" />
            Capability Probe
          </div>
          <h2 className="mt-3 text-xl font-semibold tracking-normal text-[#2E201C]">
            平台能力探测
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#7A625A]">
            展示每个平台当前可用后端、凭据模式、执行边界和禁止动作；probe 只做体检，不创建采集资源。
          </p>
        </div>
        {loading ? (
          <Loader2 className="animate-spin text-[#C96F5C]" size={18} aria-hidden="true" />
        ) : (
          <span className="rounded-full border border-[#E8D4CB] px-3 py-1 text-xs font-semibold text-[#7D4F43]">
            {items.length} probes
          </span>
        )}
      </div>

      {agentReach ? (
        <div className="mt-4 grid gap-2 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3 text-sm text-[#7A625A] md:grid-cols-3">
          <p>
            <span className="font-semibold text-[#2E201C]">Agent Reach：</span>
            {agentReach.installed ? "已发现" : "未安装"}
          </p>
          <p>
            <span className="font-semibold text-[#2E201C]">Doctor：</span>
            {formatCapabilityStatus(agentReach.doctorStatus)}
          </p>
          <p>
            <span className="font-semibold text-[#2E201C]">Side effects：</span>
            read/search 均未调用
          </p>
        </div>
      ) : null}

      {error ? (
        <p className="mt-4 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-semibold text-[#B85F4F]">
          {error}
        </p>
      ) : null}

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        {items.map((item) => {
          const primaryCandidate = item.backendCandidates[0];
          return (
            <article
              className="grid min-w-0 gap-3 rounded-2xl border border-[#F0E1D9] bg-[#FFFDFC] p-4"
              key={item.platformId}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-words text-base font-semibold text-[#2E201C]">
                    {item.platformLabel}
                  </p>
                  <p className="mt-1 text-xs font-semibold uppercase text-[#B47767]">
                    {item.platformId}
                  </p>
                </div>
                <span
                  className={cn(
                    "shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold",
                    capabilityStatusClass(item.doctorStatus),
                  )}
                >
                  {formatCapabilityStatus(item.doctorStatus)}
                </span>
              </div>

              <div className="grid gap-2 text-sm text-[#7A625A]">
                <p>
                  <span className="font-semibold text-[#2E201C]">边界：</span>
                  {formatCapabilityBoundary(item.executionBoundary)}
                </p>
                <p>
                  <span className="font-semibold text-[#2E201C]">凭据：</span>
                  {formatCredentialMode(item.credentialMode)}
                </p>
                <p>
                  <span className="font-semibold text-[#2E201C]">主后端：</span>
                  {primaryCandidate?.label ?? "待定义"} ·{" "}
                  {formatCapabilityStatus(primaryCandidate?.status ?? "unknown")}
                </p>
                {item.evidenceAsset ? (
                  <p>
                    <span className="font-semibold text-[#2E201C]">证据：</span>
                    {item.evidenceAsset.assetId}
                  </p>
                ) : null}
              </div>

              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">
                  Allowed outputs
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {item.allowedOutputs.map((output) => (
                    <span
                      className="rounded-full border border-[#D7E8D7] bg-[#F3FBF3] px-2.5 py-1 text-xs font-semibold text-[#2F6B3A]"
                      key={output}
                    >
                      {formatCapabilityOutput(output)}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">Forbidden</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {item.forbiddenActions.slice(0, 5).map((action) => (
                    <span
                      className="rounded-full border border-[#F0C8C0] bg-[#FFF2EF] px-2.5 py-1 text-xs font-semibold text-[#B85F4F]"
                      key={action}
                    >
                      {action}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-[#F0E1D9] bg-white p-3">
                <p className="text-xs font-semibold uppercase text-[#B47767]">Next action</p>
                <p className="mt-1 text-sm leading-6 text-[#7A625A]">
                  {item.nextActions[0] ?? "等待下一阶段定义。"}
                </p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
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
          <div className="flex flex-wrap gap-2 text-xs font-semibold text-[#4F7F56]">
            <span>version {appliedPackage.version}</span>
            <span>{formatPackageLifecycleStatus(appliedPackage.lifecycleStatus)}</span>
            <span>{appliedPackage.evidenceGrade}</span>
            <span>{formatAuthorizationRequired(appliedPackage.authorizationRequired)}</span>
          </div>
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
                  <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold text-[#7D4F43]">
                    <span>v{platformPackage.version}</span>
                    <span>{formatPackageLifecycleStatus(platformPackage.lifecycleStatus)}</span>
                    <span>{platformPackage.evidenceGrade}</span>
                    <span>{formatAuthorizationRequired(platformPackage.authorizationRequired)}</span>
                  </div>
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

              <div className="grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                <div className="rounded-xl border border-[#F0E1D9] bg-white p-3">
                  <p className="text-xs font-semibold uppercase text-[#B47767]">
                    Acceptance Registry
                  </p>
                  <div className="mt-2 grid gap-2">
                    {platformPackage.acceptanceRegistry.slice(0, 3).map((gate) => (
                      <div
                        className="grid gap-1 border-b border-[#F5E9E3] pb-2 last:border-0 last:pb-0"
                        key={gate.id}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-[#2E201C]">{gate.label}</p>
                          <span className="rounded-full bg-[#FFF0EA] px-2 py-1 text-xs font-semibold text-[#9E5C4D]">
                            {formatAcceptanceStatus(gate.status)}
                          </span>
                        </div>
                        <p className="text-xs leading-5 text-[#7A625A]">
                          {gate.evidenceGrade} · {gate.evidence}
                        </p>
                        {gate.nextAction ? (
                          <p className="text-xs leading-5 text-[#9E5C4D]">{gate.nextAction}</p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-xl border border-[#F0E1D9] bg-white p-3">
                  <p className="text-xs font-semibold uppercase text-[#B47767]">Governance</p>
                  <div className="mt-2 grid gap-2 text-xs leading-5 text-[#7A625A]">
                    <p>
                      <span className="font-semibold text-[#2E201C]">Owner：</span>
                      {platformPackage.owner}
                    </p>
                    <p>
                      <span className="font-semibold text-[#2E201C]">Cleanup：</span>
                      {platformPackage.cleanupPolicy}
                    </p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {platformPackage.forbiddenActions.slice(0, 6).map((action) => (
                      <span
                        className="rounded-full border border-[#F0C8C0] bg-[#FFF2EF] px-2 py-1 text-xs font-semibold text-[#B85F4F]"
                        key={action}
                      >
                        {action}
                      </span>
                    ))}
                  </div>
                </div>
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
  const [datasetFields, setDatasetFields] = useState<string[]>(githubToolFields);
  const [datasetPreview, setDatasetPreview] = useState<AutomationProductDatasetPreview | null>(null);
  const [datasetName, setDatasetName] = useState(`GitHub Tool Radar ${result.topic}`);
  const [saveResult, setSaveResult] = useState<AutomationProductDatasetSave | null>(null);
  const [datasetError, setDatasetError] = useState<string | null>(null);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [toolReport, setToolReport] = useState<AutomationGitHubToolReport | null>(null);
  const [toolReportAsset, setToolReportAsset] = useState<AutomationGitHubToolReportAsset | null>(null);
  const [toolDrift, setToolDrift] = useState<AutomationProductDriftCheck | null>(null);
  const [toolDriftEvent, setToolDriftEvent] = useState<AutomationProductDriftEvent | null>(null);
  const [toolIntelLoading, setToolIntelLoading] = useState<"report" | "asset" | "drift" | "snapshot" | null>(null);
  const [toolIntelError, setToolIntelError] = useState<string | null>(null);
  const taskRunIds = result.run?.id ? [result.run.id] : [];
  const taskIds = result.task.id ? [result.task.id] : [];

  function toggleDatasetField(field: string) {
    setDatasetFields((current) =>
      current.includes(field)
        ? current.filter((item) => item !== field)
        : [...current, field],
    );
    setDatasetPreview(null);
    setSaveResult(null);
    setToolReport(null);
    setToolReportAsset(null);
    setToolDrift(null);
    setToolDriftEvent(null);
    setDatasetError(null);
    setToolIntelError(null);
  }

  async function generateDatasetPreview() {
    setDatasetError(null);
    if (taskRunIds.length === 0) {
      setDatasetError("当前没有可进入工具数据集预览的成功运行。");
      return;
    }
    if (datasetFields.length === 0) {
      setDatasetError("请至少选择一个工具数据字段。");
      return;
    }
    setDatasetLoading(true);
    try {
      const preview = await previewAutomationGitHubToolDataset({
        authorized: true,
        taskRunIds,
        fields: datasetFields,
        maxRows: Math.max(result.maxResults, 1),
      });
      setDatasetPreview(preview);
      setSaveResult(null);
      setToolReport(null);
      setToolReportAsset(null);
      setToolDrift(null);
      setToolDriftEvent(null);
    } catch (caught) {
      setDatasetError(caught instanceof Error ? caught.message : "工具数据集预览生成失败");
    } finally {
      setDatasetLoading(false);
    }
  }

  async function saveDatasetVersion() {
    setDatasetError(null);
    if (!datasetPreview) {
      setDatasetError("请先生成工具数据集预览。");
      return;
    }
    if (!datasetName.trim()) {
      setDatasetError("请填写工具数据集名称。");
      return;
    }
    setSaveLoading(true);
    try {
      const saved = await saveAutomationGitHubToolDataset({
        authorized: datasetPreview.authorizationConfirmed,
        name: datasetName.trim(),
        description: `来自 GitHub topic ${result.topic} 的工具情报数据集。`,
        taskRunIds,
        fields: datasetPreview.summary.selectedFields,
        maxRows: Math.max(datasetPreview.rows.length, 1),
      });
      setSaveResult(saved);
      setToolReport(null);
      setToolReportAsset(null);
      setToolDrift(null);
      setToolDriftEvent(null);
      setToolIntelError(null);
    } catch (caught) {
      setDatasetError(caught instanceof Error ? caught.message : "工具数据集保存失败");
    } finally {
      setSaveLoading(false);
    }
  }

  async function generateToolReport() {
    if (!saveResult) {
      setToolIntelError("请先保存工具数据集。");
      return;
    }
    setToolIntelLoading("report");
    setToolIntelError(null);
    try {
      const report = await generateAutomationGitHubToolReport({
        authorized: saveResult.authorizationConfirmed,
        datasetId: saveResult.dataset.id,
        datasetVersionId: saveResult.version.id,
        minStars: 10000,
        topLimit: 5,
      });
      setToolReport(report);
      setToolReportAsset(null);
    } catch (caught) {
      setToolIntelError(caught instanceof Error ? caught.message : "工具雷达报告生成失败");
    } finally {
      setToolIntelLoading(null);
    }
  }

  async function saveToolReportAsset() {
    if (!saveResult) {
      setToolIntelError("请先保存工具数据集。");
      return;
    }
    if (!toolReport) {
      setToolIntelError("请先生成工具雷达报告。");
      return;
    }
    setToolIntelLoading("asset");
    setToolIntelError(null);
    try {
      const asset = await createAutomationGitHubToolReportAsset({
        authorized: saveResult.authorizationConfirmed,
        confirmCreate: true,
        datasetId: saveResult.dataset.id,
        datasetVersionId: saveResult.version.id,
        minStars: 10000,
        topLimit: 5,
      });
      setToolReport(asset);
      setToolReportAsset(asset);
    } catch (caught) {
      setToolIntelError(caught instanceof Error ? caught.message : "工具雷达报告保存失败");
    } finally {
      setToolIntelLoading(null);
    }
  }

  async function checkToolDrift() {
    if (!saveResult) {
      setToolIntelError("请先保存工具数据集。");
      return;
    }
    if (taskIds.length === 0) {
      setToolIntelError("当前没有可用于工具漂移检查的任务。");
      return;
    }
    setToolIntelLoading("drift");
    setToolIntelError(null);
    try {
      const drift = await checkAutomationGitHubToolDrift({
        authorized: saveResult.authorizationConfirmed,
        datasetId: saveResult.dataset.id,
        datasetVersionId: saveResult.version.id,
        taskIds,
        completenessDropThresholdPercent: 10,
        freshnessGraceHours: 24,
      });
      setToolDrift(drift);
      setToolDriftEvent(null);
    } catch (caught) {
      setToolIntelError(caught instanceof Error ? caught.message : "工具情报漂移检查失败");
    } finally {
      setToolIntelLoading(null);
    }
  }

  async function saveToolDriftSnapshot() {
    if (!saveResult) {
      setToolIntelError("请先保存工具数据集。");
      return;
    }
    if (!toolDrift) {
      setToolIntelError("请先完成工具情报漂移检查。");
      return;
    }
    setToolIntelLoading("snapshot");
    setToolIntelError(null);
    try {
      const event = await saveAutomationGitHubToolDriftEvent({
        authorized: saveResult.authorizationConfirmed,
        datasetId: saveResult.dataset.id,
        datasetVersionId: saveResult.version.id,
        taskIds,
        completenessDropThresholdPercent: 10,
        freshnessGraceHours: 24,
        note: "Saved from GitHub tool radar review.",
      });
      setToolDriftEvent(event);
    } catch (caught) {
      setToolIntelError(caught instanceof Error ? caught.message : "工具情报漂移快照保存失败");
    } finally {
      setToolIntelLoading(null);
    }
  }

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Panel icon={Activity} label="GitHub 主题雷达" title="公开仓库情报采集结果">
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

      <div className="grid gap-4 xl:col-span-2">
        <Panel icon={Database} label="Tool Dataset" title="工具情报数据集">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm leading-6 text-[#5F5757]">
                从本次 GitHub topic 运行中提取仓库字段，保存为可导出、可复用的数据集版本。
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {githubToolFields.map((field) => (
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
                    {fieldLabels[field] ?? field}
                  </button>
                ))}
              </div>
            </div>
            <button
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#2E201C] px-3 text-sm font-semibold text-white transition hover:bg-[#46332C] disabled:cursor-not-allowed disabled:bg-[#B8C9B0]"
              disabled={datasetLoading || taskRunIds.length === 0 || datasetFields.length === 0}
              onClick={() => void generateDatasetPreview()}
              type="button"
            >
              {datasetLoading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Database size={16} aria-hidden="true" />}
              生成工具数据集预览
            </button>
          </div>
          {datasetError ? (
            <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
              {datasetError}
            </p>
          ) : null}
          {datasetPreview ? (
            <div className="mt-4 grid gap-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <Fact label="匹配运行" value={`${datasetPreview.summary.matchedRuns}/${datasetPreview.summary.requestedRuns}`} />
                <Fact label="仓库行数" value={String(datasetPreview.summary.rowsCount)} />
                <Fact label="字段数" value={String(datasetPreview.summary.selectedFields.length)} />
                <Fact label="平均完整度" value={`${datasetPreview.summary.averageCompletenessPercent}%`} />
                <Fact label="导出草稿" value={datasetPreview.summary.exportReady ? "已就绪" : "未就绪"} />
              </div>
              {githubToolSchemaFacts(datasetPreview.exportPreview).length > 0 ? (
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                  {githubToolSchemaFacts(datasetPreview.exportPreview).map((fact) => (
                    <Fact label={fact.label} value={fact.value} key={fact.label} />
                  ))}
                </div>
              ) : null}
              <div className="flex flex-wrap gap-2">
                {datasetPreview.summary.selectedFields.map((field) => (
                  <span
                    className="rounded-full border border-[#D9E2CC] bg-white px-2.5 py-1 text-xs font-semibold text-[#536B40]"
                    key={field}
                  >
                    {field}
                  </span>
                ))}
              </div>
              <div className="overflow-x-auto rounded-xl border border-[#D9E2CC] bg-white">
                <table className="min-w-full border-collapse text-left text-sm">
                  <thead className="bg-[#ECF7EA] text-xs font-semibold uppercase text-[#4E7C45]">
                    <tr>
                      <th className="px-3 py-2">完整度</th>
                      {datasetPreview.summary.selectedFields.map((field) => (
                        <th className="px-3 py-2" key={field}>
                          {fieldLabels[field] ?? field}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {datasetPreview.rows.map((row) => (
                      <tr className="border-t border-[#E0E8D5]" key={row.rowId}>
                        <td className="px-3 py-2 text-xs font-semibold text-[#4E7C45]">
                          {row.completenessPercent}%
                        </td>
                        {datasetPreview.summary.selectedFields.map((field) => (
                          <td className="max-w-[220px] px-3 py-2 text-[#2E201C]" key={`${row.rowId}-${field}`}>
                            <span className="line-clamp-2 break-words">
                              {formatDatasetValue(row.values[field])}
                            </span>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-col gap-3 rounded-xl border border-[#D9E2CC] bg-white p-3 lg:flex-row lg:items-end lg:justify-between">
                <label className="grid min-w-0 flex-1 gap-2 text-sm font-semibold text-[#2E201C]">
                  <span>工具数据集名称</span>
                  <input
                    className="h-10 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-sm text-[#2E201C] outline-none transition placeholder:text-[#8EA17D] focus:border-[#4E7C45] focus:ring-4 focus:ring-[#E0E8D5]"
                    onChange={(event) => {
                      setDatasetName(event.target.value);
                      setSaveResult(null);
                      setToolReport(null);
                      setToolReportAsset(null);
                      setToolDrift(null);
                      setToolDriftEvent(null);
                      setDatasetError(null);
                    }}
                    value={datasetName}
                  />
                </label>
                <button
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#4E7C45] px-3 text-sm font-semibold text-white transition hover:bg-[#416B39] disabled:cursor-not-allowed disabled:bg-[#B8C9B0]"
                  disabled={saveLoading || datasetPreview.rows.length === 0}
                  onClick={() => void saveDatasetVersion()}
                  type="button"
                >
                  {saveLoading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
                  保存工具数据集
                </button>
              </div>
              {saveResult ? (
                <div className="rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] p-3">
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                    <Fact label="数据集" value={saveResult.dataset.name} />
                    <Fact label="类型" value={saveResult.dataset.datasetType} />
                    <Fact label="版本" value={`v${saveResult.version.versionNumber}`} />
                    <Fact label="保存行数" value={String(saveResult.version.rowCount)} />
                    <Fact label="完整度" value={`${saveResult.version.averageCompletenessPercent}%`} />
                  </div>
                  <div className="mt-3 grid gap-2 text-xs font-semibold text-[#536B40]">
                    <p className="break-all">数据集 ID: {saveResult.dataset.id}</p>
                    <p className="break-all">版本 ID: {saveResult.version.id}</p>
                    <p>下一步可到数据集资产台导出 CSV、JSON 或 JSONL，并接入工具雷达报告。</p>
                  </div>
                  {githubToolSchemaFacts(saveResult.version.exportPreview).length > 0 ? (
                    <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                      {githubToolSchemaFacts(saveResult.version.exportPreview).map((fact) => (
                        <Fact label={fact.label} value={fact.value} key={fact.label} />
                      ))}
                    </div>
                  ) : null}
                  <div className="mt-4 grid gap-3 rounded-xl border border-[#D9E2CC] bg-white p-3">
                    <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <p className="text-sm font-semibold text-[#2E201C]">工具雷达验收</p>
                        <p className="mt-1 text-xs leading-5 text-[#6A625D]">
                          基于已保存版本生成报告，或对同源 GitHub 任务做只读漂移检查。
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          className="inline-flex h-9 items-center justify-center gap-2 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-xs font-semibold text-[#4E7C45] hover:border-[#4E7C45] disabled:cursor-not-allowed disabled:text-[#96A48D]"
                          disabled={toolIntelLoading !== null}
                          onClick={() => void generateToolReport()}
                          type="button"
                        >
                          {toolIntelLoading === "report" ? <Loader2 className="animate-spin" size={14} aria-hidden="true" /> : <ClipboardList size={14} aria-hidden="true" />}
                          生成雷达报告
                        </button>
                        <button
                          className="inline-flex h-9 items-center justify-center gap-2 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-xs font-semibold text-[#4E7C45] hover:border-[#4E7C45] disabled:cursor-not-allowed disabled:text-[#96A48D]"
                          disabled={toolIntelLoading !== null || !toolReport}
                          onClick={() => void saveToolReportAsset()}
                          type="button"
                        >
                          {toolIntelLoading === "asset" ? <Loader2 className="animate-spin" size={14} aria-hidden="true" /> : <ClipboardList size={14} aria-hidden="true" />}
                          保存到报告中心
                        </button>
                        <button
                          className="inline-flex h-9 items-center justify-center gap-2 rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 text-xs font-semibold text-[#4E7C45] hover:border-[#4E7C45] disabled:cursor-not-allowed disabled:text-[#96A48D]"
                          disabled={toolIntelLoading !== null || taskIds.length === 0}
                          onClick={() => void checkToolDrift()}
                          type="button"
                        >
                          {toolIntelLoading === "drift" ? <Loader2 className="animate-spin" size={14} aria-hidden="true" /> : <AlertTriangle size={14} aria-hidden="true" />}
                          检查工具漂移
                        </button>
                        <button
                          className="inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-[#2E201C] px-3 text-xs font-semibold text-white hover:bg-[#46332C] disabled:cursor-not-allowed disabled:bg-[#B8C9B0]"
                          disabled={toolIntelLoading !== null || !toolDrift}
                          onClick={() => void saveToolDriftSnapshot()}
                          type="button"
                        >
                          {toolIntelLoading === "snapshot" ? <Loader2 className="animate-spin" size={14} aria-hidden="true" /> : <Database size={14} aria-hidden="true" />}
                          保存漂移快照
                        </button>
                      </div>
                    </div>
                    {toolIntelError ? (
                      <p className="rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
                        {toolIntelError}
                      </p>
                    ) : null}
                    {toolReport ? (
                      <div className="grid gap-3">
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                          <Fact label="仓库数" value={String(toolReport.summary.repositoryCount)} />
                          <Fact label="Stars 合计" value={String(toolReport.summary.totalStars)} />
                          <Fact label="高价值仓库" value={String(toolReport.summary.highValueRepositories)} />
                          <Fact label="License 已声明" value={String(toolReport.summary.licensedRepositories)} />
                          <Fact label="Release 已识别" value={String(toolReport.summary.releaseTaggedRepositories)} />
                          <Fact label="README 已识别" value={String(toolReport.summary.readmeDocumentedRepositories)} />
                          <Fact label="Issue 活跃" value={String(toolReport.summary.issueActiveRepositories)} />
                          <Fact label="Fresh commit" value={String(toolReport.summary.freshCommitRepositories)} />
                        </div>
                        <div className="grid gap-2">
                          {toolReport.topRepositories.slice(0, 3).map((repository) => (
                            <a
                              className="flex flex-col gap-1 rounded-xl border border-[#E0E8D5] bg-[#FAFCF7] p-3 text-sm text-[#2E201C] hover:border-[#4E7C45]"
                              href={repository.htmlUrl ?? "#"}
                              key={repository.repoFullName}
                              rel="noreferrer"
                              target="_blank"
                            >
                              <span className="font-semibold">{repository.repoFullName}</span>
                              <span className="text-xs text-[#6A625D]">
                                {repository.stars} stars · {repository.language ?? "unknown"} · {repository.licenseSpdxId ?? "no license"} · {repository.latestReleaseTag ?? repository.defaultBranch ?? "no release"} · {repository.issueActivityOpenCount ?? repository.openIssues ?? "-"} issues · {repository.commitFreshnessStatus ?? "unknown freshness"} · 维护风险 {repository.maintenanceRisk}
                              </span>
                            </a>
                          ))}
                        </div>
                        {toolReport.riskSections.length > 0 ? (
                          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                            {toolReport.riskSections.map((section) => (
                              <div
                                className="rounded-xl border border-[#D9E2CC] bg-white p-3"
                                key={section.title}
                              >
                                <p className="text-xs font-semibold text-[#B47767]">{section.title}</p>
                                <p className="mt-2 text-xs leading-5 text-[#536B40]">
                                  {section.items.slice(0, 4).join("、") || "无"}
                                </p>
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <div className="grid gap-2 text-xs leading-5 text-[#536B40]">
                          {toolReport.recommendations.slice(0, 3).map((recommendation) => (
                            <p className="rounded-xl bg-[#ECF7EA] px-3 py-2" key={recommendation}>
                              {recommendation}
                            </p>
                          ))}
                        </div>
                        {toolReportAsset ? (
                          <div className="rounded-xl border border-[#D7E8D7] bg-[#F3FBF3] p-3 text-sm text-[#2F6B3A]">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                              <div>
                                <p className="font-semibold">已保存到报告中心</p>
                                <p className="mt-1 break-all text-xs leading-5 text-[#4F7F56]">
                                  {toolReportAsset.report.title} · {toolReportAsset.report.id}
                                </p>
                              </div>
                              <a
                                className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-full border border-[#B9D9B8] bg-white px-3 text-xs font-semibold text-[#2F6B3A] hover:border-[#4F7F56]"
                                href={`/reports/${toolReportAsset.report.id}`}
                              >
                                <ExternalLink size={13} aria-hidden="true" />
                                打开报告
                              </a>
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    {toolDrift ? (
                      <div className="grid gap-3">
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                          <Fact label="检查任务" value={String(toolDrift.summary.checkedTasks)} />
                          <Fact label="关键漂移" value={String(toolDrift.summary.criticalTasks)} />
                          <Fact label="字段缺失" value={String(toolDrift.summary.missingFieldTasks)} />
                          <Fact label="状态" value={toolDrift.summary.criticalTasks > 0 ? "critical" : "ok"} />
                        </div>
                        {Object.keys(toolDrift.summary.driftLayers).length > 0 ? (
                          <p className="rounded-xl border border-[#E0E8D5] bg-white px-3 py-2 text-xs font-semibold text-[#536B40]">
                            分层漂移：{Object.entries(toolDrift.summary.driftLayers).map(([layer, count]) => `${layer}=${count}`).join("、")}
                          </p>
                        ) : null}
                        <div className="grid gap-2">
                          {toolDrift.items.map((item) => (
                            <div className="rounded-xl border border-[#E0E8D5] bg-[#FAFCF7] p-3 text-sm" key={item.taskId}>
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-semibold text-[#2E201C]">{item.taskName ?? item.taskId}</span>
                                <span className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-[#4E7C45]">{item.status}</span>
                              </div>
                              <p className="mt-2 text-xs leading-5 text-[#6A625D]">
                                基准 {item.datasetVersionCompletenessPercent}% · 最新 {item.latestCompletenessPercent ?? "-"}% · 下降 {item.completenessDropPercent ?? "-"}%
                              </p>
                              {item.newMissingFields.length > 0 ? (
                                <p className="mt-1 text-xs font-semibold text-[#B85F4F]">
                                  缺失字段：{item.newMissingFields.map((field) => fieldLabels[field] ?? field).join("、")}
                                </p>
                              ) : null}
                              {formatSignalGroupEntries(item.signalGroups).length > 0 ? (
                                <div className="mt-3 grid gap-2">
                                  {formatSignalGroupEntries(item.signalGroups).map((group) => (
                                    <p
                                      className="rounded-xl border border-[#E0E8D5] bg-white px-3 py-2 text-xs leading-5 text-[#536B40]"
                                      key={group.label}
                                    >
                                      <span className="font-semibold text-[#B47767]">{group.label}</span>
                                      {" · "}
                                      {group.value}
                                    </p>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {toolDriftEvent ? (
                      <p className="rounded-xl border border-[#D7E8D7] bg-[#F3FBF3] px-3 py-2 text-sm font-semibold text-[#2F6B3A]">
                        已保存漂移快照：{toolDriftEvent.status} · {toolDriftEvent.id}
                      </p>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </Panel>
      </div>
    </section>
  );
}

function StructurePreflightResult({
  authorized,
  browserActionPlan,
  browserPlanSaveLoading,
  browserPlanSaveMessage,
  genericWebRun,
  loading,
  onBrowserActionPlanChange,
  onBrowserDiagnosticChange,
  onCreateGenericWebSource,
  onSaveBrowserAutomationPlan,
  report,
  selectedProjectId,
}: {
  authorized: boolean;
  browserActionPlan: BrowserDiagnosticActionPlan | null;
  browserPlanSaveLoading: boolean;
  browserPlanSaveMessage: string | null;
  genericWebRun: GenericWebRunState | null;
  loading: boolean;
  onBrowserActionPlanChange: (actionPlan: BrowserDiagnosticActionPlan | null) => void;
  onBrowserDiagnosticChange: (diagnostic: BrowserStructureDiagnostic | null) => void;
  onCreateGenericWebSource: () => void;
  onSaveBrowserAutomationPlan: (
    actionPlan: BrowserDiagnosticActionPlan,
    diagnostic: BrowserStructureDiagnostic,
  ) => Promise<void> | void;
  report: ToolkitPreflightReport;
  selectedProjectId: string;
}) {
  const gate = report.authorizationGate;
  const strategy = report.collectionStrategy;
  const canCreateSource =
    gate.allowedToContinue &&
    selectedProjectId.length > 0 &&
    (!browserActionPlan || browserActionPlan.canCreateGenericWebSource);
  const draftFields = [
    { label: "页面标题", value: report.dom.title ?? "未识别", source: "html_title" },
    { label: "规范 URL", value: report.dom.canonicalUrl ?? report.finalUrl, source: "canonical_or_final_url" },
    { label: "页面描述", value: report.dom.description ?? "未识别", source: "meta_description" },
    {
      label: "标题层级",
      value: report.dom.headings.length > 0 ? report.dom.headings.join(" / ") : "未识别",
      source: "dom_h1_h2_h3",
    },
    { label: "同源链接", value: `${report.network.sameOriginLinks} 个`, source: "dom_links" },
    { label: "正文样本", value: report.dom.textSample || "未识别", source: "visible_text" },
  ];

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
      <div className="grid min-w-0 gap-5">
        <Panel icon={Activity} label="Structure Preflight" title="公开网页结构预检结果">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Fact label="最终 URL" value={report.finalUrl} />
            <Fact label="HTTP 状态" value={String(report.network.finalStatusCode)} />
            <Fact label="风险级别" value={formatRisk(gate.riskLevel)} />
            <Fact label="推荐路径" value={formatRecommendedPath(strategy.recommendedPath)} />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Fact label="robots" value={formatResourceAvailability(report.robots.available)} />
            <Fact label="sitemap" value={formatResourceAvailability(report.sitemap.available)} />
            <Fact label="字段稳定性" value={formatFieldStability(strategy.fieldStability)} />
            <Fact label="适配度" value={`${formatStrategyFit(strategy.fit)} · ${strategy.confidence}%`} />
          </div>
          <div
            className={cn(
              "mt-4 rounded-xl border p-3 text-sm",
              gate.allowedToContinue
                ? "border-[#D7E8D7] bg-[#F3FBF3] text-[#2F6B3A]"
                : "border-[#F0C8C0] bg-[#FFF2EF] text-[#B85F4F]",
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <p className="font-semibold">
                {gate.allowedToContinue ? "可进入下一步采集验证" : "需要人工复核后再继续"}
              </p>
              <RiskBadge risk={gate.riskLevel} />
            </div>
            <ul className="mt-2 grid gap-1 text-xs leading-5">
              {(gate.blockedReasons.length > 0 ? gate.blockedReasons : gate.requiredNextActions).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </Panel>

        <Panel icon={ClipboardList} label="Field Contract Draft" title="字段契约草稿">
          <div className="grid gap-3 md:grid-cols-2">
            {draftFields.map((field) => (
              <article
                className="min-w-0 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3"
                key={field.label}
              >
                <p className="text-sm font-semibold text-[#2E201C]">{field.label}</p>
                <p className="mt-2 max-h-28 overflow-auto break-words rounded-lg bg-white px-3 py-2 text-sm leading-5 text-[#5F5757]">
                  {field.value}
                </p>
                <p className="mt-2 text-xs font-semibold uppercase text-[#B47767]">{field.source}</p>
              </article>
            ))}
          </div>
        </Panel>
      </div>

      <aside className="grid min-w-0 gap-5">
        <Panel icon={ShieldCheck} label="Collection Strategy" title="采集路径建议">
          <div className="grid gap-3">
            <div className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="break-words text-sm font-semibold text-[#2E201C]">
                    {strategy.label}
                  </p>
                  <p className="mt-1 text-xs font-semibold uppercase text-[#B47767]">
                    {formatRecommendedPath(strategy.recommendedPath)} · {formatStrategyFit(strategy.fit)}
                  </p>
                </div>
                <span className="w-fit rounded-full bg-[#FFF0EA] px-2.5 py-1 text-xs font-semibold text-[#9E5C4D]">
                  {strategy.confidence}%
                </span>
              </div>
              <div className="mt-3 grid gap-2 text-xs leading-5 text-[#7A625A]">
                {strategy.reasons.slice(0, 3).map((reason) => (
                  <p className="rounded-lg bg-white px-3 py-2" key={reason}>
                    {reason}
                  </p>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-[#F0E1D9] bg-white p-3">
              <p className="text-xs font-semibold uppercase text-[#B47767]">下一步</p>
              <ul className="mt-2 grid gap-2 text-sm leading-5 text-[#5F5757]">
                {strategy.nextSteps.slice(0, 4).map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-[#F0E1D9] bg-white p-3">
              <p className="text-xs font-semibold uppercase text-[#B47767]">清洗建议</p>
              <ul className="mt-2 grid gap-2 text-sm leading-5 text-[#5F5757]">
                {strategy.cleaningNotes.slice(0, 3).map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          </div>
        </Panel>

        <Panel icon={Database} label="generic_web" title="采集源运行入口">
          <div className="grid gap-3">
            <p className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2 text-sm leading-6 text-[#7A625A]">
              预检通过后，可以把最终 URL 创建为 generic_web 采集源并执行一次公开页面采集。该步骤会写入采集源、任务和运行记录。
            </p>
            <button
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.18)] transition hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:bg-[#D8C8C0]"
              disabled={loading || !canCreateSource}
              onClick={onCreateGenericWebSource}
              type="button"
            >
              {loading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Database size={16} aria-hidden="true" />}
              创建并运行 generic_web
            </button>
            {!gate.allowedToContinue ? (
              <p className="text-xs leading-5 text-[#B85F4F]">当前预检存在阻断项，必须先完成人工复核。</p>
            ) : null}
            {!selectedProjectId ? (
              <p className="text-xs leading-5 text-[#B85F4F]">请选择写入项目。</p>
            ) : null}
            {browserActionPlan ? (
              <p
                className={cn(
                  "rounded-xl border px-3 py-2 text-xs leading-5",
                  browserActionPlan.canCreateGenericWebSource
                    ? "border-[#D7E8D7] bg-[#F3FBF3] text-[#2F6B3A]"
                    : "border-[#F1D9A8] bg-[#FFF9E9] text-[#87611B]",
                )}
              >
                浏览器诊断判断：
                {browserActionPlan.canCreateGenericWebSource
                  ? "可使用 generic_web 草稿创建采集源。"
                  : browserActionPlan.blockingReasons[0] ?? "需要复核推荐工具后再创建。"}
              </p>
            ) : (
              <p className="text-xs leading-5 text-[#87611B]">
                未导入浏览器诊断时只按静态预检创建；建议先导入 browser-harness 证据。
              </p>
            )}
          </div>
        </Panel>

        <BrowserDiagnosticImportPanel
          browserAutomationPlanSaveDisabledReason={
            !selectedProjectId
              ? "请选择写入项目。"
              : !authorized
                ? "请先确认授权边界。"
                : null
          }
          browserAutomationPlanSaveMessage={browserPlanSaveMessage}
          browserAutomationPlanSaving={browserPlanSaveLoading}
          compact
          onActionPlanChange={onBrowserActionPlanChange}
          onDiagnosticChange={onBrowserDiagnosticChange}
          onSaveBrowserAutomationPlan={onSaveBrowserAutomationPlan}
          preflightReport={report}
          title="浏览器诊断对照"
        />

        <Panel icon={ShieldCheck} label="Recommendations" title="后续建议">
          <div className="grid gap-2">
            {report.recommendations.slice(0, 6).map((item) => (
              <p
                className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2 text-sm leading-5 text-[#7A625A]"
                key={item}
              >
                {item}
              </p>
            ))}
          </div>
        </Panel>

        {genericWebRun ? (
          <Panel icon={CheckCircle2} label="Run Result" title="公开网页采集结果">
            <div className="grid gap-3">
              <Fact label="采集源" value={genericWebRun.source.name} />
              <Fact label="Collector" value={genericWebRun.task.collectorType} />
              <Fact label="任务状态" value={formatTaskRunStatus(genericWebRun.run?.status ?? genericWebRun.task.status)} />
              <Fact label="本次记录" value={String(genericWebRun.run?.recordsCount ?? 0)} />
              <a
                className="inline-flex h-9 items-center justify-center gap-2 rounded-full border border-[#D7E8D7] bg-[#F3FBF3] px-3 text-xs font-semibold text-[#2F6B3A] hover:border-[#4F7F56]"
                href="/tasks"
              >
                <ExternalLink size={13} aria-hidden="true" />
                查看任务页
              </a>
            </div>
          </Panel>
        ) : null}
      </aside>
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
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Fact label="Sitemap URL" value={String(discovery.pageStructure.sitemapUrlCount)} />
              <Fact label="分页 URL" value={String(discovery.pageStructure.paginationUrlCount)} />
              <Fact label="重复 URL" value={String(discovery.pageStructure.duplicateUrlCount)} />
              <Fact label="跳过 URL" value={String(discovery.pageStructure.skippedUrlCount)} />
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
              <Fact label="输入 URL" value={String(discovery.discoveryPlan.dedupeSummary.inputUrlCount)} />
              <Fact
                label="规范候选"
                value={String(discovery.discoveryPlan.dedupeSummary.canonicalCandidateCount)}
              />
              <Fact label="去重 URL" value={String(discovery.discoveryPlan.dedupeSummary.duplicateUrlCount)} />
              <Fact label="跳过 URL" value={String(discovery.discoveryPlan.dedupeSummary.skippedUrlCount)} />
            </div>
            {discovery.discoveryPlan.dedupeSummary.skippedReasons.length > 0 ? (
              <div className="mt-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
                <p className="text-xs font-semibold uppercase text-[#B47767]">跳过原因</p>
                <p className="mt-2 break-words text-sm leading-6 text-[#7A625A]">
                  {discovery.discoveryPlan.dedupeSummary.skippedReasons.join(" · ")}
                </p>
              </div>
            ) : null}
            {discovery.discoveryPlan.paginationUrls.length > 0 ? (
              <div className="mt-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
                <p className="text-xs font-semibold uppercase text-[#B47767]">分页 URL</p>
                <p className="mt-2 break-all text-sm leading-6 text-[#7A625A]">
                  {discovery.discoveryPlan.paginationUrls.slice(0, 3).join(" · ")}
                </p>
              </div>
            ) : null}
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
                  <p className="text-xs font-semibold uppercase text-[#4E7C45]">调度变更 Gate</p>
                  <h3 className="mt-1 text-sm font-semibold text-[#2E201C]">质量通过后审批自动保鲜</h3>
                  <p className="mt-1 text-xs leading-5 text-[#5F5757]">
                    只写入任务调度配置；审批动作不启动采集运行，也不触发 scheduler tick。
                  </p>
                </div>
                <span className="rounded-full bg-[#ECF7EA] px-3 py-1 text-xs font-semibold text-[#4E7C45]">
                  {taskIds.length} 个任务
                </span>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <span className="rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 py-2 text-xs font-semibold text-[#536B40]">
                  写入：任务调度配置
                </span>
                <span className="rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 py-2 text-xs font-semibold text-[#536B40]">
                  run_started=false
                </span>
                <span className="rounded-xl border border-[#D9E2CC] bg-[#FAFCF7] px-3 py-2 text-xs font-semibold text-[#536B40]">
                  scheduler_tick_started=false
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

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item)).filter(Boolean);
}

function githubToolSchemaFacts(exportPreview: Record<string, unknown>) {
  const schema = asRecord(exportPreview.schema);
  if (!schema) {
    return [];
  }
  const provenance = asRecord(schema.provenance);
  const lineage = stringArray(provenance?.lineage_fields);
  const collectorVersions = asRecord(schema.collector_versions);
  const collectorSchemaVersions = stringArray(schema.collector_schema_versions);
  return [
    { label: "Schema", value: formatDatasetValue(schema.schema_version) },
    { label: "主键", value: formatDatasetValue(schema.primary_key) },
    {
      label: "Collector",
      value: collectorVersions
        ? Object.entries(collectorVersions)
            .map(([key, value]) => `${key}:${String(value)}`)
            .join(" / ")
        : collectorSchemaVersions.join(" / ") || "—",
    },
    { label: "Lineage", value: lineage.join(" / ") || "—" },
  ].filter((item) => item.value !== "—");
}

function formatSignalGroupEntries(groups: Record<string, string[]>) {
  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([group, items]) => ({
      label: signalGroupLabels[group] ?? group,
      value: items.slice(0, 3).join(" / "),
    }));
}

function EmptyAnalysisState({ mode }: { mode: AutomationMode }) {
  const title =
    mode === "product_discovery"
      ? "等待商品 URL 发现"
      : mode === "github_topic_radar"
        ? "等待 GitHub 主题雷达运行"
        : mode === "structure_preflight"
          ? "等待结构预检"
          : "等待 URL 分析";
  const body =
    mode === "product_discovery"
      ? "从集合页、分类页或 sitemap 中提取候选商品 URL，确认后再进入商品详情页字段采集。"
      : mode === "github_topic_radar"
        ? "从公开 GitHub topic 创建 API-first 采集源，运行后会生成仓库工具情报记录。"
      : mode === "structure_preflight"
        ? "先确认公开授权，再检查 HTTP、robots、sitemap、DOM、链接和表单，判断是否可以进入 generic_web 或浏览器采集。"
        : "商品页分析会明确字段能否结构化保存，以及是否需要浏览器运行时复核。";
  return <WorkbenchEmptyState icon={Link2} text={body} title={title} />;
}

type WorkflowLaneId = "intake" | "review" | "persist" | "monitor" | "diagnostics";

function activeWorkflowLane(
  mode: AutomationMode,
  state: {
    analysis: AutomationSiteAnalysis | null;
    discovery: AutomationProductDiscovery | null;
    githubRun: GitHubTopicRunState | null;
    preflightReport: ToolkitPreflightReport | null;
  },
): WorkflowLaneId {
  if (mode === "structure_preflight" && state.preflightReport) {
    return "diagnostics";
  }
  if (mode === "github_topic_radar" && state.githubRun) {
    return "monitor";
  }
  if (mode === "product_discovery" && state.discovery) {
    return "persist";
  }
  if (mode === "product_page" && state.analysis) {
    return "review";
  }
  return "intake";
}

function workflowResultLabel(mode: AutomationMode) {
  if (mode === "github_topic_radar") {
    return "03-04 持久化 / 监控";
  }
  if (mode === "product_discovery") {
    return "02-03 复核 / 持久化";
  }
  if (mode === "structure_preflight") {
    return "02-03 复核 / 持久化";
  }
  return "02 复核";
}

function workflowResultTitle(mode: AutomationMode) {
  if (mode === "github_topic_radar") {
    return "工具情报持久化与监控";
  }
  if (mode === "product_discovery") {
    return "候选商品复核与批量持久化";
  }
  if (mode === "structure_preflight") {
    return "结构预检结果与采集入口";
  }
  return "字段候选与采集源草稿";
}

function workflowResultDescription(mode: AutomationMode) {
  if (mode === "github_topic_radar") {
    return "展示 GitHub API-first 采集结果、工具数据集、报告资产和漂移监控动作。";
  }
  if (mode === "product_discovery") {
    return "从候选 URL 到采集源预览、小批量运行、数据集保存和漂移检查保持一条连续证据链。";
  }
  if (mode === "structure_preflight") {
    return "先用公开页面预检判断后续路径；创建 generic_web 采集源仍需显式授权动作。";
  }
  return "复核字段、工具建议、清洗草稿和可入库采集源草稿。";
}

function workflowResultIcon(mode: AutomationMode) {
  if (mode === "github_topic_radar") {
    return Activity;
  }
  if (mode === "product_discovery") {
    return Link2;
  }
  if (mode === "structure_preflight") {
    return ShieldCheck;
  }
  return ClipboardList;
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

function formatCapabilityStatus(value: string) {
  const labels: Record<string, string> = {
    available: "可用",
    blocked: "阻断",
    manual_review: "需人工复核",
    missing_tool: "缺少工具",
    not_configured: "未配置",
    requires_login: "需登录态",
    requires_proxy: "需代理",
    unknown: "未知",
  };
  return labels[value] ?? value;
}

function capabilityStatusClass(value: string) {
  if (value === "available") {
    return "border-[#D7E8D7] bg-[#F3FBF3] text-[#2F6B3A]";
  }
  if (value === "blocked" || value === "missing_tool") {
    return "border-[#F0C8C0] bg-[#FFF2EF] text-[#B85F4F]";
  }
  return "border-[#E8D4CB] bg-[#FFF8F4] text-[#7D4F43]";
}

function formatCapabilityBoundary(value: AutomationCapabilityProbe["executionBoundary"]) {
  const labels: Record<AutomationCapabilityProbe["executionBoundary"], string> = {
    blocked: "阻断",
    executable: "可执行",
    import_only: "仅导入",
    read_only_probe: "只读探测",
    sop_only: "仅 SOP",
  };
  return labels[value];
}

function formatCapabilityOutput(value: string) {
  const labels: Record<string, string> = {
    BrowserDiagnosticJobRun: "浏览器诊断结果",
    DatasetVersion: "数据集版本",
    ExternalToolSnapshot: "外部工具快照",
    RawRecord: "原始采集记录",
    Report: "报告资产",
    Source: "采集源",
    TaskRun: "采集运行",
  };
  return labels[value] ?? value;
}

function formatCredentialMode(value: AutomationCapabilityProbe["credentialMode"]) {
  const labels: Record<AutomationCapabilityProbe["credentialMode"], string> = {
    browser_profile: "浏览器 profile",
    cookie: "Cookie",
    manual_export: "人工导出",
    none: "无",
    token: "Token",
    unknown: "未知",
  };
  return labels[value];
}

function formatExecutionBoundary(value: AutomationPlatformPackage["executionBoundary"]) {
  const labels: Record<AutomationPlatformPackage["executionBoundary"], string> = {
    blocked: "阻断",
    executable: "可执行",
    sop_import_only: "仅导入 SOP",
  };
  return labels[value];
}

function formatAuthorizationRequired(value: boolean) {
  return value ? "需授权" : "无需额外授权";
}

function formatPackageLifecycleStatus(value: AutomationPlatformPackage["lifecycleStatus"]) {
  const labels: Record<AutomationPlatformPackage["lifecycleStatus"], string> = {
    active: "Active",
    beta: "Beta",
    deprecated: "Deprecated",
    draft: "Draft",
    import_only: "Import only",
    sop_only: "SOP only",
  };
  return labels[value];
}

function formatAcceptanceStatus(
  value: AutomationPlatformPackage["acceptanceRegistry"][number]["status"],
) {
  const labels: Record<
    AutomationPlatformPackage["acceptanceRegistry"][number]["status"],
    string
  > = {
    blocked: "Blocked",
    done_scoped_l4: "Scoped L4",
    local_done: "Local done",
    local_external_done: "Local external",
    manual_review: "Manual review",
    retained_l4: "Retained L4",
    todo: "Todo",
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

function formatResourceAvailability(value: boolean) {
  return value ? "可读取" : "需复核";
}

function formatRecommendedPath(value: ToolkitPreflightReport["collectionStrategy"]["recommendedPath"]) {
  const labels: Record<ToolkitPreflightReport["collectionStrategy"]["recommendedPath"], string> = {
    blocked_review: "阻断复核",
    browser_automation: "浏览器自动化",
    generic_web: "静态页面采集",
    manual_review: "人工复核",
    official_api_or_file: "API/文件导入",
  };
  return labels[value];
}

function formatStrategyFit(value: ToolkitPreflightReport["collectionStrategy"]["fit"]) {
  const labels: Record<ToolkitPreflightReport["collectionStrategy"]["fit"], string> = {
    blocked: "阻断",
    high: "高适配",
    low: "低适配",
    medium: "中适配",
  };
  return labels[value];
}

function formatFieldStability(value: ToolkitPreflightReport["collectionStrategy"]["fieldStability"]) {
  const labels: Record<ToolkitPreflightReport["collectionStrategy"]["fieldStability"], string> = {
    high: "高",
    low: "低",
    medium: "中",
  };
  return labels[value];
}

function serializeBrowserDiagnosticPayload(
  diagnostic: BrowserStructureDiagnostic,
): Record<string, unknown> {
  return {
    schema_version: diagnostic.schemaVersion,
    generated_at: diagnostic.generatedAt,
    requested_url: diagnostic.requestedUrl,
    final_url: diagnostic.finalUrl,
    run_policy: {
      authorization_confirmed: diagnostic.runPolicy.authorizationConfirmed,
      execution_mode: diagnostic.runPolicy.executionMode,
      production_write: diagnostic.runPolicy.productionWrite,
      login_or_private_page_allowed: diagnostic.runPolicy.loginOrPrivatePageAllowed,
      cookies_exported: diagnostic.runPolicy.cookiesExported,
      note: diagnostic.runPolicy.note,
    },
    visible_text: {
      length: diagnostic.visibleText.length,
      line_count: diagnostic.visibleText.lineCount,
      sample: diagnostic.visibleText.sample,
    },
    dom_counters: {
      links: diagnostic.domCounters.links,
      same_origin_links: diagnostic.domCounters.sameOriginLinks,
      external_links: diagnostic.domCounters.externalLinks,
      forms: diagnostic.domCounters.forms,
      inputs: diagnostic.domCounters.inputs,
      buttons: diagnostic.domCounters.buttons,
      tables: diagnostic.domCounters.tables,
      lists: diagnostic.domCounters.lists,
      articles: diagnostic.domCounters.articles,
      cards: diagnostic.domCounters.cards,
      images: diagnostic.domCounters.images,
      scripts: diagnostic.domCounters.scripts,
      stylesheets: diagnostic.domCounters.stylesheets,
      json_ld_blocks: diagnostic.domCounters.jsonLdBlocks,
    },
    risk_flags: diagnostic.riskFlags,
    extraction_strategy: {
      recommended_path: diagnostic.extractionStrategy.recommendedPath,
      fit: diagnostic.extractionStrategy.fit,
      confidence: diagnostic.extractionStrategy.confidence,
      field_stability: diagnostic.extractionStrategy.fieldStability,
      reasons: diagnostic.extractionStrategy.reasons,
      next_steps: diagnostic.extractionStrategy.nextSteps,
      cleaning_notes: diagnostic.extractionStrategy.cleaningNotes,
    },
    network_summary: {
      resource_count: diagnostic.networkSummary.resourceCount,
      same_origin_resources: diagnostic.networkSummary.sameOriginResources,
      cross_origin_resources: diagnostic.networkSummary.crossOriginResources,
      xhr_fetch_count: diagnostic.networkSummary.xhrFetchCount,
      script_count: diagnostic.networkSummary.scriptCount,
      image_count: diagnostic.networkSummary.imageCount,
      api_candidate_count: diagnostic.networkSummary.apiCandidateCount,
      api_candidates: diagnostic.networkSummary.apiCandidates.map((candidate) => ({
        url: candidate.url,
        initiator_type: candidate.initiatorType,
        same_origin: candidate.sameOrigin,
        duration_ms: candidate.durationMs,
        transfer_size: candidate.transferSize,
      })),
      initiator_type_counts: diagnostic.networkSummary.initiatorTypeCounts,
    },
    evidence: {
      screenshot_path: diagnostic.evidence.screenshotPath,
      source: diagnostic.evidence.source,
      errors: diagnostic.evidence.errors,
    },
  };
}

function hostLabelFromUrl(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.hostname || value;
  } catch {
    return value;
  }
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

function readRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function readArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function formatSpecDryRunStatus(value: AutomationBrowserExecutableSpecDryRun["summary"]["status"]) {
  const labels: Record<AutomationBrowserExecutableSpecDryRun["summary"]["status"], string> = {
    blocked: "阻断",
    ready: "可进入下一步",
    review: "需复核",
  };
  return labels[value];
}

function formatSpecCheckStatus(value: "passed" | "review" | "blocked") {
  const labels: Record<"passed" | "review" | "blocked", string> = {
    blocked: "阻断",
    passed: "通过",
    review: "复核",
  };
  return labels[value];
}

function formatBrowserJobStatus(value: string) {
  const labels: Record<string, string> = {
    blocked: "已阻断",
    cancelled: "已取消",
    queued: "已排队",
    ready_for_manual_execution: "已审核，等待人工执行",
  };
  return labels[value] ?? value;
}

function formatBrowserLocalRunStatus(value: string) {
  const labels: Record<string, string> = {
    blocked: "已阻断",
    blocked_ephemeral_probe: "浏览器探测被阻断",
    completed_ephemeral_probe: "浏览器探测完成",
    completed_snapshot_replay: "快照回放完成",
    failed: "未完成",
    failed_ephemeral_probe: "浏览器探测失败",
  };
  return labels[value] ?? value;
}

function formatBrowserLocalSelectorStatus(value: string) {
  const labels: Record<string, string> = {
    not_observed_in_diagnostic_snapshot: "诊断快照未识别",
    observed_from_diagnostic_snapshot: "已从诊断快照识别",
  };
  return labels[value] ?? value;
}

function formatBrowserJobReason(value: string) {
  const labels: Record<string, string> = {
    browser_diagnostic_job_cancelled_before_runner_start: "任务已取消，未启动浏览器运行。",
    browser_diagnostic_job_created_no_runner: "任务已创建为只读资产，执行器尚未接入。",
    browser_harness_binary_unavailable: "browser-harness CLI 不可用。",
    browser_harness_ephemeral_probe_only: "本机探测仅读取临时 tab 页面元信息。",
    browser_harness_probe_failed: "browser-harness 探测未完成。",
    browser_automation_runtime_not_registered:
      "浏览器自动化运行时尚未注册为正式采集器。",
    browser_evidence_boundary_clean: "证据边界干净，未写文件或采集资源。",
    browser_evidence_boundary_has_side_effect: "证据资产出现写入痕迹，需停止晋级。",
    browser_local_runner_snapshot_replay_only: "本地 runner 仅回放已保存诊断快照。",
    browser_promotion_no_write_confirmed: "已确认本次只是预检，不执行写入。",
    browser_runtime_strategy_manual_review_required:
      "运行时策略仍需人工复核后才能进入写入链路。",
    collector_config_dry_run_valid: "采集配置预检通过。",
    collector_config_invalid: "采集配置预检未通过。",
    collector_not_registered: "目标采集器未注册。",
    execution_dry_run_no_write: "当前只是执行前预检，没有写入。",
    generic_web_may_not_reproduce_browser_runtime:
      "Generic Web 采集器可能无法复现浏览器运行态字段。",
    manual_review_required: "需要人工确认目标类型、字段和保留策略。",
    m2_read_only_contract_no_direct_promotion:
      "当前阶段仅沉淀只读证据，不能直接创建采集资源。",
    no_files_written_no_collection_resources_created: "未写文件，未创建采集资源。",
    no_real_browser_started_no_files_written_no_collection_resources_created:
      "未启动真实浏览器，未写文件，未创建采集资源。",
    no_source_task_taskrun_dataset_notification_or_scheduler_side_effect:
      "未创建采集源、任务、运行、数据集、通知或调度。",
    preview_only_no_source_task_write: "当前仅生成候选包，没有写入采集资源。",
    product_page_collector_static_runtime_only:
      "商品页采集器为静态运行时，需复核动态字段可复现性。",
    required_selectors_observed: "必需字段已观测到。",
    required_selector_missing: "必需 selector 仍有缺失，需复核后再进入后续链路。",
    separate_write_authorization_required: "正式写入需要单独授权。",
  };
  return labels[value] ?? value;
}

function formatBrowserPromotionCheckStatus(value: string) {
  const labels: Record<string, string> = {
    blocked: "阻断",
    passed: "通过",
    review: "复核",
  };
  return labels[value] ?? value;
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
