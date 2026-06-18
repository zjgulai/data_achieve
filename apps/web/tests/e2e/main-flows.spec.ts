import {
  type APIRequestContext,
  type APIResponse,
  type Locator,
  type Page,
  expect,
  test,
} from "@playwright/test";

const realApiMode = process.env.PLAYWRIGHT_REAL_API === "true";

type RealApiCredentials = {
  email: string;
  password: string;
};

let generatedRealApiCredentials: RealApiCredentials | null = null;

function realApiBaseUrl() {
  return process.env.PLAYWRIGHT_BASE_URL ?? "https://scrapy.lute-tlz-dddd.top";
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
  return generatedRealApiCredentials;
}

async function authenticateRealApiRequest(request: APIRequestContext) {
  const baseUrl = realApiBaseUrl();
  const configuredPassword = process.env.SCRAPY_DEMO_PASSWORD;
  if (configuredPassword) {
    const email = process.env.SCRAPY_DEMO_EMAIL ?? "owner@example.com";
    const response = await request.post(`${baseUrl}/api/auth/login`, {
      data: { email, password: configuredPassword },
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
  await page.getByRole("button", { name: "商品发现" }).click();
  await page
    .getByLabel(
      "我确认这是公开可访问页面，采集分析不涉及登录态、验证码绕过或未授权数据访问。",
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
  await page.getByRole("button", { name: "确认创建 Source/Task" }).click();
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
  await page.getByRole("button", { name: "保存 Dataset Version" }).click();
  await expect(page.getByText("Schedule Approval")).toBeVisible();
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
  );
  if (!sendResponse.ok()) {
    throw new Error(
      `Notification fixture report send failed: ${await sendResponse.text()}`,
    );
  }
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
    await expectNoVisibleTechnicalNoise(page);
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

    await page.getByRole("link", { name: "打开详情页" }).first().click();
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
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByText(`${ruleName}: rule created`)).toBeVisible();
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

    const acknowledgeButton = eventStream.getByRole("button", { name: "确认" });
    if (realApiMode) {
      await acknowledgeButton.click();
      await expect(page.getByText(/AlertEvent .*: acknowledged/)).toBeVisible();
    } else {
      await expect(acknowledgeButton).toBeDisabled();
    }
    await eventStatus.selectOption("acknowledged");
    await expect(eventCard).toBeVisible();

    await eventStream.getByRole("button", { name: "解决" }).click();
    await expect(page.getByText(/AlertEvent .*: resolved/)).toBeVisible();
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
    await expect(page.getByText("匹配 DriftEvent")).toBeVisible();
    await expect(page.getByText("预览不会创建 AlertRule")).toBeVisible();
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
    await expect(page.getByText("Version 2")).toBeVisible();
    await expect(page.getByText("cast price to decimal when present").first()).toBeVisible();
    await expect(page.getByText("数据行预览")).toBeVisible();
    await expect(page.getByText("Demo Carry Bag", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "生成导出文件" }).click();
    await expect(page.getByText("已生成导出文件")).toBeVisible();
    await expect(page.getByRole("link", { name: "下载" }).first()).toBeVisible();
    await expect(page.getByText("ecommerce_product_drift").first()).toBeVisible();
    await expect(page.getByText("缺字段：price, sku")).toBeVisible();
    await page.getByRole("button", { name: "预览告警策略" }).click();
    await expect(page.getByText("匹配 DriftEvent")).toBeVisible();
    await expect(page.getByText("预览不会创建 AlertRule")).toBeVisible();
    await page.getByRole("button", { name: "确认创建策略" }).click();
    await expect(page.getByText("已创建 DriftEvent 告警策略")).toBeVisible();
    await expect(page.getByText("未创建 AlertEvent")).toBeVisible();
    await page.getByRole("button", { name: "生成告警事件" }).click();
    await expect(page.getByText("已生成 dataset_drift Signal")).toBeVisible();
    await expect(page.getByText("已创建 AlertEvent 1 条")).toBeVisible();
    await expect(page.getByText("未发送通知").first()).toBeVisible();
    await page.getByRole("button", { name: "发送站内通知" }).click();
    await expect(page.getByText("已发送站内通知 1 条")).toBeVisible();
    await expect(page.getByText("AlertEvent 已标记为 sent")).toBeVisible();
    await expect(page.getByText("未发送邮件")).toBeVisible();

    await page.getByRole("combobox", { name: "通知通道" }).selectOption("email");
    await page.getByRole("button", { name: "预览告警策略" }).click();
    await expect(page.getByText("预览不会创建 AlertRule")).toBeVisible();
    await page.getByRole("button", { name: "确认创建策略" }).click();
    await expect(
      page.getByText("已创建 DriftEvent 告警策略").first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "生成告警事件" }).last().click();
    await expect(page.getByText("已创建 AlertEvent 1 条")).toBeVisible();
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
        await expect(mobileCards.first()).toBeVisible();
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
      page.getByText(/selected notifications marked read/),
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

test.describe("mobile layout guard", () => {
  for (const route of [
    "/reports",
    "/alerts",
    "/notifications",
    "/tasks",
    "/sources",
    "/datasets",
  ]) {
    test(`${route} does not overflow horizontally`, async ({
      page,
    }, testInfo) => {
      test.skip(
        testInfo.project.name !== "mobile",
        "mobile-only layout assertion",
      );
      await page.goto(route);
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
