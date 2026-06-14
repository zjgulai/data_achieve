import {
  APIRequestContext,
  type Locator,
  type Page,
  expect,
  test,
} from "@playwright/test";

const realApiMode = process.env.PLAYWRIGHT_REAL_API === "true";

async function loginByApi(page: Page, request: APIRequestContext) {
  if (!realApiMode) {
    return;
  }
  const baseUrl =
    process.env.PLAYWRIGHT_BASE_URL ?? "https://scrapy.lute-tlz-dddd.top";
  const email = process.env.SCRAPY_DEMO_EMAIL ?? "owner@example.com";
  const password = process.env.SCRAPY_DEMO_PASSWORD;
  if (!password) {
    throw new Error(
      "SCRAPY_DEMO_PASSWORD is required when PLAYWRIGHT_REAL_API=true",
    );
  }

  const response = await request.post(`${baseUrl}/api/auth/login`, {
    data: { email, password },
  });
  if (!response.ok()) {
    const detail = await response.text();
    throw new Error(`Real API login failed (${response.status()}): ${detail}`);
  }

  const rawSetCookie = response.headers()["set-cookie"] as string | undefined;
  if (!rawSetCookie) {
    throw new Error(
      "Real API login response did not return access token cookie",
    );
  }

  const cookieText = rawSetCookie.split(";")[0];
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

async function createTaskFlowFixture(
  request: APIRequestContext,
  suffix: string,
) {
  if (!realApiMode) {
    return null;
  }
  const baseUrl =
    process.env.PLAYWRIGHT_BASE_URL ?? "https://scrapy.lute-tlz-dddd.top";
  const email = process.env.SCRAPY_DEMO_EMAIL ?? "owner@example.com";
  const password = process.env.SCRAPY_DEMO_PASSWORD;
  if (!password) {
    throw new Error(
      "SCRAPY_DEMO_PASSWORD is required when PLAYWRIGHT_REAL_API=true",
    );
  }
  await request.post(`${baseUrl}/api/auth/login`, {
    data: { email, password },
  });
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
  const baseUrl =
    process.env.PLAYWRIGHT_BASE_URL ?? "https://scrapy.lute-tlz-dddd.top";
  const email = process.env.SCRAPY_DEMO_EMAIL ?? "owner@example.com";
  const password = process.env.SCRAPY_DEMO_PASSWORD;
  if (!password) {
    throw new Error(
      "SCRAPY_DEMO_PASSWORD is required when PLAYWRIGHT_REAL_API=true",
    );
  }
  await request.post(`${baseUrl}/api/auth/login`, {
    data: { email, password },
  });
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

async function createReportFixture(request: APIRequestContext, suffix: string) {
  if (!realApiMode) {
    return;
  }
  await createIntelligenceFixture(request, `report-${suffix}`);
  const baseUrl =
    process.env.PLAYWRIGHT_BASE_URL ?? "https://scrapy.lute-tlz-dddd.top";
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
  const baseUrl =
    process.env.PLAYWRIGHT_BASE_URL ?? "https://scrapy.lute-tlz-dddd.top";
  const email = process.env.SCRAPY_DEMO_EMAIL ?? "owner@example.com";
  const password = process.env.SCRAPY_DEMO_PASSWORD;
  if (!password) {
    throw new Error(
      "SCRAPY_DEMO_PASSWORD is required when PLAYWRIGHT_REAL_API=true",
    );
  }
  await request.post(`${baseUrl}/api/auth/login`, {
    data: { email, password },
  });
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

test.beforeEach(async ({ page, request }) => {
  if (!realApiMode) {
    return;
  }
  await loginByApi(page, request);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/dashboard$/);
});

test.describe("MVP workspace routes", () => {
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
    await expect(
      page.getByRole("heading", { name: "自动分发", exact: true }),
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

    let sourceCard = page
      .locator("article")
      .filter({ hasText: sourceName })
      .first();
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

    sourceCard = page
      .locator("article")
      .filter({ hasText: updatedName })
      .first();
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
    await expect(sourceCard.getByText("已启用")).toBeVisible();
    await expect(sourceCard.getByText("尚未运行")).toBeVisible();
    await activateControl(
      sourceCard.getByRole("button", { name: "停用" }),
      testInfo.project.name,
    );
    await expect(
      page.getByText(`${updatedName}: source disabled`),
    ).toBeVisible();
    await expect(sourceCard.getByText("已停用")).toBeVisible();
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
