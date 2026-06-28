import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import type {
  ToolkitAuthorizationChecklist,
  ToolkitBrowserLab,
  ToolkitImageAnchorDiagnostic,
  ToolkitIntelligence,
  ToolkitLecturePlaybook,
  ToolkitLearningPath,
  ToolkitMethodCardDraft,
  ToolkitMethodCardDraftStatus,
  ToolkitMethod,
  ToolkitMetrics,
  ToolkitOverview,
  ToolkitPreflightReport,
  ToolkitTool,
} from "@/types/toolkit";

type ToolkitOverviewResponse = {
  dataset: string;
  generated_at: string | null;
  metrics: ToolkitMetricsResponse;
  learning_paths: ToolkitLearningPathResponse[];
  lecture_playbooks: ToolkitLecturePlaybookResponse[];
  image_anchor_diagnostics: ToolkitImageAnchorDiagnosticResponse[];
  browser_labs: ToolkitBrowserLabResponse[];
  authorization_checklists: ToolkitAuthorizationChecklistResponse[];
  tools: ToolkitToolResponse[];
  methods: ToolkitMethodResponse[];
  intelligence_items: ToolkitIntelligenceResponse[];
};

type ToolkitMetricsResponse = {
  source_count: number;
  tool_count: number;
  method_count: number;
  intelligence_count: number;
  evidence_count: number;
  last_collected_at: string | null;
};

type ToolkitToolResponse = {
  id: string;
  name: string;
  category: string;
  risk_level: string;
  collector_type: string;
  source_title: string;
  source_url: string | null;
  description: string | null;
  language: string | null;
  license: string | null;
  stars: number | null;
  forks: number | null;
  open_issues: number | null;
  updated_at: string | null;
  collected_at: string;
  source_credibility_score: number;
  source_credibility_level: string;
  source_credibility_factors: string[];
};

type ToolkitMethodResponse = {
  id: string;
  title: string;
  category: string;
  risk_level: string;
  collector_type: string;
  source_url: string | null;
  platform: string | null;
  recommended_collector: string | null;
  data_types: string[];
  boundary: string | null;
  training_takeaway: string | null;
  collected_at: string;
};

type ToolkitIntelligenceResponse = {
  id: string;
  title: string;
  summary: string;
  domain: string;
  intelligence_type: string;
  final_score: number;
  evidence_count: number;
  updated_at: string;
};

type ToolkitLearningPathResponse = {
  id: string;
  title: string;
  stage: string;
  focus: string;
  risk_level: string;
  tool_count: number;
  method_count: number;
  intelligence_count: number;
  evidence_count: number;
  tools: string[];
  methods: string[];
  acceptance_criteria: string[];
  source_urls: string[];
};

type ToolkitLecturePlaybookResponse = {
  id: string;
  intelligence_id: string;
  title: string;
  audience: string;
  level: string;
  duration_minutes: number;
  claim: string;
  teaching_sequence: string[];
  hands_on_steps: string[];
  verification_steps: string[];
  risk_boundaries: string[];
  classroom_exercise: string;
  evidence_urls: string[];
  evidence_count: number;
  final_score: number;
};

type ToolkitImageAnchorDiagnosticResponse = {
  id: string;
  image_label: string;
  extracted_claim: string;
  source_title: string;
  source_url: string;
  source_type: string;
  classification: string;
  risk_level: string;
  value_judgement: string;
  collection_use: string;
  training_takeaway: string;
  related_tools: string[];
  evidence_urls: string[];
};

type ToolkitBrowserLabResponse = {
  id: string;
  title: string;
  focus: string;
  risk_level: string;
  inspection_targets: string[];
  playwright_checks: string[];
  evidence_outputs: string[];
  training_task: string;
  acceptance_criteria: string[];
};

type ToolkitAuthorizationChecklistResponse = {
  id: string;
  title: string;
  risk_level: string;
  required_checks: string[];
  blocked_conditions: string[];
  evidence_required: string[];
  approval_rule: string;
};

type ToolkitPreflightHttpResourceResponse = {
  url: string;
  status_code: number | null;
  content_type: string | null;
  content_length: number | null;
  available: boolean;
  summary: string;
};

type ToolkitPreflightRedirectResponse = {
  url: string;
  status_code: number;
  location: string | null;
};

type ToolkitPreflightDomResponse = {
  title: string | null;
  description: string | null;
  canonical_url: string | null;
  meta_robots: string | null;
  headings: string[];
  link_count: number;
  script_count: number;
  stylesheet_count: number;
  image_count: number;
  form_count: number;
  text_sample: string;
};

type ToolkitPreflightNetworkResponse = {
  request_method: string;
  final_status_code: number;
  final_content_type: string | null;
  redirect_count: number;
  same_origin_links: number;
  external_links: number;
  script_count: number;
  stylesheet_count: number;
  image_count: number;
  form_count: number;
};

type ToolkitPreflightAuthorizationGateResponse = {
  allowed_to_continue: boolean;
  risk_level: string;
  blocked_reasons: string[];
  required_next_actions: string[];
};

type ToolkitPreflightCollectionStrategyResponse = {
  recommended_path:
    | "generic_web"
    | "browser_automation"
    | "official_api_or_file"
    | "manual_review"
    | "blocked_review";
  label: string;
  fit: "high" | "medium" | "low" | "blocked";
  confidence: number;
  field_stability: "high" | "medium" | "low";
  reasons: string[];
  next_steps: string[];
  cleaning_notes: string[];
};

type ToolkitPreflightReportResponse = {
  requested_url: string;
  final_url: string;
  checked_at: string;
  authorization_confirmed: boolean;
  headers: Record<string, string>;
  redirects: ToolkitPreflightRedirectResponse[];
  robots: ToolkitPreflightHttpResourceResponse;
  sitemap: ToolkitPreflightHttpResourceResponse;
  security_txt: ToolkitPreflightHttpResourceResponse;
  dom: ToolkitPreflightDomResponse;
  network: ToolkitPreflightNetworkResponse;
  authorization_gate: ToolkitPreflightAuthorizationGateResponse;
  collection_strategy: ToolkitPreflightCollectionStrategyResponse;
  recommendations: string[];
};

type ToolkitMethodCardDraftResponse = {
  id: string;
  title: string;
  method_id: string;
  source_url: string;
  status: ToolkitMethodCardDraftStatus;
  manual_confirm_state: ToolkitMethodCardDraftStatus;
  risk_level: string;
  recommended_collector: string;
  data_types: string[];
  boundary: string;
  training_takeaway: string;
  review_note: string | null;
  created_at: string;
  last_saved_at: string;
};

type ToolkitMethodCardDraftListResponse = {
  drafts: ToolkitMethodCardDraftResponse[];
};

export async function getToolkitOverview(): Promise<ToolkitOverview> {
  if (mockApiEnabled) {
    return getMockToolkitOverview();
  }
  const response = await apiFetch<ToolkitOverviewResponse>("/api/toolkit");
  return {
    dataset: response.dataset,
    generatedAt: response.generated_at,
    metrics: mapMetrics(response.metrics),
    learningPaths: response.learning_paths.map(mapLearningPath),
    lecturePlaybooks: response.lecture_playbooks.map(mapLecturePlaybook),
    imageAnchorDiagnostics: response.image_anchor_diagnostics.map(
      mapImageAnchorDiagnostic,
    ),
    browserLabs: response.browser_labs.map(mapBrowserLab),
    authorizationChecklists: response.authorization_checklists.map(
      mapAuthorizationChecklist,
    ),
    tools: response.tools.map(mapTool),
    methods: response.methods.map(mapMethod),
    intelligenceItems: response.intelligence_items.map(mapIntelligence),
  };
}

export async function runToolkitPreflight(
  url: string,
  authorized: boolean,
): Promise<ToolkitPreflightReport> {
  if (mockApiEnabled) {
    return getMockToolkitPreflightReport(url, authorized);
  }
  const response = await apiFetch<ToolkitPreflightReportResponse>("/api/toolkit/preflight", {
    method: "POST",
    body: JSON.stringify({ url, authorized }),
  });
  return mapPreflightReport(response);
}

export async function getToolkitMethodCardDrafts(): Promise<ToolkitMethodCardDraft[]> {
  if (mockApiEnabled) {
    return [];
  }
  const response = await apiFetch<ToolkitMethodCardDraftListResponse>(
    "/api/toolkit/method-card-drafts",
  );
  return response.drafts.map(mapMethodCardDraft);
}

export async function saveToolkitMethodCardDraft(
  report: ToolkitPreflightReport,
  status: ToolkitMethodCardDraftStatus,
  reviewNote: string,
): Promise<ToolkitMethodCardDraft> {
  if (mockApiEnabled) {
    return {
      id: "mock-method-card-draft",
      title: report.collectionStrategy.label,
      methodId: report.collectionStrategy.recommendedPath,
      sourceUrl: report.finalUrl,
      status,
      manualConfirmState: status,
      riskLevel: report.authorizationGate.riskLevel,
      recommendedCollector: report.collectionStrategy.recommendedPath,
      dataTypes: ["public_page", "dom", "network_summary"],
      boundary: report.authorizationGate.allowedToContinue
        ? "仅用于 mock 模式下的公开页面预检演示。"
        : "授权确认未完成，保留为复核草稿。",
      trainingTakeaway: "先确认授权边界，再选择采集路径和字段契约。",
      reviewNote: reviewNote.trim() || null,
      createdAt: "2026-06-25T00:00:00Z",
      lastSavedAt: "2026-06-25T00:00:00Z",
    };
  }
  const response = await apiFetch<ToolkitMethodCardDraftResponse>(
    "/api/toolkit/method-card-drafts",
    {
      method: "POST",
      body: JSON.stringify({
        preflight_report: toPreflightReportRequest(report),
        status,
        review_note: reviewNote.trim() || null,
      }),
    },
  );
  return mapMethodCardDraft(response);
}

function mapMetrics(response: ToolkitMetricsResponse): ToolkitMetrics {
  return {
    sourceCount: response.source_count,
    toolCount: response.tool_count,
    methodCount: response.method_count,
    intelligenceCount: response.intelligence_count,
    evidenceCount: response.evidence_count,
    lastCollectedAt: response.last_collected_at,
  };
}

function mapTool(response: ToolkitToolResponse): ToolkitTool {
  return {
    id: response.id,
    name: response.name,
    category: response.category,
    riskLevel: response.risk_level,
    collectorType: response.collector_type,
    sourceTitle: response.source_title,
    sourceUrl: response.source_url,
    description: response.description,
    language: response.language,
    license: response.license,
    stars: response.stars,
    forks: response.forks,
    openIssues: response.open_issues,
    updatedAt: response.updated_at,
    collectedAt: response.collected_at,
    sourceCredibilityScore: response.source_credibility_score,
    sourceCredibilityLevel: response.source_credibility_level,
    sourceCredibilityFactors: response.source_credibility_factors,
  };
}

function mapMethod(response: ToolkitMethodResponse): ToolkitMethod {
  return {
    id: response.id,
    title: response.title,
    category: response.category,
    riskLevel: response.risk_level,
    collectorType: response.collector_type,
    sourceUrl: response.source_url,
    platform: response.platform,
    recommendedCollector: response.recommended_collector,
    dataTypes: response.data_types,
    boundary: response.boundary,
    trainingTakeaway: response.training_takeaway,
    collectedAt: response.collected_at,
  };
}

function mapIntelligence(response: ToolkitIntelligenceResponse): ToolkitIntelligence {
  return {
    id: response.id,
    title: response.title,
    summary: response.summary,
    domain: response.domain,
    intelligenceType: response.intelligence_type,
    finalScore: response.final_score,
    evidenceCount: response.evidence_count,
    updatedAt: response.updated_at,
  };
}

function mapLearningPath(response: ToolkitLearningPathResponse): ToolkitLearningPath {
  return {
    id: response.id,
    title: response.title,
    stage: response.stage,
    focus: response.focus,
    riskLevel: response.risk_level,
    toolCount: response.tool_count,
    methodCount: response.method_count,
    intelligenceCount: response.intelligence_count,
    evidenceCount: response.evidence_count,
    tools: response.tools,
    methods: response.methods,
    acceptanceCriteria: response.acceptance_criteria,
    sourceUrls: response.source_urls,
  };
}

function mapLecturePlaybook(
  response: ToolkitLecturePlaybookResponse,
): ToolkitLecturePlaybook {
  return {
    id: response.id,
    intelligenceId: response.intelligence_id,
    title: response.title,
    audience: response.audience,
    level: response.level,
    durationMinutes: response.duration_minutes,
    claim: response.claim,
    teachingSequence: response.teaching_sequence,
    handsOnSteps: response.hands_on_steps,
    verificationSteps: response.verification_steps,
    riskBoundaries: response.risk_boundaries,
    classroomExercise: response.classroom_exercise,
    evidenceUrls: response.evidence_urls,
    evidenceCount: response.evidence_count,
    finalScore: response.final_score,
  };
}

function mapImageAnchorDiagnostic(
  response: ToolkitImageAnchorDiagnosticResponse,
): ToolkitImageAnchorDiagnostic {
  return {
    id: response.id,
    imageLabel: response.image_label,
    extractedClaim: response.extracted_claim,
    sourceTitle: response.source_title,
    sourceUrl: response.source_url,
    sourceType: response.source_type,
    classification: response.classification,
    riskLevel: response.risk_level,
    valueJudgement: response.value_judgement,
    collectionUse: response.collection_use,
    trainingTakeaway: response.training_takeaway,
    relatedTools: response.related_tools,
    evidenceUrls: response.evidence_urls,
  };
}

function mapBrowserLab(response: ToolkitBrowserLabResponse): ToolkitBrowserLab {
  return {
    id: response.id,
    title: response.title,
    focus: response.focus,
    riskLevel: response.risk_level,
    inspectionTargets: response.inspection_targets,
    playwrightChecks: response.playwright_checks,
    evidenceOutputs: response.evidence_outputs,
    trainingTask: response.training_task,
    acceptanceCriteria: response.acceptance_criteria,
  };
}

function mapAuthorizationChecklist(
  response: ToolkitAuthorizationChecklistResponse,
): ToolkitAuthorizationChecklist {
  return {
    id: response.id,
    title: response.title,
    riskLevel: response.risk_level,
    requiredChecks: response.required_checks,
    blockedConditions: response.blocked_conditions,
    evidenceRequired: response.evidence_required,
    approvalRule: response.approval_rule,
  };
}

function mapPreflightReport(
  response: ToolkitPreflightReportResponse,
): ToolkitPreflightReport {
  return {
    requestedUrl: response.requested_url,
    finalUrl: response.final_url,
    checkedAt: response.checked_at,
    authorizationConfirmed: response.authorization_confirmed,
    headers: response.headers,
    redirects: response.redirects.map((redirect) => ({
      url: redirect.url,
      statusCode: redirect.status_code,
      location: redirect.location,
    })),
    robots: mapPreflightHttpResource(response.robots),
    sitemap: mapPreflightHttpResource(response.sitemap),
    securityTxt: mapPreflightHttpResource(response.security_txt),
    dom: {
      title: response.dom.title,
      description: response.dom.description,
      canonicalUrl: response.dom.canonical_url,
      metaRobots: response.dom.meta_robots,
      headings: response.dom.headings,
      linkCount: response.dom.link_count,
      scriptCount: response.dom.script_count,
      stylesheetCount: response.dom.stylesheet_count,
      imageCount: response.dom.image_count,
      formCount: response.dom.form_count,
      textSample: response.dom.text_sample,
    },
    network: {
      requestMethod: response.network.request_method,
      finalStatusCode: response.network.final_status_code,
      finalContentType: response.network.final_content_type,
      redirectCount: response.network.redirect_count,
      sameOriginLinks: response.network.same_origin_links,
      externalLinks: response.network.external_links,
      scriptCount: response.network.script_count,
      stylesheetCount: response.network.stylesheet_count,
      imageCount: response.network.image_count,
      formCount: response.network.form_count,
    },
    authorizationGate: {
      allowedToContinue: response.authorization_gate.allowed_to_continue,
      riskLevel: response.authorization_gate.risk_level,
      blockedReasons: response.authorization_gate.blocked_reasons,
      requiredNextActions: response.authorization_gate.required_next_actions,
    },
    collectionStrategy: {
      recommendedPath: response.collection_strategy.recommended_path,
      label: response.collection_strategy.label,
      fit: response.collection_strategy.fit,
      confidence: response.collection_strategy.confidence,
      fieldStability: response.collection_strategy.field_stability,
      reasons: response.collection_strategy.reasons,
      nextSteps: response.collection_strategy.next_steps,
      cleaningNotes: response.collection_strategy.cleaning_notes,
    },
    recommendations: response.recommendations,
  };
}

function mapMethodCardDraft(
  response: ToolkitMethodCardDraftResponse,
): ToolkitMethodCardDraft {
  return {
    id: response.id,
    title: response.title,
    methodId: response.method_id,
    sourceUrl: response.source_url,
    status: response.status,
    manualConfirmState: response.manual_confirm_state,
    riskLevel: response.risk_level,
    recommendedCollector: response.recommended_collector,
    dataTypes: response.data_types,
    boundary: response.boundary,
    trainingTakeaway: response.training_takeaway,
    reviewNote: response.review_note,
    createdAt: response.created_at,
    lastSavedAt: response.last_saved_at,
  };
}

function mapPreflightHttpResource(
  response: ToolkitPreflightHttpResourceResponse,
) {
  return {
    url: response.url,
    statusCode: response.status_code,
    contentType: response.content_type,
    contentLength: response.content_length,
    available: response.available,
    summary: response.summary,
  };
}

function getMockToolkitOverview(): ToolkitOverview {
  return {
    dataset: "mock-toolkit-overview",
    generatedAt: "2026-06-25T00:00:00Z",
    metrics: {
      sourceCount: 6,
      toolCount: 4,
      methodCount: 4,
      intelligenceCount: 3,
      evidenceCount: 12,
      lastCollectedAt: "2026-06-25T00:00:00Z",
    },
    learningPaths: [
      {
        id: "mock-public-collection-path",
        title: "公开来源采集工作流",
        stage: "operator",
        focus: "授权预检、字段契约、结构化保存和漂移监控",
        riskLevel: "low",
        toolCount: 4,
        methodCount: 4,
        intelligenceCount: 3,
        evidenceCount: 12,
        tools: ["browser-harness", "Playwright", "GitHub API", "RSS/Atom"],
        methods: ["公开页面预检", "GitHub API-first", "RSS/Atom 更新", "浏览器诊断资产"],
        acceptanceCriteria: [
          "目标来源通过授权边界确认",
          "字段候选和清洗规则可复核",
          "保存后的数据集版本带有来源和质量指标",
        ],
        sourceUrls: ["https://example.com"],
      },
    ],
    lecturePlaybooks: [
      {
        id: "mock-collection-operator-brief",
        intelligenceId: "mock-public-collection-intel",
        title: "公开来源采集操作说明",
        audience: "采集运营和数据产品负责人",
        level: "starter",
        durationMinutes: 30,
        claim: "先做授权和结构预检，再进入字段选择、保存和监控。",
        teachingSequence: ["确认目标", "运行预检", "选择字段", "保存数据集", "观察漂移"],
        handsOnSteps: ["输入公开 URL", "查看 robots/DOM/network 摘要", "生成采集计划"],
        verificationSteps: ["检查授权状态", "检查字段完整率", "检查漂移事件"],
        riskBoundaries: ["不复用登录态", "不绕过验证码", "不采集授权范围外页面"],
        classroomExercise: "使用 example.com 完成一次 mock 预检。",
        evidenceUrls: ["https://example.com"],
        evidenceCount: 3,
        finalScore: 82,
      },
    ],
    imageAnchorDiagnostics: [
      {
        id: "mock-image-anchor",
        imageLabel: "公开页面截图证据",
        extractedClaim: "截图只能证明页面结构样例，不能代表生产写入已发生。",
        sourceTitle: "Mock public page",
        sourceUrl: "https://example.com",
        sourceType: "public_page",
        classification: "evidence_boundary",
        riskLevel: "low",
        valueJudgement: "适合作为结构诊断证据。",
        collectionUse: "辅助字段候选复核。",
        trainingTakeaway: "截图证据要和数据写入证据分开记录。",
        relatedTools: ["Playwright"],
        evidenceUrls: ["https://example.com"],
      },
    ],
    browserLabs: [
      {
        id: "mock-browser-lab",
        title: "浏览器证据适配器诊断",
        focus: "只读页面结构、选择器和网络摘要",
        riskLevel: "medium",
        inspectionTargets: ["DOM 标题", "链接数量", "表单数量"],
        playwrightChecks: ["页面可打开", "主要选择器可定位"],
        evidenceOutputs: ["截图摘要", "选择器预览", "网络摘要"],
        trainingTask: "使用隔离浏览器完成公开页面只读诊断。",
        acceptanceCriteria: ["browserStarted 记录清楚", "filesWritten 状态清楚"],
      },
    ],
    authorizationChecklists: [
      {
        id: "mock-public-url-checklist",
        title: "公开 URL 授权检查",
        riskLevel: "medium",
        requiredChecks: ["确认页面公开可访问", "确认不需要账号登录", "确认不访问个人数据"],
        blockedConditions: ["验证码绕过", "私网页面", "支付或个人消息页面"],
        evidenceRequired: ["目标 URL", "预检摘要", "操作者确认"],
        approvalRule: "未确认授权时只允许保存草稿。",
      },
    ],
    tools: [
      {
        id: "mock-browser-harness",
        name: "browser-harness",
        category: "browser_automation",
        riskLevel: "medium",
        collectorType: "browser_automation",
        sourceTitle: "Browser Harness",
        sourceUrl: null,
        description: "隔离浏览器只读诊断适配器。",
        language: "TypeScript",
        license: "MIT",
        stars: null,
        forks: null,
        openIssues: null,
        updatedAt: null,
        collectedAt: "2026-06-25T00:00:00Z",
        sourceCredibilityScore: 80,
        sourceCredibilityLevel: "high",
        sourceCredibilityFactors: ["local_smoke", "read_only_boundary"],
      },
      {
        id: "mock-github-api",
        name: "GitHub API",
        category: "official_api",
        riskLevel: "low",
        collectorType: "github_topic",
        sourceTitle: "GitHub REST API",
        sourceUrl: "https://docs.github.com/rest",
        description: "优先用于公开仓库元数据采集。",
        language: null,
        license: null,
        stars: null,
        forks: null,
        openIssues: null,
        updatedAt: null,
        collectedAt: "2026-06-25T00:00:00Z",
        sourceCredibilityScore: 90,
        sourceCredibilityLevel: "high",
        sourceCredibilityFactors: ["official_api", "structured_response"],
      },
    ],
    methods: [
      {
        id: "mock-generic-web-method",
        title: "公开页面结构预检",
        category: "platform_method",
        riskLevel: "low",
        collectorType: "toolkit_preflight",
        sourceUrl: "https://example.com",
        platform: "Public Web",
        recommendedCollector: "generic_web",
        dataTypes: ["title", "description", "headings", "links"],
        boundary: "只读取公开页面结构，不访问登录态或私有页面。",
        trainingTakeaway: "先跑预检，再决定字段和采集路径。",
        collectedAt: "2026-06-25T00:00:00Z",
      },
      {
        id: "mock-github-topic-method",
        title: "GitHub 主题雷达",
        category: "platform_method",
        riskLevel: "low",
        collectorType: "github_topic",
        sourceUrl: "https://docs.github.com/rest/search/search",
        platform: "GitHub",
        recommendedCollector: "github_topic",
        dataTypes: ["stars", "forks", "license", "release", "freshness"],
        boundary: "遵守 API 频控，只采集公开仓库元数据。",
        trainingTakeaway: "API-first 路径优先于浏览器 DOM 抓取。",
        collectedAt: "2026-06-25T00:00:00Z",
      },
    ],
    intelligenceItems: [
      {
        id: "mock-public-collection-intel",
        title: "公开来源采集路径优先级",
        summary: "官方 API 或 RSS 可用时优先使用结构化入口；浏览器诊断用于补充页面结构证据。",
        domain: "platform",
        intelligenceType: "collection_method",
        finalScore: 82,
        evidenceCount: 3,
        updatedAt: "2026-06-25T00:00:00Z",
      },
    ],
  };
}

function getMockToolkitPreflightReport(
  url: string,
  authorized: boolean,
): ToolkitPreflightReport {
  const normalizedUrl = normalizeMockUrl(url);
  return {
    requestedUrl: url,
    finalUrl: normalizedUrl,
    checkedAt: "2026-06-25T00:00:00Z",
    authorizationConfirmed: authorized,
    headers: {
      "content-type": "text/html; charset=utf-8",
    },
    redirects: [],
    robots: {
      url: `${new URL(normalizedUrl).origin}/robots.txt`,
      statusCode: 200,
      contentType: "text/plain",
      contentLength: 128,
      available: true,
      summary: "mock 模式下的 robots 摘要。",
    },
    sitemap: {
      url: `${new URL(normalizedUrl).origin}/sitemap.xml`,
      statusCode: 200,
      contentType: "application/xml",
      contentLength: 512,
      available: true,
      summary: "mock 模式下的 sitemap 摘要。",
    },
    securityTxt: {
      url: `${new URL(normalizedUrl).origin}/.well-known/security.txt`,
      statusCode: null,
      contentType: null,
      contentLength: null,
      available: false,
      summary: "mock 模式未发现 security.txt。",
    },
    dom: {
      title: "Mock public page",
      description: "本地 mock 模式公开页面预检样例。",
      canonicalUrl: normalizedUrl,
      metaRobots: "index,follow",
      headings: ["Mock public page", "Collection evidence"],
      linkCount: 12,
      scriptCount: 2,
      stylesheetCount: 1,
      imageCount: 3,
      formCount: 0,
      textSample: "Mock content for local design and workflow verification.",
    },
    network: {
      requestMethod: "GET",
      finalStatusCode: 200,
      finalContentType: "text/html; charset=utf-8",
      redirectCount: 0,
      sameOriginLinks: 10,
      externalLinks: 2,
      scriptCount: 2,
      stylesheetCount: 1,
      imageCount: 3,
      formCount: 0,
    },
    authorizationGate: {
      allowedToContinue: authorized,
      riskLevel: authorized ? "low" : "medium",
      blockedReasons: authorized ? [] : ["authorization_not_confirmed"],
      requiredNextActions: authorized
        ? ["复核字段候选", "选择采集路径"]
        : ["确认目标 URL 授权边界"],
    },
    collectionStrategy: {
      recommendedPath: authorized ? "generic_web" : "manual_review",
      label: authorized ? "公开页面结构预检" : "授权复核后继续",
      fit: authorized ? "medium" : "blocked",
      confidence: authorized ? 0.72 : 0.32,
      fieldStability: "medium",
      reasons: ["mock 模式下使用本地预检样例，未访问远端 API。"],
      nextSteps: authorized
        ? ["保存方法卡草稿", "进入字段候选复核"]
        : ["先补充授权依据"],
      cleaningNotes: ["去除空白", "保留 canonical URL", "记录内容哈希"],
    },
    recommendations: ["mock 模式只用于本地 UI 和流程检查。"],
  };
}

function normalizeMockUrl(url: string): string {
  try {
    return new URL(url).toString();
  } catch {
    return "https://example.com/";
  }
}

function toPreflightReportRequest(
  report: ToolkitPreflightReport,
): ToolkitPreflightReportResponse {
  return {
    requested_url: report.requestedUrl,
    final_url: report.finalUrl,
    checked_at: report.checkedAt,
    authorization_confirmed: report.authorizationConfirmed,
    headers: report.headers,
    redirects: report.redirects.map((redirect) => ({
      url: redirect.url,
      status_code: redirect.statusCode,
      location: redirect.location,
    })),
    robots: toPreflightHttpResourceRequest(report.robots),
    sitemap: toPreflightHttpResourceRequest(report.sitemap),
    security_txt: toPreflightHttpResourceRequest(report.securityTxt),
    dom: {
      title: report.dom.title,
      description: report.dom.description,
      canonical_url: report.dom.canonicalUrl,
      meta_robots: report.dom.metaRobots,
      headings: report.dom.headings,
      link_count: report.dom.linkCount,
      script_count: report.dom.scriptCount,
      stylesheet_count: report.dom.stylesheetCount,
      image_count: report.dom.imageCount,
      form_count: report.dom.formCount,
      text_sample: report.dom.textSample,
    },
    network: {
      request_method: report.network.requestMethod,
      final_status_code: report.network.finalStatusCode,
      final_content_type: report.network.finalContentType,
      redirect_count: report.network.redirectCount,
      same_origin_links: report.network.sameOriginLinks,
      external_links: report.network.externalLinks,
      script_count: report.network.scriptCount,
      stylesheet_count: report.network.stylesheetCount,
      image_count: report.network.imageCount,
      form_count: report.network.formCount,
    },
    authorization_gate: {
      allowed_to_continue: report.authorizationGate.allowedToContinue,
      risk_level: report.authorizationGate.riskLevel,
      blocked_reasons: report.authorizationGate.blockedReasons,
      required_next_actions: report.authorizationGate.requiredNextActions,
    },
    collection_strategy: {
      recommended_path: report.collectionStrategy.recommendedPath,
      label: report.collectionStrategy.label,
      fit: report.collectionStrategy.fit,
      confidence: report.collectionStrategy.confidence,
      field_stability: report.collectionStrategy.fieldStability,
      reasons: report.collectionStrategy.reasons,
      next_steps: report.collectionStrategy.nextSteps,
      cleaning_notes: report.collectionStrategy.cleaningNotes,
    },
    recommendations: report.recommendations,
  };
}

function toPreflightHttpResourceRequest(
  resource: ToolkitPreflightReport["robots"],
): ToolkitPreflightHttpResourceResponse {
  return {
    url: resource.url,
    status_code: resource.statusCode,
    content_type: resource.contentType,
    content_length: resource.contentLength,
    available: resource.available,
    summary: resource.summary,
  };
}
