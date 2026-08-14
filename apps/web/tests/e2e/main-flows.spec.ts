import {
  type APIRequestContext,
  type APIResponse,
  type Locator,
  type Page,
  expect,
  test,
} from "@playwright/test";

const realApiMode = process.env.PLAYWRIGHT_REAL_API === "true";
const browserDiagnosticFixtureJson = JSON.stringify({
  schema_version: "browser_structure_diagnostic.v1",
  generated_at: "2026-06-19T14:00:00Z",
  requested_url: "https://example.com",
  final_url: "https://example.com/",
  run_policy: {
    authorization_confirmed: true,
    execution_mode: "browser_harness_real_chrome_read_only",
    production_write: false,
    login_or_private_page_allowed: false,
    cookies_exported: false,
  },
  visible_text: {
    length: 180,
    line_count: 4,
    sample: "Example Domain",
  },
  dom_counters: {
    links: 1,
    same_origin_links: 0,
    external_links: 1,
    forms: 0,
    inputs: 0,
    buttons: 0,
    tables: 0,
    lists: 0,
    articles: 0,
    cards: 0,
    images: 0,
    scripts: 0,
    stylesheets: 0,
    json_ld_blocks: 0,
  },
  risk_flags: [],
  extraction_strategy: {
    recommended_path: "generic_web",
    fit: "high",
    confidence: 84,
    field_stability: "high",
    reasons: ["浏览器渲染后正文、链接和标题可直接读取。"],
    next_steps: ["建立 DOM 字段契约。"],
    cleaning_notes: ["清洗标题和链接。"],
  },
  network_summary: {
    resource_count: 0,
    same_origin_resources: 0,
    cross_origin_resources: 0,
    xhr_fetch_count: 0,
    script_count: 0,
    image_count: 0,
    api_candidate_count: 0,
    api_candidates: [],
    initiator_type_counts: {},
  },
  evidence: {
    screenshot_path: "tmp/outputs/browser-diagnostics/example.png",
    source: "browser-harness",
    errors: [],
  },
});

const browserAutomationDiagnosticFixtureJson = JSON.stringify({
  schema_version: "browser_structure_diagnostic.v1",
  generated_at: "2026-06-19T14:10:00Z",
  requested_url: "https://example.com/app",
  final_url: "https://example.com/app",
  run_policy: {
    authorization_confirmed: true,
    execution_mode: "browser_harness_real_chrome_read_only",
    production_write: false,
    login_or_private_page_allowed: false,
    cookies_exported: false,
  },
  visible_text: {
    length: 680,
    line_count: 18,
    sample: "Dynamic Product Grid",
  },
  dom_counters: {
    links: 18,
    same_origin_links: 12,
    external_links: 6,
    forms: 0,
    inputs: 2,
    buttons: 9,
    tables: 0,
    lists: 2,
    articles: 0,
    cards: 16,
    images: 16,
    scripts: 24,
    stylesheets: 4,
    json_ld_blocks: 0,
  },
  risk_flags: ["dynamic_rendering"],
  extraction_strategy: {
    recommended_path: "browser_automation",
    fit: "medium",
    confidence: 72,
    field_stability: "medium",
    reasons: ["页面依赖浏览器渲染和异步接口，静态 HTML 不足以稳定抽取字段。"],
    next_steps: ["使用 browser-harness 生成只读动作轨迹。"],
    cleaning_notes: ["对卡片文本和 API 候选 URL 做结构化清洗。"],
  },
  network_summary: {
    resource_count: 38,
    same_origin_resources: 30,
    cross_origin_resources: 8,
    xhr_fetch_count: 6,
    script_count: 24,
    image_count: 16,
    api_candidate_count: 1,
    api_candidates: [
      {
        url: "https://example.com/api/products",
        initiator_type: "fetch",
        same_origin: true,
        duration_ms: 124,
        transfer_size: 4096,
      },
    ],
    initiator_type_counts: { fetch: 6, script: 24 },
  },
  evidence: {
    screenshot_path: "tmp/outputs/browser-diagnostics/example-app.png",
    source: "browser-harness",
    errors: [],
  },
});

type RealApiCredentials = {
  email: string;
  password: string;
};

let generatedRealApiCredentials: RealApiCredentials | null = null;
const cleanupCompatibleE2eEmail = /^e2e-[^@]+@example\.com$/;

function realApiBaseUrl() {
  return process.env.PLAYWRIGHT_BASE_URL ?? "https://scrapy.lute-tlz-dddd.top";
}

function assertCleanupCompatibleE2eEmail(email: string, source: string) {
  if (!cleanupCompatibleE2eEmail.test(email)) {
    throw new Error(
      `${source} must be a cleanup-compatible one-time E2E email matching e2e-*@example.com`,
    );
  }
}

function generatedCredentials(): RealApiCredentials {
  if (generatedRealApiCredentials) {
    return generatedRealApiCredentials;
  }
  const stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  generatedRealApiCredentials = {
    email: `e2e-real-api-${stamp}@example.com`,
    password: `E2ePass-${stamp}`,
  };
  assertCleanupCompatibleE2eEmail(generatedRealApiCredentials.email, "Generated credentials");
  return generatedRealApiCredentials;
}

function configuredCredentials(): RealApiCredentials | null {
  const email = process.env.SCRAPY_DEMO_EMAIL;
  const password = process.env.SCRAPY_DEMO_PASSWORD;
  if (!email && !password) {
    return null;
  }
  if (!email || !password) {
    throw new Error(
      "SCRAPY_DEMO_EMAIL and SCRAPY_DEMO_PASSWORD must be set together for real API E2E.",
    );
  }
  assertCleanupCompatibleE2eEmail(email, "SCRAPY_DEMO_EMAIL");
  return { email, password };
}

async function authenticateRealApiRequest(request: APIRequestContext) {
  const baseUrl = realApiBaseUrl();
  const configured = configuredCredentials();
  if (configured) {
    const response = await request.post(`${baseUrl}/api/auth/login`, {
      data: configured,
    });
    assertAuthResponse(response, "Real API login");
    return { baseUrl, cookieText: extractCookieText(response, "login") };
  }

  const credentials = generatedCredentials();
  const response = await request.post(`${baseUrl}/api/auth/register`, {
    data: {
      email: credentials.email,
      password: credentials.password,
      name: "Playwright Real API E2E",
    },
  });
  if (response.status() === 409) {
    const loginResponse = await request.post(`${baseUrl}/api/auth/login`, {
      data: credentials,
    });
    assertAuthResponse(loginResponse, "Generated Real API login");
    return { baseUrl, cookieText: extractCookieText(loginResponse, "login") };
  }
  assertAuthResponse(response, "Generated Real API register");
  return { baseUrl, cookieText: extractCookieText(response, "register") };
}

function assertAuthResponse(response: APIResponse, label: string) {
  if (!response.ok()) {
    throw new Error(`${label} failed (${response.status()})`);
  }
}

function extractCookieText(response: APIResponse, action: string) {
  const rawSetCookie = response.headers()["set-cookie"] as string | undefined;
  if (!rawSetCookie) {
    throw new Error(`Real API ${action} response did not return access token cookie`);
  }
  return rawSetCookie.split(";")[0];
}

async function loginByApi(page: Page, request: APIRequestContext) {
  if (!realApiMode) {
    return;
  }
  const { baseUrl, cookieText } = await authenticateRealApiRequest(request);
  const [name, ...valueParts] = cookieText.split("=");
  if (!name || valueParts.length === 0) {
    throw new Error("Real API login response set-cookie header format invalid");
  }
  await page.context().addCookies([
    {
      name,
      value: valueParts.join("="),
      url: baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`,
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
    },
  ]);
}

async function activateControl(locator: Locator, projectName: string) {
  if (projectName === "mobile") {
    await locator.focus();
    await locator.press("Enter");
    return;
  }
  await locator.click();
}

function visibleArticleByText(page: Page, text: string) {
  return page.locator("article").filter({ hasText: text }).filter({ visible: true }).first();
}

async function expectNoVisibleTechnicalNoise(page: Page) {
  for (const text of [
    "RawRecord",
    "Content Hash",
    "Reference Metadata",
    "RawRecord ID",
    "Rule Metadata",
    "Payload Audit",
    "manual-json payload",
    "source_competitor_homepage",
    "HTML snapshot retained",
    "Entity ID",
    "Signal ID",
    "AlertRule",
    "AlertEvent",
    "DriftEvent",
    "TaskRun",
    "DatasetVersion",
    "CleaningPlan",
    "Source/Task",
    "Latest Snapshot",
    "payload 审计",
  ]) {
    await expect(page.getByText(text)).toHaveCount(0);
  }
}

async function createAutomationDatasetAsset(page: Page, datasetName?: string) {
  await page.goto("/automation");
  await expect(
    page.getByRole("heading", { name: "URL 到结构化采集计划" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "采集入口与授权边界" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "能力评估与平台包选择" })).toBeVisible();
  await page.getByRole("button", { name: "商品发现" }).click();
  await page
    .getByLabel(
      "我确认目标为公开可访问页面或公开 API，采集分析不涉及登录态、验证码绕过或未授权数据访问。",
    )
    .check();
  await page.getByRole("button", { name: "发现商品 URL" }).click();
  await expect(
    page.getByRole("heading", { name: "候选商品 URL" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "生成采集源预览" }).click();
  await expect(
    page.getByRole("heading", { name: "子商品页采集源预览" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "确认创建采集源和任务" }).click();
  await expect(page.getByText("已创建或复用采集源")).toBeVisible();
  await page.getByRole("button", { name: "小批量运行" }).click();
  await expect(page.getByText("采集结果数据集预览")).toBeVisible();
  await expect(page.getByRole("button", { name: "标题" })).toBeVisible();
  await expect(page.getByRole("button", { name: "价格" })).toBeVisible();
  await expect(page.getByRole("button", { name: "SKU" })).toBeVisible();
  await expect(page.getByRole("button", { name: "规范 URL" })).toBeVisible();

  await page.getByRole("button", { name: "生成数据集预览" }).click();
  await expect(page.getByText("数据集名称")).toBeVisible();
  if (datasetName) {
    await page.getByLabel("数据集名称").fill(datasetName);
  }
  await page.getByRole("button", { name: "保存数据集版本" }).click();
  await expect(page.getByText("调度变更 Gate")).toBeVisible();
  await expect(page.getByText("scheduler_tick_started=false")).toBeVisible();
  await page.getByRole("button", { name: "审批调度" }).click();
  await expect(page.getByText("Drift Check")).toBeVisible();
  await page.getByRole("button", { name: "检查漂移" }).click();
  await expect(page.getByText("关键漂移", { exact: true })).toBeVisible();
  await expect(page.getByText("critical")).toBeVisible();
  await expect(
    page.getByText("漂移检查为只读评估，不会启动采集、创建告警或发送通知。"),
  ).toBeVisible();
  await page.getByRole("button", { name: "保存漂移快照" }).click();
  await expect(page.getByText("已保存漂移快照")).toBeVisible();
  await expect(page.getByText("漂移历史")).toBeVisible();
  await expect(page.getByText("ecommerce_product_drift").first()).toBeVisible();
}

async function createTaskFlowFixture(
  request: APIRequestContext,
  suffix: string,
) {
  if (!realApiMode) {
    return null;
  }
  const { baseUrl } = await authenticateRealApiRequest(request);
  const projectsResponse = await request.get(`${baseUrl}/api/projects`);
  if (!projectsResponse.ok()) {
    throw new Error(
      `Project fixture lookup failed: ${await projectsResponse.text()}`,
    );
  }
  const projects = (await projectsResponse.json()) as Array<{ id: string }>;
  if (projects.length === 0) {
    throw new Error("Task fixture requires at least one project");
  }
  const taskName = `Playwright Task Flow ${suffix} ${Date.now()}`;
  const taskExternalId = `playwright/task-flow-${suffix}-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
  const sourceResponse = await request.post(`${baseUrl}/api/sources`, {
    data: {
      project_id: projects[0].id,
      name: taskName,
      type: "manual_json",
      config: {
        entity_type: "github_repo",
        json_data: { full_name: taskExternalId, stars: 233 },
      },
      schedule_cron: null,
    },
  });
  if (!sourceResponse.ok()) {
    throw new Error(
      `Task fixture source create failed: ${await sourceResponse.text()}`,
    );
  }
  const source = (await sourceResponse.json()) as { id: string };
  const enableResponse = await request.post(
    `${baseUrl}/api/sources/${source.id}/enable`,
  );
  if (!enableResponse.ok()) {
    throw new Error(
      `Task fixture enable failed: ${await enableResponse.text()}`,
    );
  }
  return taskName;
}

async function createIntelligenceFixture(
  request: APIRequestContext,
  suffix: string,
) {
  if (!realApiMode) {
    return;
  }
  const { baseUrl } = await authenticateRealApiRequest(request);
  const projectsResponse = await request.get(`${baseUrl}/api/projects`);
  if (!projectsResponse.ok()) {
    throw new Error(
      `Project fixture lookup failed: ${await projectsResponse.text()}`,
    );
  }
  const projects = (await projectsResponse.json()) as Array<{ id: string }>;
  if (projects.length === 0) {
    throw new Error("Intelligence fixture requires at least one project");
  }
  const sourceName = `Playwright Intelligence ${suffix} ${Date.now()}`;
  const intelligenceExternalId = `playwright/intelligence-flow-${suffix}-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
  const sourceResponse = await request.post(`${baseUrl}/api/sources`, {
    data: {
      project_id: projects[0].id,
      name: sourceName,
      type: "manual_json",
      config: {
        entity_type: "github_repo",
        json_data: { full_name: intelligenceExternalId, stars: 100 },
      },
      schedule_cron: null,
    },
  });
  if (!sourceResponse.ok()) {
    throw new Error(
      `Intelligence fixture source create failed: ${await sourceResponse.text()}`,
    );
  }
  const source = (await sourceResponse.json()) as { id: string };
  const enableResponse = await request.post(
    `${baseUrl}/api/sources/${source.id}/enable`,
  );
  if (!enableResponse.ok()) {
    throw new Error(
      `Intelligence fixture enable failed: ${await enableResponse.text()}`,
    );
  }
  const task = (await enableResponse.json()) as { id: string };
  const firstRunResponse = await request.post(
    `${baseUrl}/api/tasks/${task.id}/run`,
  );
  if (!firstRunResponse.ok()) {
    throw new Error(
      `Intelligence fixture first run failed: ${await firstRunResponse.text()}`,
    );
  }
  const updateResponse = await request.patch(
    `${baseUrl}/api/sources/${source.id}`,
    {
      data: {
        config: {
          entity_type: "github_repo",
          json_data: { full_name: intelligenceExternalId, stars: 360 },
        },
      },
    },
  );
  if (!updateResponse.ok()) {
    throw new Error(
      `Intelligence fixture source update failed: ${await updateResponse.text()}`,
    );
  }
  const secondRunResponse = await request.post(
    `${baseUrl}/api/tasks/${task.id}/run`,
  );
  if (!secondRunResponse.ok()) {
    throw new Error(
      `Intelligence fixture second run failed: ${await secondRunResponse.text()}`,
    );
  }
}

async function createAlertEventFixture(request: APIRequestContext, suffix: string) {
  if (!realApiMode) {
    return;
  }
  const { baseUrl } = await authenticateRealApiRequest(request);
  const projectsResponse = await request.get(`${baseUrl}/api/projects`);
  if (!projectsResponse.ok()) {
    throw new Error(
      `Project fixture lookup failed: ${await projectsResponse.text()}`,
    );
  }
  const projects = (await projectsResponse.json()) as Array<{ id: string }>;
  if (projects.length === 0) {
    throw new Error("Alert event fixture requires at least one project");
  }
  const ruleName = `Playwright Alert Event ${suffix} ${Date.now()}`;
  const ruleResponse = await request.post(`${baseUrl}/api/alert-rules`, {
    data: {
      project_id: projects[0].id,
      name: ruleName,
      signal_type: "*",
      condition: { field: "severity", op: "in", value: ["high", "critical"] },
      channel: "in_app",
      enabled: true,
    },
  });
  if (!ruleResponse.ok()) {
    throw new Error(
      `Alert event fixture rule create failed: ${await ruleResponse.text()}`,
    );
  }
  await createIntelligenceFixture(request, `alert-event-${suffix}`);
}

async function createReportFixture(request: APIRequestContext, suffix: string) {
  if (!realApiMode) {
    return;
  }
  await createIntelligenceFixture(request, `report-${suffix}`);
  const { baseUrl } = await authenticateRealApiRequest(request);
  const projectsResponse = await request.get(`${baseUrl}/api/projects`);
  if (!projectsResponse.ok()) {
    throw new Error(
      `Project fixture lookup failed: ${await projectsResponse.text()}`,
    );
  }
  const projects = (await projectsResponse.json()) as Array<{ id: string }>;
  if (projects.length === 0) {
    throw new Error("Report fixture requires at least one project");
  }
  const reportResponse = await request.post(`${baseUrl}/api/reports/generate`, {
    data: { project_id: projects[0].id, report_type: "daily" },
  });
  if (!reportResponse.ok()) {
    throw new Error(
      `Report fixture create failed: ${await reportResponse.text()}`,
    );
  }
}

async function createNotificationFixture(request: APIRequestContext) {
  if (!realApiMode) {
    return;
  }
  const { baseUrl } = await authenticateRealApiRequest(request);
  const projectsResponse = await request.get(`${baseUrl}/api/projects`);
  if (!projectsResponse.ok()) {
    throw new Error(
      `Project fixture lookup failed: ${await projectsResponse.text()}`,
    );
  }
  const projects = (await projectsResponse.json()) as Array<{ id: string }>;
  if (projects.length === 0) {
    throw new Error("Notification fixture requires at least one project");
  }
  const reportResponse = await request.post(`${baseUrl}/api/reports/generate`, {
    data: { project_id: projects[0].id, report_type: "daily" },
  });
  if (!reportResponse.ok()) {
    throw new Error(
      `Notification fixture report create failed: ${await reportResponse.text()}`,
    );
  }
  const report = (await reportResponse.json()) as { id: string };
  const sendResponse = await request.post(
    `${baseUrl}/api/reports/${report.id}/send`,
    {
      data: { authorized: true, confirm_send: true, channels: ["in_app"] },
      headers: { "Idempotency-Key": `report-send-${report.id}` },
    },
  );
  if (!sendResponse.ok()) {
    throw new Error(
      `Notification fixture report send failed: ${await sendResponse.text()}`,
    );
  }
}

type WorkflowPlannerMode = "periodic_monitoring" | "batch_research";

const plannerProjects = {
  canonicalHeld: {
    id: "00000000-0000-4000-8000-000000000031",
    name: "Planner Fixture - Canonical Held",
  },
  syntheticPartial: {
    id: "00000000-0000-4000-8000-000000000032",
    name: "Planner Fixture - Synthetic Partial",
  },
  syntheticResolved: {
    id: "00000000-0000-4000-8000-000000000033",
    name: "Planner Fixture - Synthetic Resolved",
  },
} as const;

async function installLocalOnlyRequestGuard(
  page: Page,
): Promise<() => string[]> {
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    const requestUrl = new URL(request.url());
    if (
      (requestUrl.protocol === "http:" || requestUrl.protocol === "https:") &&
      requestUrl.hostname !== "localhost" &&
      requestUrl.hostname !== "127.0.0.1"
    ) {
      externalRequests.push(request.url());
    }
  });
  await page.route("**/*", async (route) => {
    const requestUrl = new URL(route.request().url());
    if (
      (requestUrl.protocol === "http:" || requestUrl.protocol === "https:") &&
      requestUrl.hostname !== "localhost" &&
      requestUrl.hostname !== "127.0.0.1"
    ) {
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });
  return () => [...externalRequests];
}

async function openPlannerFromDashboard(
  page: Page,
  projectName: string,
  mode: WorkflowPlannerMode,
) {
  await page.goto("/dashboard");
  const entryCards = page.getByTestId("workflow-planner-entry-cards");
  const periodicLink = entryCards.getByRole("link", { name: /创建监测项目/ });
  const batchLink = entryCards.getByRole("link", { name: /批量检索与解析/ });
  await expect(periodicLink).toHaveAttribute(
    "href",
    "/automation/planner?mode=periodic_monitoring",
  );
  await expect(batchLink).toHaveAttribute(
    "href",
    "/automation/planner?mode=batch_research",
  );
  await expect(entryCards).not.toContainText("运行");
  await expect(entryCards).not.toContainText("激活");
  const overviewFact = page.getByText("情报总量", { exact: true }).first();
  await expect(overviewFact).toBeVisible();
  await expect(
    entryCards.locator("xpath=following-sibling::*[1]"),
  ).toContainText("情报总量");

  await (mode === "periodic_monitoring" ? periodicLink : batchLink).click();
  await expect(page).toHaveURL(
    new RegExp(`/automation/planner\\?mode=${mode}$`),
  );
  await expect(page.locator(`#planner-mode-${mode}`)).toBeChecked();
  const selector = page.getByTestId("global-project-selector");
  await expect(
    selector.locator("option", { hasText: projectName }),
  ).toBeAttached();
  await selector.selectOption({ label: projectName });
  await expect(page.getByTestId("workflow-planner-workspace")).toContainText(
    projectName,
  );
  await expect(
    page.locator('[data-project-filter-applied="false"]'),
  ).toBeVisible();
}

async function openPlannerWithoutSelection(
  page: Page,
  mode: WorkflowPlannerMode,
) {
  await page.goto(`/automation/planner?mode=${mode}`);
  await expect(page.locator(`#planner-mode-${mode}`)).toBeChecked();
  await expect(
    page.getByTestId("global-project-selector").locator("option").nth(1),
  ).toBeAttached();
}

async function advanceBatchPlanner(
  page: Page,
  canonicalTerm: string,
  seedUrl?: string,
) {
  await page.getByRole("button", { name: "下一步" }).click();
  await page.locator("#planner-scope-0-canonical-term").fill(canonicalTerm);
  if (seedUrl) {
    await page.locator("#planner-scope-0-seed-url-0").fill(seedUrl);
  }
  await page.getByRole("button", { name: "下一步" }).click();
  await page.locator("#planner-platform-reddit").check();
  await page.getByRole("button", { name: "下一步" }).click();
}

async function generatePlannerPreview(page: Page) {
  await page.getByTestId("workflow-planner-generate-preview").click();
  await expect(page.getByTestId("workflow-planner-preview")).toBeVisible();
  await expect(
    page.getByTestId("workflow-planner-generate-preview"),
  ).toHaveAttribute("aria-busy", "false");
}

async function regeneratePlannerPreview(page: Page) {
  const sawBusy = page.evaluate(() => {
    const button = document.querySelector(
      '[data-testid="workflow-planner-generate-preview"]',
    );
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Generate Preview button is missing");
    }
    return new Promise<boolean>((resolve) => {
      const observer = new MutationObserver(() => {
        if (button.getAttribute("aria-busy") === "true") {
          observer.disconnect();
          resolve(true);
        }
      });
      observer.observe(button, {
        attributes: true,
        attributeFilter: ["aria-busy"],
      });
    });
  });
  await page.getByTestId("workflow-planner-generate-preview").click();
  expect(await sawBusy).toBe(true);
  await expect(
    page.getByTestId("workflow-planner-generate-preview"),
  ).toHaveAttribute("aria-busy", "false");
  await expect(page.getByTestId("workflow-planner-preview")).toBeVisible();
}

async function navigateWithPrimaryNavigation(page: Page, label: string) {
  const mobileDrawer = page.getByRole("dialog", { name: "移动主导航" });
  if (!(await mobileDrawer.isVisible())) {
    const mobileOpener = page.getByRole("button", { name: "打开导航" });
    if (await mobileOpener.isVisible()) {
      await mobileOpener.click();
      await expect(mobileDrawer).toBeVisible();
    }
  }
  const navigation = (await mobileDrawer.isVisible())
    ? mobileDrawer.getByRole("navigation", { name: "主导航" })
    : page.getByRole("navigation", { name: "主导航" });
  await navigation.getByRole("link", { name: label, exact: true }).click();
}

async function openSavedWorkflowPlan(
  page: Page,
  planName: string,
  expectedVersion: number,
) {
  await navigateWithPrimaryNavigation(page, "已保存计划");
  await expect(page).toHaveURL(/\/automation\/plans$/);
  const list = page.getByTestId("saved-workflow-plan-list");
  await expect(list).toBeVisible();
  const planLink = list.getByRole("link", { name: planName, exact: true });
  await expect(planLink).toHaveCount(1);
  await expect(planLink.locator("xpath=ancestor::tr")).toContainText(
    `v${expectedVersion}`,
  );
  await expectNoDocumentOverflow(page);
  await expectNoForbiddenWorkflowActions(list);
  const detailHref = await planLink.getAttribute("href");
  if (!detailHref) {
    throw new Error("Saved WorkflowPlan detail href is missing");
  }
  const detailUrl = new URL(detailHref, page.url()).toString();
  await planLink.click();
  await expect(page).toHaveURL(detailUrl);
  await expect(
    page.getByTestId("workflow-plan-detail-workspace"),
  ).toBeVisible();
  return { detailHref, detailUrl };
}

async function expectNoDocumentOverflow(page: Page) {
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(1);
}

async function expectNoForbiddenWorkflowActions(root: Locator) {
  const forbiddenAction =
    /activate|\brun\b|schedule|provider|actor|\bllm\b|workflow\s*run|激活|运行|调度/i;
  await expect(root.getByRole("button", { name: forbiddenAction })).toHaveCount(
    0,
  );
  await expect(root.getByRole("link", { name: forbiddenAction })).toHaveCount(
    0,
  );
}

test.beforeEach(async ({ page, request }, testInfo) => {
  if (!realApiMode) {
    return;
  }
  if (testInfo.title === "registers and logs in through the auth UI") {
    return;
  }
  await loginByApi(page, request);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/dashboard$/);
});

test.describe("MVP workspace routes", () => {
  test("registers and logs in through the auth UI", async ({
    page,
  }, testInfo) => {
    await page.context().clearCookies();
    const stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const email = `e2e-${testInfo.project.name}-${stamp}@example.com`;
    const password = `E2ePass-${stamp}`;

    await page.goto("/login");
    await expect(
      page.getByRole("heading", { name: "登录到可追溯的情报工作台" }),
    ).toBeVisible();
    await expectNoVisibleTechnicalNoise(page);

    await page.getByRole("button", { name: "注册" }).click();
    await page.getByRole("button", { name: "创建账号" }).click();
    await expect(page.getByText("请输入邮箱。")).toBeVisible();
    await page.getByLabel("名称").fill("E2E Workspace Owner");
    await page.getByLabel("邮箱").fill(email);
    await page.getByLabel("密码").fill(password);
    await page.getByLabel("Show password").click();
    await expect(page.locator("#auth-password")).toHaveAttribute("type", "text");
    await page.getByRole("button", { name: "创建账号" }).click();
    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });

    await page.context().clearCookies();
    await page.goto("/login");
    await page.getByLabel("邮箱").fill(email);
    await page.getByLabel("密码").fill(password);
    await page.getByRole("button", { name: "登录", exact: true }).last().click();
    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: "全局仪表盘" }),
    ).toBeVisible();
  });

  test("renders dashboard and intelligence evidence flow", async ({
    page,
    request,
  }, testInfo) => {
    await createIntelligenceFixture(request, testInfo.project.name);
    await page.goto("/dashboard");
    await expect(
      page.getByRole("heading", { name: "全局仪表盘" }),
    ).toBeVisible();
    await expect(page.getByText("情报总量")).toBeVisible();

    await page.goto("/intelligence");
    await expect(
      page.getByRole("heading", { name: "情报中心", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Intelligence 列表")).toBeVisible();
    await expect(
      page.getByRole("link", { name: "打开详情页" }).first(),
    ).toBeVisible();
    await expect(page.getByText("Evidence Timeline")).toBeVisible();
    await expect(page.getByText("采集运行").first()).toBeVisible();
    await expect(page.getByText("原始事实").first()).toBeVisible();
    await page.getByRole("link", { name: "打开详情页" }).click();
    await expect(page).toHaveURL(/\/intelligence\/.+/);
    await expect(page.getByText("原始内容摘要").first()).toBeVisible();
    await expect(page.getByText("证据摘录").first()).toBeVisible();
    await expect(page.getByText("查看原始数据").first()).toBeVisible();
    await expect(page.getByText("Content Hash")).toHaveCount(0);
    await expect(page.getByText("Reference Metadata")).toHaveCount(0);
    await expect(page.getByText("RawRecord ID")).toHaveCount(0);
    await expectNoVisibleTechnicalNoise(page);
  });

  test("filters toolkit and validates URL preflight guardrails", async ({
    page,
  }) => {
    await page.goto("/toolkit");
    await expect(
      page.getByRole("heading", { name: "数据采集培训工具与方法库" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "授权 URL 预检向导" }),
    ).toBeVisible();
    await expect(page.getByText("浏览器解析实验室")).toBeVisible();
    await expect(page.getByText("平台采集方法卡")).toBeVisible();

    const search = page.getByLabel("搜索采集工具库");
    await search.fill("Playwright");
    await expect(
      page.locator("button").filter({ hasText: "Playwright" }).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "安装 SOP", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "验收命令", exact: true }),
    ).toBeVisible();

    await search.fill("not-a-real-tool-filter");
    await expect(
      page.getByText("没有匹配工具，放宽关键词或筛选条件。"),
    ).toBeVisible();
    await page.getByRole("button", { name: "清空筛选" }).click();
    await expect(
      page.getByRole("heading", { name: "工具雷达", exact: true }),
    ).toBeVisible();
    await expect(
      page.locator("button").filter({ hasText: "Firecrawl" }).first(),
    ).toBeVisible();

    await page.getByRole("button", { name: "生成预检报告" }).click();
    await expect(page.getByText("请输入需要预检的授权 URL。")).toBeVisible();
    await page
      .getByPlaceholder("https://example.com")
      .fill("https://example.com");
    await page.getByRole("button", { name: "生成预检报告" }).click();
    await expect(
      page.getByText("必须先确认该 URL 属于自有、授权或明确允许分析的目标。"),
    ).toBeVisible();
    await page.getByLabel("Browser diagnostic JSON").fill(browserDiagnosticFixtureJson);
    await page.getByRole("button", { name: "导入浏览器诊断 JSON" }).click();
    await expect(page.getByRole("heading", { name: "真实浏览器诊断" })).toBeVisible();
    await expect(page.getByText("只读证据")).toBeVisible();
    await expect(page.getByText("已导入浏览器诊断，可作为后续字段契约和采集方式判断依据。")).toBeVisible();
    await expect(page.getByText("字段契约草案", { exact: true })).toBeVisible();
    await expect(page.getByText("采集工具推荐", { exact: true })).toBeVisible();
    await expect(page.getByText("generic_web 公开页面采集")).toBeVisible();
    await expect(page.getByText("可创建 generic_web 草稿")).toBeVisible();
    await page.getByLabel("Selector hint for visible_text").fill("main article");
    await page.getByLabel("选择字段 页面标题").uncheck();
    await page.getByRole("button", { name: "保存字段契约草稿" }).click();
    await expect(page.getByText("字段契约已保存")).toBeVisible();
    await expect(page.getByText("已选择 2 个字段")).toBeVisible();
    await expect(page.getByLabel("Selector hint for visible_text")).toHaveValue("main article");
    await expect(page.getByText("API 候选")).toBeVisible();
    await page.getByRole("button", { name: "清空" }).last().click();
    await page.getByLabel("Browser diagnostic JSON").fill(browserAutomationDiagnosticFixtureJson);
    await page.getByRole("button", { name: "导入浏览器诊断 JSON" }).click();
    await expect(page.getByText("浏览器自动化任务草稿")).toBeVisible();
    await expect(page.getByText("browser_harness · 字段")).toBeVisible();
    await expect(page.getByText("创建前复核", { exact: true })).toBeVisible();
    await expect(page.getByText("只读执行，不提交表单、不点击购买或发布类按钮。")).toBeVisible();
    await expectNoVisibleTechnicalNoise(page);
  });

  test("renders API market list and endpoint detail without live calls", async ({
    page,
  }) => {
    await page.goto("/api-market");
    await expect(
      page.getByRole("heading", { level: 1, name: "能力市场" }),
    ).toBeVisible();
    await expect(
      page.getByText("provider_call=false", { exact: true }).first(),
    ).toBeVisible();
    await expect(page.getByText("credential_read_attempted")).toHaveCount(0);

    await page.getByRole("button", { name: "列表视图" }).click();
    await page.getByTestId("capability-filter-platform").selectOption("youtube");
    const youtubeImplementation = page.locator(
      'article[data-implementation-id="youtube.v3"]',
    );
    await expect(youtubeImplementation).toBeVisible();
    await youtubeImplementation
      .getByRole("button", { name: "能力详情" })
      .click();
    const capabilityDialog = page.getByRole("dialog", { name: "能力详情" });
    await expect(capabilityDialog).toContainText(
      "credential_read_attempted",
    );
    await capabilityDialog
      .getByRole("link", {
        name: "Fixture Review: YouTube Comment Threads",
      })
      .click();

    await expect(page).toHaveURL(/\/api-market\/youtube-v3-commentthreads-list$/);
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "YouTube Comment Threads",
      }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "请求合同与参数" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Fixture 响应预览" })).toBeVisible();
    await expect(page.getByText("provider_call_attempted")).toBeVisible();
    await expect(page.getByText("credential_read_attempted")).toBeVisible();
    await expect(page.getByText("live_client_created")).toBeVisible();
    await expect(page.getByText("production_write_allowed")).toBeVisible();
    await expect(page.getByText("false").first()).toBeVisible();
    await expect(page.getByText("social_comment.v1")).toBeVisible();
    await expect(page.getByText("fixture://youtube.v3/commentThreads.list/1")).toBeVisible();
    await expect(page.getByRole("button", { name: "复制 fixture" })).toBeVisible();

    await page.getByRole("button", { name: "生成本页预案" }).click();
    await expect(page.getByRole("heading", { name: "Readiness Review" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Adapter Plan Gate" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Dataset Preview Gate" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Source Template Gate" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "L4 Approval Packet Gate" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Execution Dry Run" })).toBeVisible();
    await expect(page.getByText("provider_call_attempted=false").first()).toBeVisible();
    await expect(page.getByText("credential_read_attempted=false").first()).toBeVisible();
    await expect(page.getByText("live_client_created=false").first()).toBeVisible();
    await expect(page.getByText("production_write_allowed=false").first()).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("generates and sends a report", async ({ page, request }, testInfo) => {
    await createReportFixture(request, testInfo.project.name);
    await page.goto("/reports");
    await expect(page.getByRole("heading", { name: "报告中心" })).toBeVisible();
    await expect(
      page
        .locator("section")
        .filter({ has: page.getByRole("heading", { name: "报告队列" }) })
        .locator("article")
        .first(),
    ).toBeVisible();
    await expect(page.getByLabel("生成项目")).toBeVisible();
    await expect(page.getByLabel("报告筛选项目")).toBeVisible();
    const reportQueue = page.locator("section").filter({
      has: page.getByRole("heading", { name: "报告队列" }),
    });
    await page
      .getByPlaceholder("搜索标题、项目、正文...")
      .fill("not-a-real-report-filter");
    await expect(page.getByText("当前筛选条件下暂无报告")).toBeVisible();
    await page.getByPlaceholder("搜索标题、项目、正文...").fill("");
    await reportQueue
      .getByRole("button", { name: "待发送", exact: true })
      .click();
    await expect(reportQueue.locator("article").first()).toBeVisible();
    await reportQueue.getByRole("button", { name: "全部", exact: true }).click();
    await expect(page.getByText("自动分发", { exact: true }).first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "订阅规则", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("邮件通道诊断")).toBeVisible();
    if (!realApiMode) {
      await page.getByRole("button", { name: "测试邮件" }).click();
      await expect(page.getByText(/测试未发送|测试邮件已发送/)).toBeVisible();
    }
    await page.getByLabel("发送时间").fill("09:30");
    await page.getByLabel("站内通知").check();
    await page.getByLabel("邮件").check();
    await page.getByRole("button", { name: "保存订阅", exact: true }).click();
    await expect(page.getByText("订阅已保存")).toBeVisible();
    await expect(page.getByText(/09:30/).first()).toBeVisible();
    await page.getByRole("button", { name: "立即执行" }).first().click();
    await expect(page.getByText("订阅已手动执行")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByRole("button", { name: "立即执行" }).first(),
    ).toBeEnabled();
    await page.getByRole("button", { name: "执行历史" }).first().click();
    await expect(page.getByText("手动触发").first()).toBeVisible();
    const retryButton = page.getByRole("button", { name: "重试" }).first();
    const retryCount = await retryButton.count();
    if (!realApiMode || retryCount > 0) {
      await retryButton.click();
      await expect(page.getByText("订阅已重试")).toBeVisible();
      await expect(page.getByText("失败重试").first()).toBeVisible();
    }
    await page.getByLabel("生成周期").selectOption("24h");
    await expect(page.getByText("证据引用").first()).toBeVisible();
    await expect(page.getByText("证据引用详情").first()).toBeVisible();
    const reportIntelligenceLink = page
      .locator('a[href^="/intelligence/"]')
      .first();
    if (realApiMode) {
      const evidenceBackedReport = page
        .getByRole("button")
        .filter({ hasText: /[1-9]\d* evidence refs/ })
        .first();
      if ((await evidenceBackedReport.count()) > 0) {
        await evidenceBackedReport.click();
        await expect(reportIntelligenceLink).toBeVisible();
      }
    } else {
      await expect(reportIntelligenceLink).toBeVisible();
    }

    const selectedReportDetail = page.locator("section").filter({
      hasText: "派发状态",
    });
    await selectedReportDetail.getByRole("link", { name: "打开详情页" }).click();
    await expect(page).toHaveURL(/\/reports\/.+/);
    await expect(page.getByRole("heading", { name: "报告详情" })).toBeVisible();
    await expect(page.getByText("审计记录").first()).toBeVisible();
    await expect(page.getByText("证据引用详情").first()).toBeVisible();
    await page.getByRole("button", { name: "复制链接", exact: true }).click();
    await expect(page.getByText("链接已复制").first()).toBeVisible();
    await expect(page.getByText("复制链接").first()).toBeVisible();
    await page.getByRole("link", { name: "返回报告中心" }).click();
    await expect(page).toHaveURL(/\/reports$/);

    const downloadPromise = page.waitForEvent("download");
    await page
      .getByRole("button", { name: "下载 Markdown", exact: true })
      .click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.md$/);

    await page.getByRole("button", { name: "生成日报", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "核心发现", exact: true }),
    ).toBeVisible();

    const reportDetail = page
      .locator("section")
      .filter({ hasText: "派发状态" });
    await reportDetail
      .getByRole("button", { name: "发送报告", exact: true })
      .click();
    await expect(
      reportDetail.getByRole("button", { name: "已发送", exact: true }),
    ).toBeDisabled();
    await expect(reportDetail.getByText("报告已进入通知链路")).toBeVisible();
    await expect(reportDetail.getByText("报告发送").first()).toBeVisible();
  });

  test("creates alert rule and displays alert events", async ({
    page,
  }, testInfo) => {
    await page.goto("/alerts");
    await expect(page.getByRole("heading", { name: "预警中心" })).toBeVisible();
    await expect(page.getByText("预警事件流")).toBeVisible();
    const ruleCards = page
      .locator("article")
      .filter({ hasText: "High severity signal" });
    if (!realApiMode) {
      await expect(ruleCards).toHaveCount(1);
      await expect(
        page.getByRole("heading", { name: "page_changed" }),
      ).toBeVisible();
    }

    const ruleName = `High severity signal ${testInfo.project.name} ${Date.now()}`;
    await page.getByLabel("规则名称").fill(ruleName);
    await page.getByRole("button", { name: "创建规则" }).click();
    await expect(page.getByText(`${ruleName}：规则已创建`)).toBeVisible();
    await expect(
      page.locator("article").filter({ hasText: ruleName }),
    ).toHaveCount(1);
    await expectNoVisibleTechnicalNoise(page);
  });

  test("filters alert events and updates event status", async ({
    page,
    request,
  }, testInfo) => {
    await createAlertEventFixture(request, `status-${testInfo.project.name}`);
    await page.goto("/alerts");
    await expect(page.getByRole("heading", { name: "预警中心" })).toBeVisible();

    const eventStream = page.locator("aside").filter({
      has: page.getByRole("heading", { name: "预警事件流" }),
    });
    const eventSearch = eventStream.getByPlaceholder("搜索事件、信号");
    const eventStatus = eventStream.locator("select");
    const eventCard = eventStream.getByRole("button", { name: /star_growth/ }).first();

    await eventSearch.fill("not-a-real-alert-event");
    await expect(page.getByText("没有匹配的预警事件。")).toBeVisible();
    await eventSearch.fill("star_growth");
    await eventStatus.selectOption(realApiMode ? "sent" : "acknowledged");
    await expect(eventCard).toBeVisible();
    await eventCard.click();
    await expect(eventStream.getByText("事件事实")).toBeVisible();

    const acknowledgeButton = eventStream.getByRole("button", { name: "确认", exact: true });
    if (realApiMode) {
      await acknowledgeButton.click();
      await expect(page.getByText(/告警事件 .*：已确认/)).toBeVisible();
    } else {
      await expect(acknowledgeButton).toBeDisabled();
    }
    await eventStatus.selectOption("acknowledged");
    await expect(eventCard).toBeVisible();

    await eventStream.getByRole("button", { name: "解决", exact: true }).click();
    await expect(page.getByText(/告警事件 .*：已解决/)).toBeVisible();
    await eventStatus.selectOption("resolved");
    await expect(eventCard).toBeVisible();
    await expectNoVisibleTechnicalNoise(page);
  });

  test("creates project and opens domain workspace", async ({
    page,
  }, testInfo) => {
    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "项目组合控制台" })).toBeVisible();

    const projectName = `Playwright Project ${testInfo.project.name} ${Date.now()}`;
    await page.getByRole("button", { name: "New Project" }).click();
    await expect(page.getByRole("dialog", { name: "创建项目" })).toBeVisible();
    await page.getByLabel("Name").fill(projectName);
    await page.getByLabel("Domain").selectOption("competitor");
    await page.getByLabel("Owner").fill("e2e");
    await page
      .getByLabel("Description")
      .fill("生产 E2E 创建的竞品采集项目，用于验证项目页、筛选和业务域跳转。");
    await page.getByRole("button", { name: "创建" }).click();
    await expect(page.getByText(`${projectName} created for e2e`)).toBeVisible();
    await page.getByPlaceholder("搜索项目、域、状态").fill(projectName);
    const projectCard = visibleArticleByText(page, projectName);
    await expect(projectCard).toBeVisible();
    await expect(page.getByRole("heading", { name: "项目作战室" })).toBeVisible();
    await projectCard.getByRole("link", { name: "Domain" }).click();
    await expect(page).toHaveURL(/\/domain\/competitor$/);
    await expect(
      page.getByRole("heading", { name: "竞品守望", exact: true }),
    ).toBeVisible();
    await expectNoVisibleTechnicalNoise(page);
  });

  test("runs automation workbench through dataset save and read-only drift check", async ({
    page,
  }) => {
    await createAutomationDatasetAsset(page);
  });

  test("renders automation platform packages and applies executable package", async ({
    page,
  }) => {
    await page.goto("/automation");
    await expect(page.getByRole("heading", { name: "采集入口与授权边界" })).toBeVisible();
    await expect(page.getByText("持久化").first()).toBeVisible();
    await expect(page.getByText("监控").first()).toBeVisible();
    await expect(page.getByText("诊断").first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "平台包矩阵" }),
    ).toBeVisible();
    await expect(page.getByText("独立站 / Shopify-style 商品采集", { exact: true })).toBeVisible();
    await expect(page.getByText("GitHub API-first 工具情报采集", { exact: true })).toBeVisible();
    await expect(page.getByText("公开网页结构解析预检", { exact: true })).toBeVisible();
    await expect(page.getByText("Public Web / RSS / Docs 更新监控", { exact: true })).toBeVisible();
    await expect(page.getByText("可执行", { exact: true })).toHaveCount(4);

    await page
      .getByRole("button", { name: "应用独立站 / Shopify-style 商品采集" })
      .click();
    await expect(page.getByRole("button", { name: "商品发现" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.getByLabel("集合页 / 列表页 URL")).toHaveValue(
      "https://shop.example/collections/summer-bags",
    );
    const appliedPackagePanel = page.locator("section").filter({
      hasText: "已应用平台包：独立站 / Shopify-style 商品采集",
    });
    await expect(
      appliedPackagePanel.getByText("已应用平台包：独立站 / Shopify-style 商品采集"),
    ).toBeVisible();
    await expect(appliedPackagePanel.getByText("操作清单")).toBeVisible();
    await expect(appliedPackagePanel.getByText("默认清洗规则")).toBeVisible();
    await expect(appliedPackagePanel.getByText("标题", { exact: true }).first()).toBeVisible();
    await expect(appliedPackagePanel.getByText("价格", { exact: true }).first()).toBeVisible();
    await expect(appliedPackagePanel.getByText("SKU", { exact: true }).first()).toBeVisible();
    await expect(appliedPackagePanel.getByText("SKU: fill_default")).toBeVisible();
    await expect(appliedPackagePanel.getByText("规范 URL", { exact: true }).first()).toBeVisible();

    await page.getByRole("button", { name: "应用公开网页结构解析预检" }).click();
    await expect(page.getByRole("button", { name: "结构预检", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.getByLabel("公开网页 URL")).toHaveValue("https://example.com");
    await expect(page.locator("form").getByText("预检范围", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "生成结构预检" }).click();
    await expect(
      page.getByText("请先确认目标为公开页面或公开 API，且你有权进行采集分析。"),
    ).toBeVisible();

    await page.getByRole("button", { name: "应用GitHub API-first 工具情报采集" }).click();
    await expect(page.getByRole("button", { name: "GitHub 主题", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.getByLabel("GitHub topic")).toHaveValue("web-scraping");
    await page
      .getByLabel("我确认目标为公开可访问页面或公开 API，采集分析不涉及登录态、验证码绕过或未授权数据访问。")
      .check();
    await page.getByLabel("最多仓库").fill("3");
    await page.getByRole("button", { name: "创建并运行 GitHub 主题雷达" }).click();
    await expect(page.getByRole("heading", { name: "公开仓库情报采集结果" })).toBeVisible();
    await expect(page.getByText("采集源与任务已创建")).toBeVisible();
    await expect(page.getByText("GitHub Topic Radar: web-scraping")).toBeVisible();
    await expect(page.getByText("github_topic", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("成功", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "生成工具数据集预览" }).click();
    await expect(page.getByText("工具情报数据集", { exact: true })).toBeVisible();
    await expect(page.getByText("仓库行数")).toBeVisible();
    await expect(page.getByText("github_tool_radar.v2")).toBeVisible();
    await expect(page.getByText("html_url", { exact: true }).last()).toBeVisible();
    await expect(page.getByText("source_task_run_ids / raw_record_id / source_url")).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Release 时间" })).toBeVisible();
    if (!realApiMode) {
      await expect(page.getByText("v0.7.0")).toBeVisible();
    }
    await page.getByRole("button", { name: "保存工具数据集" }).click();
    await expect(page.getByText("数据集 ID:")).toBeVisible();
    await expect(page.getByText("工具雷达验收")).toBeVisible();
    await page.getByRole("button", { name: "生成雷达报告" }).click();
    await expect(page.getByText("高价值仓库")).toBeVisible();
    await expect(page.getByText("维护风险", { exact: true })).toBeVisible();
    if (!realApiMode) {
      await expect(page.getByText("风险 low")).toBeVisible();
      await expect(page.getByText("low=2")).toBeVisible();
    }
    await expect(page.getByText("not_a_provider_call_or_live_install")).toBeVisible();
    await page.getByRole("button", { name: "保存到报告中心" }).click();
    await expect(page.getByText("已保存到报告中心")).toBeVisible();
    await expect(page.getByRole("link", { name: "打开报告" })).toBeVisible();
    await page.getByRole("button", { name: "检查工具漂移" }).click();
    await expect(page.getByText("检查任务")).toBeVisible();
    await expect(page.getByText("状态", { exact: true }).first()).toBeVisible();
    if (!realApiMode) {
      await expect(page.getByText("字段缺失").first()).toBeVisible();
      await expect(page.getByText("missing:topics")).toBeVisible();
      await expect(page.getByText("Issue 活跃", { exact: true }).last()).toBeVisible();
      await expect(page.getByText("open_issues_increased:120->200")).toBeVisible();
      await expect(page.getByText("Release 新鲜度", { exact: true }).last()).toBeVisible();
      await expect(page.getByText("latest_release_published_at_missing")).toBeVisible();
    }
    await page.getByRole("button", { name: "保存漂移快照" }).click();
    await expect(page.getByText("已保存漂移快照")).toBeVisible();
    await expectNoVisibleTechnicalNoise(page);
  });

  test("saves browser automation diagnostic as read-only plan", async ({
    page,
  }) => {
    await page.route("**/api/toolkit/preflight", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        status: 200,
        body: JSON.stringify({
          requested_url: "https://example.com/app",
          final_url: "https://example.com/app",
          checked_at: "2026-06-19T14:20:00Z",
          authorization_confirmed: true,
          headers: { "content-type": "text/html" },
          redirects: [],
          robots: {
            url: "https://example.com/robots.txt",
            status_code: 200,
            content_type: "text/plain",
            content_length: 24,
            available: true,
            summary: "No blocking rule found.",
          },
          sitemap: {
            url: "https://example.com/sitemap.xml",
            status_code: 404,
            content_type: null,
            content_length: null,
            available: false,
            summary: "Not found.",
          },
          security_txt: {
            url: "https://example.com/.well-known/security.txt",
            status_code: 404,
            content_type: null,
            content_length: null,
            available: false,
            summary: "Not found.",
          },
          dom: {
            title: "Dynamic Product Grid",
            description: "Dynamic app shell",
            canonical_url: "https://example.com/app",
            meta_robots: null,
            headings: ["Dynamic Product Grid"],
            link_count: 12,
            script_count: 24,
            stylesheet_count: 4,
            image_count: 16,
            form_count: 0,
            text_sample: "Dynamic Product Grid",
          },
          network: {
            request_method: "GET",
            final_status_code: 200,
            final_content_type: "text/html",
            redirect_count: 0,
            same_origin_links: 12,
            external_links: 6,
            script_count: 24,
            stylesheet_count: 4,
            image_count: 16,
            form_count: 0,
          },
          authorization_gate: {
            allowed_to_continue: true,
            risk_level: "medium",
            blocked_reasons: [],
            required_next_actions: ["导入 browser-harness 只读诊断。"],
          },
          collection_strategy: {
            recommended_path: "browser_automation",
            label: "浏览器自动化",
            fit: "medium",
            confidence: 72,
            field_stability: "medium",
            reasons: ["页面依赖浏览器渲染和异步接口。"],
            next_steps: ["保存只读 browser automation 方案。"],
            cleaning_notes: ["复核字段 selector hint。"],
          },
          recommendations: ["导入 browser-harness 证据后保存只读方案。"],
        }),
      });
    });
    await page.goto("/automation");
    await page.getByRole("button", { name: "结构预检", exact: true }).click();
    await expect(page.getByRole("heading", { name: "浏览器诊断与执行器边界" })).toBeVisible();
    await page
      .getByLabel("我确认目标为公开可访问页面或公开 API，采集分析不涉及登录态、验证码绕过或未授权数据访问。")
      .check();
    await page.getByLabel("公开网页 URL").fill("https://example.com/app");
    await page.getByRole("button", { name: "生成结构预检" }).click();
    await expect(
      page.getByRole("heading", { name: "公开网页结构预检结果" }),
    ).toBeVisible();

    await page.getByLabel("Browser diagnostic JSON").fill(browserAutomationDiagnosticFixtureJson);
    await page.getByRole("button", { name: "导入浏览器诊断 JSON" }).click();
    await expect(page.getByText("浏览器自动化任务草稿")).toBeVisible();
    await expect(page.getByRole("button", { name: "保存只读自动化方案" })).toBeVisible();

    await page.getByRole("button", { name: "保存只读自动化方案" }).click();
    await expect(page.getByText(/已保存 Browser Automation:/)).toBeVisible();
    await expect(page.getByText("浏览器诊断资产")).toBeVisible();
    await expect(page.getByText("只读资产").first()).toBeVisible();
    await expect(page.getByText("执行规格：").first()).toBeVisible();
    await page.getByRole("button", { name: "校验执行规格" }).click();
    await expect(page.getByText("规格校验：需复核")).toBeVisible();
    await expect(page.getByText("未启动浏览器运行，未允许写入。")).toBeVisible();
    await page.getByRole("button", { name: "创建浏览器诊断任务" }).click();
    await expect(page.getByText("浏览器诊断任务", { exact: true })).toBeVisible();
    await expect(page.getByText("已审核，等待人工执行")).toBeVisible();
    await expect(page.getByText("任务已创建为只读资产，执行器尚未接入。")).toBeVisible();
    await page.getByRole("button", { name: "生成执行器合同" }).click();
    await expect(page.getByText("执行器合同", { exact: true })).toBeVisible();
    await expect(page.getByText("browser_harness_read_only_local")).toBeVisible();
    await expect(page.getByText("local_ephemeral_browser_context")).toBeVisible();
    await page.getByRole("button", { name: "生成本地回放证据" }).click();
    await expect(page.getByText("本地回放证据", { exact: true })).toBeVisible();
    await expect(page.getByText("diagnostic_snapshot_replay")).toBeVisible();
    await expect(page.getByText("未启动真实浏览器", { exact: true })).toBeVisible();
    await expect(page.getByText("Dynamic Product Grid").first()).toBeVisible();
    await page.getByRole("button", { name: "运行本机浏览器探测" }).click();
    await expect(page.getByText("ephemeral_browser_harness_probe")).toBeVisible();
    await expect(page.getByText("已完成浏览器只读探测", { exact: true })).toBeVisible();
    await expect(page.getByText("未写文件", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "取消任务" }).click();
    await expect(page.getByText("已取消")).toBeVisible();
    await expect(page.getByText("未启动采集运行。").first()).toBeVisible();
    await expectNoVisibleTechnicalNoise(page);
  });

  test("operates real dataset asset export and drift alert preview", async ({
    page,
  }, testInfo) => {
    test.skip(!realApiMode, "Dataset asset write-through smoke needs real API.");

    const datasetName = `Playwright Dataset ${testInfo.project.name} ${Date.now()}`;
    await createAutomationDatasetAsset(page, datasetName);

    await page.goto("/datasets");
    await expect(
      page.getByRole("heading", { name: "数据集资产台", exact: true }),
    ).toBeVisible();
    const datasetCard = page.locator("button").filter({ hasText: datasetName }).first();
    await expect(datasetCard).toBeVisible({ timeout: 15_000 });
    await datasetCard.click();
    await expect(page.getByRole("heading", { name: "选中数据集概览" })).toBeVisible();
    await expect(page.getByText(datasetName).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "版本历史" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "版本字段与清洗规则" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "数据集导出" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "漂移告警策略" })).toBeVisible();
    await expect(page.getByText("文件写出 Gate")).toBeVisible();
    await expect(page.getByText("只读预览 Gate")).toBeVisible();
    await expect(page.getByText("策略写入 Gate")).toBeVisible();
    await expect(page.getByText("事件桥接 Gate")).toBeVisible();
    await expect(page.getByText("站内通知发送 Gate")).toBeVisible();
    await expect(page.getByText("外部邮件发送 Gate")).toBeVisible();
    await expect(page.getByText("数据行预览")).toBeVisible();
    await expect(page.getByText("Demo Carry Bag", { exact: true }).first()).toBeVisible();

    await page.getByLabel("导出格式").selectOption("json");
    await page.getByRole("button", { name: "生成导出文件" }).click();
    await expect(page.getByText("已生成导出文件")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("link", { name: "下载" }).first()).toBeVisible();

    await page.getByLabel("触发阈值").selectOption("warning");
    await page.getByLabel("通知通道").selectOption("in_app");
    await page.getByRole("button", { name: "预览告警策略" }).click();
    await expect(page.getByText("匹配漂移快照")).toBeVisible();
    await expect(page.getByText("预览不会创建告警策略")).toBeVisible();
    await expectNoVisibleTechnicalNoise(page);
  });

  test("renders dataset assets and drift history in mock mode", async ({ page }) => {
    test.skip(realApiMode, "Dataset asset smoke is mock-only in this suite.");

    await page.goto("/datasets");
    await expect(
      page.getByRole("heading", { name: "数据集资产台", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "数据集资产池" })).toBeVisible();
    await expect(page.getByText("Shopify 商品价格数据集").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "选中数据集概览" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "版本历史" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "版本字段与清洗规则" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "数据集导出" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "漂移历史" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "漂移告警策略" })).toBeVisible();
    await expect(page.getByText("文件写出 Gate")).toBeVisible();
    await expect(page.getByText("事件桥接 Gate")).toBeVisible();
    await expect(page.getByText("外部邮件发送 Gate")).toBeVisible();
    await expect(page.getByText("Version 2")).toBeVisible();
    await expect(page.getByText("cast price to decimal when present").first()).toBeVisible();
    await expect(page.getByText("数据行预览")).toBeVisible();
    await expect(page.getByText("Demo Carry Bag", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "生成导出文件" }).click();
    await expect(page.getByText("已生成导出文件")).toBeVisible();
    await expect(page.getByRole("link", { name: "下载" }).first()).toBeVisible();
    await expect(page.getByText("商品字段漂移").first()).toBeVisible();
    await expect(page.getByText("缺字段：price, sku")).toBeVisible();
    await page.getByRole("button", { name: "预览告警策略" }).click();
    await expect(page.getByText("匹配漂移快照")).toBeVisible();
    await expect(page.getByText("预览不会创建告警策略")).toBeVisible();
    await page.getByRole("button", { name: "确认创建策略" }).click();
    await expect(page.getByText("已创建漂移告警策略")).toBeVisible();
    await expect(page.getByText("未创建告警事件")).toBeVisible();
    await page.getByRole("button", { name: "生成告警事件" }).click();
    await expect(page.getByText("已生成数据集漂移信号")).toBeVisible();
    await expect(page.getByText("已创建告警事件 1 条")).toBeVisible();
    await expect(page.getByText("未发送通知").first()).toBeVisible();
    await page.getByRole("button", { name: "发送站内通知" }).click();
    await expect(page.getByText("已发送站内通知 1 条")).toBeVisible();
    await expect(page.getByText("告警事件已标记为已发送")).toBeVisible();
    await expect(page.getByText("未发送邮件")).toBeVisible();

    await page.getByRole("combobox", { name: "通知通道" }).selectOption("email");
    await page.getByRole("button", { name: "预览告警策略" }).click();
    await expect(page.getByText("预览不会创建告警策略")).toBeVisible();
    await page.getByRole("button", { name: "确认创建策略" }).click();
    await expect(
      page.getByText("已创建漂移告警策略").first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "生成告警事件" }).last().click();
    await expect(page.getByText("已创建告警事件 1 条")).toBeVisible();
    await page.getByRole("button", { name: "发送邮件告警" }).last().click();
    await expect(page.getByText("已发送邮件告警")).toBeVisible();
  });

  test("covers signals entities raw records and domain pages", async ({
    page,
    request,
  }, testInfo) => {
    await createIntelligenceFixture(request, `coverage-${testInfo.project.name}`);

    await page.goto("/signals");
    await expect(page.getByRole("heading", { name: "信号检测控制台" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "信号详情" })).toBeVisible();
    await expect(page.getByText("检测规则事实")).toBeVisible();
    await expect(
      page.locator("button").filter({ hasText: /Star Growth|Page Changed|Data Quality/ }).first(),
    ).toBeVisible();
    await page.getByPlaceholder("搜索信号、实体、规则").fill("not-a-real-signal");
    await expect(page.getByText("没有匹配的信号。")).toBeVisible();
    await page.getByPlaceholder("搜索信号、实体、规则").fill("");
    await expectNoVisibleTechnicalNoise(page);

    await page.goto("/entities");
    await expect(page.getByRole("heading", { name: "实体快照工作台" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "快照时间线" })).toBeVisible();
    await expect(page.getByText("来源批次").first()).toBeVisible();
    await page.getByPlaceholder("搜索实体、外部 ID").fill("playwright");
    await expect(page.getByText(/Playwright|没有匹配的实体/i).first()).toBeVisible();
    await expectNoVisibleTechnicalNoise(page);

    await page.goto("/raw-records");
    await expect(page.getByRole("heading", { name: "原始事实层审计台" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "记录详情" })).toBeVisible();
    await expect(page.getByText("关键事实字段").first()).toBeVisible();
    await page.getByPlaceholder("搜索标题、来源、字段").fill("playwright");
    await expect(page.getByText(/playwright|没有匹配的原始事实/i).first()).toBeVisible();
    await expectNoVisibleTechnicalNoise(page);

    for (const [route, heading] of [
      ["/domain/osint", "开源雷达"],
      ["/domain/ecommerce", "电商风向"],
      ["/domain/social", "社媒脉搏"],
      ["/domain/competitor", "竞品守望"],
    ] as const) {
      await page.goto(route);
      await expect(
        page.getByRole("heading", { name: heading, exact: true }),
      ).toBeVisible();
      await expect(page.getByText("情报总量")).toBeVisible();
      await expectNoVisibleTechnicalNoise(page);
    }
  });

  test("manages source edit retest enable and disable flow", async ({
    page,
  }, testInfo) => {
    await page.goto("/sources");
    await expect(
      page.getByRole("heading", { name: "数据源接入工作台" }),
    ).toBeVisible();
    await expect(page.getByText("数据源资产池")).toBeVisible();

    const sourceName = `Playwright Manual JSON ${testInfo.project.name} ${Date.now()}`;
    const updatedName = `${sourceName} Updated`;
    await page.getByRole("button", { name: /Manual JSON/ }).click();
    await page.getByLabel("名称").fill(sourceName);
    await page.getByLabel("Entity Type").fill("github_repo");
    await page
      .getByLabel("JSON")
      .fill(
        JSON.stringify(
          { full_name: "playwright/source-flow", stars: 88 },
          null,
          2,
        ),
      );
    await page.getByLabel("Cron").fill("");
    await page.getByRole("button", { name: "创建 Source" }).click();
    await expect(page.getByText("Source created")).toBeVisible();

    let sourceCard = visibleArticleByText(page, sourceName);
    await expect(sourceCard).toBeVisible();
    await sourceCard.getByRole("button", { name: "编辑" }).click();
    await page.getByLabel("名称").fill(updatedName);
    await page
      .getByLabel("JSON")
      .fill(
        JSON.stringify(
          { full_name: "playwright/source-flow", stars: 144 },
          null,
          2,
        ),
      );
    await page.getByLabel("JSON").blur();
    await page
      .getByRole("button", { name: "保存 Source" })
      .scrollIntoViewIfNeeded();
    await activateControl(
      page.getByRole("button", { name: "保存 Source" }),
      testInfo.project.name,
    );
    await expect(
      page.getByText(`${updatedName}: source updated; retest before next run`),
    ).toBeVisible();

    sourceCard = visibleArticleByText(page, updatedName);
    await activateControl(
      sourceCard.getByRole("button", { name: "重测配置" }),
      testInfo.project.name,
    );
    await expect(
      page.getByText(`${updatedName}: Config is valid.`),
    ).toBeVisible();
    await activateControl(
      sourceCard.getByRole("button", { name: "启用" }),
      testInfo.project.name,
    );
    await expect(page.getByText(`${updatedName}: task enabled`)).toBeVisible();
    sourceCard = visibleArticleByText(page, updatedName);
    await expect(sourceCard).toContainText("已启用");
    await expect(sourceCard).toContainText("尚未运行");
    await activateControl(
      sourceCard.getByRole("button", { name: "停用" }),
      testInfo.project.name,
    );
    await expect(
      page.getByText(`${updatedName}: source disabled`),
    ).toBeVisible();
    sourceCard = visibleArticleByText(page, updatedName);
    await expect(sourceCard).toContainText("已停用");
  });

  test("inspects task workspace and diagnostics", async ({
    page,
    request,
  }, testInfo) => {
    const fixtureTaskName = await createTaskFlowFixture(
      request,
      testInfo.project.name,
    );
    await page.goto("/tasks");
    await expect(
      page.getByRole("heading", { name: "采集运行控制台", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "任务运行列表", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "失败任务诊断", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "运行日志", exact: true }),
    ).toBeVisible();
    if (fixtureTaskName) {
      await page
        .getByPlaceholder("搜索任务名称或数据源...")
        .fill(fixtureTaskName);
      if (testInfo.project.name === "mobile") {
        await expect(
          page.locator("div.md\\:hidden").getByText(fixtureTaskName).first(),
        ).toBeVisible();
      } else {
        await expect(
          page.locator("tbody").getByText(fixtureTaskName).first(),
        ).toBeVisible();
      }
    }
    const desktopRows = page.locator("tbody tr");
    const emptyHint = page.locator("p:has-text('当前筛选条件下没有任务')");
    if (testInfo.project.name === "mobile") {
      const mobileCards = page.locator("div.md\\:hidden [role='button']");
      if ((await mobileCards.count()) > 0) {
        const mobileTaskCard = fixtureTaskName
          ? mobileCards.filter({ hasText: fixtureTaskName }).first()
          : mobileCards.first();
        await expect(mobileTaskCard).toBeVisible();
        await mobileTaskCard.getByRole("button", { name: "日志" }).click();
        await expect(page.getByText("查看最近一次运行详情")).toBeVisible();
        await expect(page.getByRole("heading", { name: "运行历史" })).toBeVisible();
        await expect(page.getByText("重试历史")).toBeVisible();
        const pauseButton = mobileTaskCard.getByRole("button", { name: "暂停" });
        if ((await pauseButton.count()) > 0) {
          await pauseButton.click();
          await expect(page.getByText(/paused/)).toBeVisible();
          await mobileTaskCard.getByRole("button", { name: "恢复" }).click();
          await expect(page.getByText(/resumed/)).toBeVisible();
        }
      } else if ((await emptyHint.count()) > 0) {
        await expect(emptyHint.first()).toBeVisible();
      } else {
        const desktopRowCount = await desktopRows.count();
        if (desktopRowCount > 0) {
          expect(desktopRowCount).toBeGreaterThan(0);
        }
      }
      return;
    }

    if ((await emptyHint.count()) > 0) {
      await expect(emptyHint.first()).toBeVisible();
      return;
    }

    const firstTaskRow = desktopRows.first();
    await firstTaskRow.click();
    const pauseButton = firstTaskRow.locator('button[title="暂停"]');
    if ((await pauseButton.count()) > 0) {
      await pauseButton.click();
      await expect(page.getByText(/paused/)).toBeVisible();
    }
    const resumeButton = firstTaskRow.locator('button[title="恢复"]');
    if ((await resumeButton.count()) > 0) {
      await resumeButton.click();
      await expect(page.getByText(/resumed/)).toBeVisible();
    }
    const rowLogButton = firstTaskRow.locator('button[title="日志"]');
    await expect(rowLogButton).toBeVisible();
    await rowLogButton.click();
    await expect(page.getByText("查看最近一次运行详情")).toBeVisible();
    await expect(page.getByRole("heading", { name: "运行历史" })).toBeVisible();
    await expect(page.getByText("重试历史")).toBeVisible();
  });

  test("handles notification bulk read and preferences", async ({
    page,
    request,
  }) => {
    await createNotificationFixture(request);
    await page.goto("/notifications");
    await expect(
      page.getByRole("heading", { name: "站内通知收件箱", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "通知偏好" })).toBeVisible();

    const inbox = page.locator("section").filter({
      has: page.getByRole("heading", { name: "通知队列" }),
    });
    await inbox.getByPlaceholder("搜索标题、正文、引用").fill("not-a-real-notification");
    await expect(inbox.getByText("暂无通知。")).toBeVisible();
    await inbox.getByPlaceholder("搜索标题、正文、引用").fill("");
    await inbox.getByRole("button", { name: "All", exact: true }).click();
    await expect(inbox.locator("article").first()).toBeVisible();
    await inbox.locator("select").selectOption("report_ready");
    await expect(inbox.locator("article").first()).toBeVisible();
    await inbox.locator("select").selectOption("all");
    await inbox.getByRole("button", { name: "Unread", exact: true }).click();

    await page.getByLabel("报告 站内通知").click();
    await page.getByRole("button", { name: "保存偏好" }).click();
    await expect(page.getByText("通知偏好已保存")).toBeVisible();

    const notificationCard = page
      .locator("article")
      .filter({ hasText: /unread/ })
      .first();
    await expect(notificationCard).toBeVisible();

    await notificationCard.getByLabel(/选择通知/).check({ force: true });
    await expect(page.getByText(/已选 1 条/)).toBeVisible();
    await page.getByRole("button", { name: "批量标记已读" }).click();
    await expect(
      page.getByText(/已标记 1 条通知为已读/),
    ).toBeVisible();
    if (!realApiMode) {
      await expect(
        page
          .locator("article")
          .filter({ hasText: "Data quality anomaly watch" }),
      ).toHaveCount(0);
    }
  });
});

test.describe("workflow planner local mock acceptance", () => {
  test.skip(realApiMode, "Workflow Planner fixture acceptance is mock-only.");
  test.beforeAll(() => {
    if (process.env.PLAYWRIGHT_BASE_URL) {
      throw new Error(
        "Workflow Planner fixture acceptance requires PLAYWRIGHT_BASE_URL to be unset so Playwright owns the local mock server.",
      );
    }
  });

  test("workflow planner periodic flow stays held with canonical catalog", async ({
    page,
  }) => {
    const externalRequests = await installLocalOnlyRequestGuard(page);
    await openPlannerFromDashboard(
      page,
      plannerProjects.canonicalHeld.name,
      "periodic_monitoring",
    );

    await page.goto("/dashboard");
    await page
      .getByTestId("workflow-planner-entry-cards")
      .getByRole("link", { name: /批量检索与解析/ })
      .click();
    await expect(page.locator("#planner-mode-batch_research")).toBeChecked();
    await page.getByRole("button", { name: "下一步" }).click();
    await page.locator("#planner-scope-0-canonical-term").fill("transient");
    await page.goto("/dashboard");
    await page
      .getByTestId("workflow-planner-entry-cards")
      .getByRole("link", { name: /创建监测项目/ })
      .click();
    await expect(
      page.locator("#planner-mode-periodic_monitoring"),
    ).toBeChecked();
    await page.getByRole("button", { name: "下一步" }).click();
    await expect(page.locator("#planner-scope-0-canonical-term")).toHaveValue(
      "",
    );

    await page.locator("#planner-scope-0-canonical-term").fill("Acme");
    await page.getByRole("button", { name: "添加 Scope" }).click();
    await page.locator("#planner-scope-1-type").selectOption("category");
    await page.locator("#planner-scope-1-canonical-term").fill("running shoes");
    await page.getByRole("button", { name: "下一步" }).click();
    await page.locator("#planner-platform-reddit").check();
    await page.locator("#planner-schedule-cadence").selectOption("daily");
    await page.locator("#planner-schedule-timezone").fill("Asia/Shanghai");
    await page.getByRole("button", { name: "下一步" }).click();
    await generatePlannerPreview(page);

    const planningStatusCard = page
      .getByText("Planning status", { exact: true })
      .locator("..");
    await expect(
      planningStatusCard.getByText("held", { exact: true }),
    ).toBeVisible();
    await expect(
      page.locator('[data-project-filter-applied="true"]'),
    ).toBeVisible();
    const fingerprint = page.getByTestId("workflow-planner-fingerprint");
    await expect(fingerprint).toHaveText(/^sha256:[0-9a-f]{64}$/);
    const simpleFingerprint = await fingerprint.textContent();
    expect(simpleFingerprint).not.toBeNull();
    await page.getByRole("tab", { name: "高级视图" }).click();
    await expect(page.getByTestId("workflow-planner-primary")).toHaveCount(0);
    await expect(fingerprint).toHaveText(simpleFingerprint!);
    await expect(page.locator('[role="tabpanel"]:not([hidden])')).toContainText(
      "execution_authorized=false",
    );

    await page.getByTestId("global-project-selector").selectOption({
      label: plannerProjects.syntheticPartial.name,
    });
    await expect(
      page.locator('[data-project-filter-applied="false"]'),
    ).toBeVisible();
    expect(externalRequests()).toEqual([]);
  });

  test("workflow planner batch flow preserves unclassified seed url", async ({
    page,
  }) => {
    const externalRequests = await installLocalOnlyRequestGuard(page);
    const externalSeedUrl = "https://outside-seed.example/items/42";
    await openPlannerFromDashboard(
      page,
      plannerProjects.canonicalHeld.name,
      "batch_research",
    );
    await advanceBatchPlanner(page, "running shoes", externalSeedUrl);
    await generatePlannerPreview(page);

    await expect(
      page.getByTestId("workflow-planner-unclassified-url"),
    ).toContainText(externalSeedUrl);
    const fingerprint = page.getByTestId("workflow-planner-fingerprint");
    await expect(fingerprint).toHaveText(/^sha256:[0-9a-f]{64}$/);
    const firstFingerprint = await fingerprint.textContent();
    expect(firstFingerprint).not.toBeNull();
    await regeneratePlannerPreview(page);
    await expect(fingerprint).toHaveText(firstFingerprint!);
    await expect(
      page.locator('[data-project-filter-applied="true"]'),
    ).toBeVisible();
    expect(externalRequests()).toEqual([]);
  });

  test("workflow planner renders synthetic resolved primary fallback and shadow", async ({
    page,
  }) => {
    const externalRequests = await installLocalOnlyRequestGuard(page);
    await openPlannerFromDashboard(
      page,
      plannerProjects.syntheticResolved.name,
      "batch_research",
    );
    await advanceBatchPlanner(page, "running shoes");
    await generatePlannerPreview(page);

    const simpleTab = page.getByRole("tab", { name: "简单视图" });
    await simpleTab.focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("tab", { name: "高级视图" })).toBeFocused();
    await expect(page.getByRole("tab", { name: "高级视图" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.getByTestId("workflow-planner-primary")).toBeVisible();
    await expect(page.getByTestId("workflow-planner-fallback")).toBeVisible();
    await expect(page.getByTestId("workflow-planner-shadow")).toBeVisible();
    await expect(page.locator('[role="tabpanel"]:not([hidden])')).toContainText(
      "execution_authorized=false",
    );

    await page.getByRole("button", { name: "上一步" }).click();
    await page.getByRole("button", { name: "上一步" }).click();
    await page.getByRole("button", { name: "上一步" }).click();
    await page.locator("#planner-mode-periodic_monitoring").check();
    await expect(
      page.locator('[data-project-filter-applied="false"]'),
    ).toBeVisible();
    expect(externalRequests()).toEqual([]);
  });

  test("workflow planner marks preview stale and ignores older response", async ({
    page,
  }) => {
    const externalRequests = await installLocalOnlyRequestGuard(page);
    await openPlannerFromDashboard(
      page,
      plannerProjects.syntheticResolved.name,
      "batch_research",
    );
    await advanceBatchPlanner(page, "e2e-slow-first");
    await page.clock.install();
    await page.clock.pauseAt(Date.now());

    await page.getByTestId("workflow-planner-generate-preview").click();
    await expect(
      page.getByTestId("workflow-planner-generate-preview"),
    ).toHaveAttribute("aria-busy", "true");
    await expect(
      page.locator('[data-project-filter-applied="false"]'),
    ).toBeVisible();
    await page.getByRole("button", { name: "上一步" }).click();
    await page.getByRole("button", { name: "上一步" }).click();
    await page
      .locator("#planner-scope-0-canonical-term")
      .fill("e2e-fast-second");
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByTestId("workflow-planner-generate-preview").click();
    await page.clock.fastForward(10);

    const newestFingerprint = `sha256:${"2".repeat(64)}`;
    await expect(page.getByTestId("workflow-planner-fingerprint")).toHaveText(
      newestFingerprint,
    );
    await expect(
      page.locator('[data-project-filter-applied="true"]'),
    ).toBeVisible();
    await page.clock.fastForward(240);
    await expect(page.getByTestId("workflow-planner-fingerprint")).toHaveText(
      newestFingerprint,
    );

    await page.getByRole("button", { name: "上一步" }).click();
    await page.getByRole("button", { name: "上一步" }).click();
    await page
      .locator("#planner-scope-0-canonical-term")
      .fill("post-preview-edit");
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByRole("button", { name: "下一步" }).click();
    await expect(page.getByTestId("workflow-planner-stale")).toBeVisible();
    await expect(
      page.locator('[data-project-filter-applied="false"]'),
    ).toBeVisible();
    expect(externalRequests()).toEqual([]);
  });

  test("workflow plan persistence saves held v1, preserves no-op, and compares v2", async ({
    page,
  }, testInfo) => {
    await page.setViewportSize(
      testInfo.project.name === "mobile"
        ? { width: 375, height: 812 }
        : { width: 1440, height: 900 },
    );
    const externalRequests = await installLocalOnlyRequestGuard(page);
    const planName = `E2E held persistence ${testInfo.project.name}`;
    const firstTerm = "e2e-held-persistence-v1";
    const secondTerm = "e2e-held-persistence-v2";

    await openPlannerFromDashboard(
      page,
      plannerProjects.canonicalHeld.name,
      "batch_research",
    );
    await advanceBatchPlanner(page, firstTerm);
    await generatePlannerPreview(page);

    const firstSavePanel = page.getByTestId("workflow-plan-save-panel");
    await expect(firstSavePanel).toContainText(
      "held Preview 可以保存，但保存不会解除阻断、批准或启动运行。",
    );
    await expectNoForbiddenWorkflowActions(
      page.getByTestId("workflow-planner-workspace"),
    );
    await page.locator("#workflow-plan-name").fill(planName);
    await page.getByTestId("workflow-plan-save").click();
    await expect(firstSavePanel).toContainText("已创建 Plan 与 Version v1。");
    await expectNoDocumentOverflow(page);

    await openSavedWorkflowPlan(page, planName, 1);
    const firstDetail = page.getByTestId("workflow-plan-detail-workspace");
    await expect(
      firstDetail.getByRole("heading", { name: planName }),
    ).toBeVisible();
    await expect(firstDetail).toContainText("当前 v1");
    const firstHistory = page.getByTestId("workflow-plan-version-history");
    await expect(firstHistory).toContainText("已加载 1 / 1");
    await expect(
      firstHistory.getByRole("heading", { name: "v1", exact: true }),
    ).toBeVisible();
    const firstCompare = page.getByTestId("workflow-plan-version-compare");
    await expect(firstCompare).toContainText(
      "至少需要 2 个 Version 才能比较。",
    );
    await expectNoForbiddenWorkflowActions(firstDetail);
    await expectNoDocumentOverflow(page);

    await firstDetail.getByRole("link", { name: "Edit in Planner" }).click();
    await expect(page).toHaveURL(/\/automation\/planner\?/);
    const workspace = page.getByTestId("workflow-planner-workspace");
    await expect(workspace).toContainText(`${planName} · 当前基线 v1`);
    await page.getByRole("button", { name: "下一步" }).click();
    await expect(page.locator("#planner-scope-0-canonical-term")).toHaveValue(
      firstTerm,
    );
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByRole("button", { name: "下一步" }).click();
    await generatePlannerPreview(page);
    const noOpSavePanel = page.getByTestId("workflow-plan-save-panel");
    await page.getByTestId("workflow-plan-save").click();
    await expect(noOpSavePanel).toContainText("语义未变化，未创建新 Version。");

    await page.getByRole("button", { name: "上一步" }).click();
    await page.getByRole("button", { name: "上一步" }).click();
    await page.locator("#planner-scope-0-canonical-term").fill(secondTerm);
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByRole("button", { name: "下一步" }).click();
    await expect(page.getByTestId("workflow-planner-stale")).toBeVisible();
    await expect(page.getByTestId("workflow-plan-save")).toHaveCount(0);
    await generatePlannerPreview(page);
    const secondSavePanel = page.getByTestId("workflow-plan-save-panel");
    await page.getByTestId("workflow-plan-save").click();
    await expect(secondSavePanel).toContainText("已创建 Version v2。");

    await openSavedWorkflowPlan(page, planName, 2);
    const secondDetail = page.getByTestId("workflow-plan-detail-workspace");
    await expect(secondDetail).toContainText("当前 v2");
    const secondHistory = page.getByTestId("workflow-plan-version-history");
    await expect(secondHistory).toContainText("已加载 2 / 2");
    await expect(
      secondHistory.getByRole("heading", { name: "v2", exact: true }),
    ).toBeVisible();
    await expect(
      secondHistory.getByRole("heading", { name: "v1", exact: true }),
    ).toBeVisible();
    const secondCompare = page.getByTestId("workflow-plan-version-compare");
    await expect(
      secondCompare.getByLabel("Base Version").locator("option:checked"),
    ).toContainText("v1");
    await expect(
      secondCompare.getByLabel("Target Version").locator("option:checked"),
    ).toContainText("v2");
    await expect(
      secondCompare.getByRole("heading", { name: "scopes", exact: true }),
    ).toBeVisible();
    await expect(secondCompare).not.toContainText("同一 Version，无差异。");
    await expectNoForbiddenWorkflowActions(secondDetail);
    await expectNoDocumentOverflow(page);
    expect(externalRequests()).toEqual([]);
  });

  test("workflow plan persistence guards dirty same-origin navigation", async ({
    page,
  }) => {
    const externalRequests = await installLocalOnlyRequestGuard(page);
    const dirtyTerm = "e2e-dirty-navigation";
    await openPlannerFromDashboard(
      page,
      plannerProjects.canonicalHeld.name,
      "batch_research",
    );
    await page.getByRole("button", { name: "下一步" }).click();
    await page.locator("#planner-scope-0-canonical-term").fill(dirtyTerm);

    const dismissed = new Promise<void>((resolve) => {
      page.once("dialog", async (dialog) => {
        expect(dialog.message()).toBe(
          "当前 Workflow Planner 有未保存变更，确定离开吗？",
        );
        await dialog.dismiss();
        resolve();
      });
    });
    await navigateWithPrimaryNavigation(page, "已保存计划");
    await dismissed;
    await expect(page).toHaveURL(/\/automation\/planner\?/);
    await expect(page.locator("#planner-scope-0-canonical-term")).toHaveValue(
      dirtyTerm,
    );

    const accepted = new Promise<void>((resolve) => {
      page.once("dialog", async (dialog) => {
        expect(dialog.message()).toBe(
          "当前 Workflow Planner 有未保存变更，确定离开吗？",
        );
        await dialog.accept();
        resolve();
      });
    });
    await navigateWithPrimaryNavigation(page, "已保存计划");
    await accepted;
    await expect(page).toHaveURL(/\/automation\/plans$/);
    expect(externalRequests()).toEqual([]);
  });

  test("workflow plan persistence preserves draft across save-time stale and conflict", async ({
    page,
  }, testInfo) => {
    const externalRequests = await installLocalOnlyRequestGuard(page);
    const planName = `E2E conflict persistence ${testInfo.project.name}`;
    await openPlannerFromDashboard(
      page,
      plannerProjects.syntheticResolved.name,
      "batch_research",
    );
    await advanceBatchPlanner(page, "e2e-save-error-baseline");
    await generatePlannerPreview(page);
    await page.locator("#workflow-plan-name").fill(planName);
    await page.getByTestId("workflow-plan-save").click();
    await expect(page.getByTestId("workflow-plan-save-panel")).toContainText(
      "已创建 Plan 与 Version v1。",
    );

    await page.getByRole("button", { name: "上一步" }).click();
    await page.getByRole("button", { name: "上一步" }).click();
    await page
      .locator("#planner-scope-0-canonical-term")
      .fill("e2e-preview-stale-save");
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByRole("button", { name: "下一步" }).click();
    await generatePlannerPreview(page);
    await page.getByTestId("workflow-plan-save").click();
    await expect(
      page.getByText(
        "Preview 已过期；已保留草稿，请重新生成 Preview 后再保存。",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(page.getByTestId("workflow-planner-stale")).toBeVisible();
    await expect(page.getByTestId("workflow-plan-save")).toHaveCount(0);
    await page.getByRole("button", { name: "上一步" }).click();
    await page.getByRole("button", { name: "上一步" }).click();
    await expect(page.locator("#planner-scope-0-canonical-term")).toHaveValue(
      "e2e-preview-stale-save",
    );

    await page
      .locator("#planner-scope-0-canonical-term")
      .fill("e2e-version-conflict-save");
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByRole("button", { name: "下一步" }).click();
    await generatePlannerPreview(page);
    await page.getByTestId("workflow-plan-save").click();
    await expect(
      page.getByText(
        "当前 Version 已推进；已刷新并发基线，保留本地草稿，未自动合并或重提。请重新生成 Preview。",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(page.getByTestId("workflow-planner-workspace")).toContainText(
      `${planName} · 当前基线 v2`,
    );
    await expect(page.getByTestId("workflow-plan-save")).toHaveCount(0);
    await page.getByRole("button", { name: "上一步" }).click();
    await page.getByRole("button", { name: "上一步" }).click();
    await expect(page.locator("#planner-scope-0-canonical-term")).toHaveValue(
      "e2e-version-conflict-save",
    );

    const accepted = new Promise<void>((resolve) => {
      page.once("dialog", async (dialog) => {
        expect(dialog.message()).toBe(
          "当前 Workflow Planner 有未保存变更，确定离开吗？",
        );
        await dialog.accept();
        resolve();
      });
    });
    const opened = openSavedWorkflowPlan(page, planName, 2);
    await accepted;
    await opened;
    const currentPreview = page.getByRole("region", {
      name: "当前 Version Preview",
    });
    await expect(currentPreview).toContainText("e2e-version-conflict-remote");
    await expect(currentPreview).not.toContainText("e2e-version-conflict-save");
    const history = page.getByTestId("workflow-plan-version-history");
    await expect(history).toContainText("已加载 2 / 2");
    await expect(
      history.getByRole("heading", { name: "v3", exact: true }),
    ).toHaveCount(0);
    expect(externalRequests()).toEqual([]);
  });

  test("project selection syncs in same tab and across tabs", async ({
    page,
  }, testInfo) => {
    test.skip(
      testInfo.project.name === "mobile",
      "Cross-tab storage synchronization is desktop-only in this suite.",
    );
    const firstExternalRequests = await installLocalOnlyRequestGuard(page);
    const secondPage = await page.context().newPage();
    const secondExternalRequests =
      await installLocalOnlyRequestGuard(secondPage);
    await openPlannerWithoutSelection(page, "batch_research");
    await openPlannerWithoutSelection(secondPage, "periodic_monitoring");
    const partialId = plannerProjects.syntheticPartial.id;
    await expect(
      page
        .getByTestId("global-project-selector")
        .locator(`option[value="${partialId}"]`),
    ).toBeAttached();
    await expect(
      secondPage
        .getByTestId("global-project-selector")
        .locator(`option[value="${partialId}"]`),
    ).toBeAttached();

    await page.getByTestId("global-project-selector").selectOption(partialId);
    await expect(page.getByTestId("global-project-selector")).toHaveValue(
      partialId,
    );
    await expect(page.getByTestId("workflow-planner-workspace")).toContainText(
      plannerProjects.syntheticPartial.name,
    );
    await expect(secondPage.getByTestId("global-project-selector")).toHaveValue(
      partialId,
    );
    await expect(
      secondPage.getByTestId("workflow-planner-workspace"),
    ).toContainText(plannerProjects.syntheticPartial.name);
    await expect(
      page.locator('[data-project-filter-applied="false"]'),
    ).toBeVisible();
    await expect(
      secondPage.locator('[data-project-filter-applied="false"]'),
    ).toBeVisible();
    expect(firstExternalRequests()).toEqual([]);
    expect(secondExternalRequests()).toEqual([]);
    await secondPage.close();
  });

  test("workflow planner focuses first invalid field", async ({ page }) => {
    const externalRequests = await installLocalOnlyRequestGuard(page);
    await openPlannerFromDashboard(
      page,
      plannerProjects.canonicalHeld.name,
      "periodic_monitoring",
    );
    const next = page.getByRole("button", { name: "下一步" });
    await next.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#planner-scope-0-canonical-term")).toBeVisible();
    await page.getByRole("button", { name: "下一步" }).focus();
    await page.keyboard.press("Enter");
    await expect
      .poll(() => page.evaluate(() => document.activeElement?.id))
      .toBe("planner-scope-0-canonical-term");
    await expect(
      page.locator("#planner-scope-0-canonical-term"),
    ).toHaveAttribute("aria-invalid", "true");
    expect(externalRequests()).toEqual([]);
  });

  test("workflow planner has no horizontal overflow at 375 and 1440", async ({
    page,
  }) => {
    const externalRequests = await installLocalOnlyRequestGuard(page);
    for (const viewport of [
      { width: 375, height: 812 },
      { width: 1440, height: 900 },
    ]) {
      await page.setViewportSize(viewport);
      await openPlannerFromDashboard(
        page,
        plannerProjects.syntheticResolved.name,
        "batch_research",
      );
      await advanceBatchPlanner(page, "running shoes");
      await generatePlannerPreview(page);
      const simpleOverflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      );
      expect(simpleOverflow).toBeLessThanOrEqual(1);
      await page.getByRole("tab", { name: "高级视图" }).click();
      const advancedOverflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      );
      expect(advancedOverflow).toBeLessThanOrEqual(1);
    }
    expect(externalRequests()).toEqual([]);
  });
});

test("capability market switches views and opens evidence detail", async ({
  page,
}, testInfo) => {
  await page.setViewportSize(
    testInfo.project.name === "mobile"
      ? { width: 375, height: 812 }
      : { width: 1440, height: 900 },
  );

  const blockedOrigins: string[] = [];
  await page.route("**/*", async (route) => {
    const requestUrl = new URL(route.request().url());
    if (
      (requestUrl.protocol === "http:" || requestUrl.protocol === "https:") &&
      requestUrl.hostname !== "localhost" &&
      requestUrl.hostname !== "127.0.0.1"
    ) {
      blockedOrigins.push(requestUrl.origin);
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });

  await page.goto("/api-market?view=scenarios&project_id=p1");
  await expect(page.getByRole("heading", { name: "能力市场" })).toBeVisible();
  const scenarioCards = page.getByTestId("capability-scenario");
  await expect(scenarioCards).toHaveCount(8);
  await expect(
    scenarioCards.getByText("候选，尚不可执行", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    scenarioCards.getByText("L2-fixture", { exact: true }).first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "矩阵视图" }).click();
  await expect(page).toHaveURL(/\/api-market\?(?=.*view=matrix)(?=.*project_id=p1)/);

  const visibleMatrixCells = page.locator(
    '[data-testid="capability-matrix-cell"]:visible',
  );
  if (testInfo.project.name === "mobile") {
    const platformSelect = page.getByTestId("capability-platform-select");
    await expect(platformSelect.locator("option")).toHaveCount(7);
    for (const platform of [
      "youtube",
      "reddit",
      "x",
      "instagram",
      "threads",
      "tiktok",
      "linkedin",
    ]) {
      await platformSelect.selectOption(platform);
      await expect(visibleMatrixCells).toHaveCount(6);
    }
    await platformSelect.selectOption("youtube");
  } else {
    await expect(visibleMatrixCells).toHaveCount(42);
    const dimensions = await visibleMatrixCells.evaluateAll((cells) =>
      cells.map((cell) => {
        const box = cell.getBoundingClientRect();
        return { height: box.height, width: box.width };
      }),
    );
    const widths = dimensions.map(({ width }) => width);
    const heights = dimensions.map(({ height }) => height);
    expect(Math.max(...widths) - Math.min(...widths)).toBeLessThan(2);
    expect(Math.max(...heights) - Math.min(...heights)).toBeLessThan(2);
  }

  const officialYoutubeCell = page.locator(
    '[data-testid="capability-matrix-cell"][data-platform="youtube"][data-access-channel="official_authorized_api"]:visible',
  );
  await officialYoutubeCell.click();
  const detailDialog = page.getByRole("dialog", { name: "能力详情" });
  await expect(detailDialog).toBeVisible();
  await expect(
    detailDialog.getByText("候选，尚不可执行", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    detailDialog.getByText("provider_call=false", { exact: true }),
  ).toBeVisible();
  await expect(detailDialog.getByText("youtube.v3", { exact: true }).first()).toBeVisible();
  await expect(detailDialog.getByRole("heading", { name: "Evidence" })).toBeVisible();
  await expect(
    detailDialog.getByRole("link", { name: /Fixture Review/ }).first(),
  ).toBeVisible();
  const detailCloseButton = detailDialog.getByRole("button", {
    name: "关闭能力详情",
  });
  await expect(detailCloseButton).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(detailDialog.locator(":focus")).toHaveCount(1);
  await page.keyboard.press("Tab");
  await expect(detailCloseButton).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(detailDialog).toHaveCount(0);
  await expect(officialYoutubeCell).toBeFocused();

  await page.getByRole("button", { name: "列表视图" }).click();
  await page.getByTestId("capability-filter-platform").selectOption("reddit");
  await expect(page).toHaveURL(/\/api-market\?(?=.*view=list)(?=.*platform=reddit)(?=.*project_id=p1)/);
  await page.reload();
  await expect(page.getByTestId("capability-filter-platform")).toHaveValue("reddit");
  await expect(page.locator('article[data-implementation-id="reddit.praw"]')).toHaveCount(1);
  await expect(page.locator("[data-implementation-id]")).toHaveCount(1);
  const redditCard = page.locator('article[data-implementation-id="reddit.praw"]');
  await expect(
    redditCard.getByText("候选，尚不可执行", { exact: true }),
  ).toBeVisible();
  await expect(redditCard.getByText("L2-fixture", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "比较实现" })).toBeDisabled();
  await expect(
    page.getByText("当前平台只有一个实现，暂无可比较项", { exact: true }),
  ).toBeVisible();

  await page.goto("/api-market/youtube-v3-commentthreads-list");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "YouTube Comment Threads",
    }),
  ).toBeVisible();
  await expect(page.getByText("provider_call=false", { exact: true }).first()).toBeVisible();
  expect(blockedOrigins).toEqual([]);
});

test.describe("mobile layout guard", () => {
  for (const route of [
    "/reports",
    "/alerts",
    "/notifications",
    "/tasks",
    "/sources",
    "/datasets",
    "/automation",
    "/api-market",
    "/api-market/youtube-v3-commentthreads-list",
  ]) {
    test(`${route} does not overflow horizontally`, async ({
      page,
    }, testInfo) => {
      test.skip(
        testInfo.project.name !== "mobile",
        "mobile-only layout assertion",
      );
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await page.locator("main").waitFor({ state: "visible" });
      const overflow = await page.evaluate(() => {
        return (
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth
        );
      });
      expect(overflow).toBeLessThanOrEqual(1);
    });
  }
});

test("six-entry navigation is complete on desktop and mobile", async ({
  page,
}, testInfo) => {
  const mobile = testInfo.project.name === "mobile";
  await page.setViewportSize(
    mobile ? { width: 375, height: 812 } : { width: 1440, height: 900 },
  );

  const blockedOrigins: string[] = [];
  await page.route("**/*", async (route) => {
    const requestUrl = new URL(route.request().url());
    if (
      (requestUrl.protocol === "http:" || requestUrl.protocol === "https:") &&
      requestUrl.hostname !== "localhost" &&
      requestUrl.hostname !== "127.0.0.1"
    ) {
      blockedOrigins.push(requestUrl.origin);
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });

  await page.goto("/dashboard");
  expect(["localhost", "127.0.0.1"]).toContain(new URL(page.url()).hostname);

  if (mobile) {
    const opener = page.getByRole("button", { name: "打开导航" });
    await opener.click();
    const drawer = page.getByRole("dialog", { name: "移动主导航" });
    const closeButton = drawer.getByRole("button", { name: "关闭导航" });
    await expect(drawer).toHaveAttribute("aria-modal", "true");
    await expect(
      page.getByRole("button", { name: "关闭导航遮罩" }),
    ).toHaveAttribute("tabindex", "-1");
    await expect(drawer.getByTestId("mobile-primary-nav-link")).toHaveCount(6);
    await expect(drawer.getByRole("link", { name: "采集工具库" })).toBeVisible();
    await expect(closeButton).toBeFocused();

    await page.keyboard.press("Shift+Tab");
    await expect(
      drawer.getByRole("link", { name: "能力市场", exact: true }),
    ).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(closeButton).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    await expect(opener).toBeFocused();
    await opener.click();
    await page
      .getByRole("dialog", { name: "移动主导航" })
      .getByRole("link", { name: "数据资产", exact: true })
      .click();
    await expect(page).toHaveURL(/\/datasets$/);
  } else {
    const primaryLinks = page.getByTestId("primary-nav-link");
    await expect(primaryLinks).toHaveCount(6);
    await expect(primaryLinks).toHaveText([
      "工作台",
      "监测项目",
      "采集工作流",
      "数据资产",
      "洞察与交付",
      "能力市场",
    ]);
    await expect(
      page.getByRole("link", { name: "工作台", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await page.getByRole("link", { name: "能力市场", exact: true }).click();
    await expect(page).toHaveURL(/\/api-market(?:\?.*)?$/);
  }

  const selector = page.getByTestId("global-project-selector");
  await expect(selector.locator("option").nth(1)).toBeAttached();
  const projectId = await selector.locator("option").nth(1).getAttribute("value");
  expect(projectId).toBeTruthy();
  await selector.selectOption(projectId!);
  await page.reload();
  await expect(page.getByTestId("global-project-selector")).toHaveValue(
    projectId!,
  );
  await expect(
    page.getByText("当前页面未应用项目过滤（全局数据）"),
  ).toBeVisible();
  await expect(page.locator('[data-project-filter-applied="false"]')).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() =>
        Object.entries(window.localStorage).filter(([key]) =>
          key.startsWith("data-intelligence-hub:selected-project"),
        ),
      ),
    )
    .toEqual([["data-intelligence-hub:selected-project-id", projectId]]);

  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  expect(blockedOrigins).toEqual([]);
});
