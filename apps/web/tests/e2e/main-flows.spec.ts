import { expect, test } from "@playwright/test";

const realApiMode = process.env.PLAYWRIGHT_REAL_API === "true";

test.beforeEach(async ({ page }) => {
  if (!realApiMode) {
    return;
  }
  const email = process.env.SCRAPY_DEMO_EMAIL ?? "owner@example.com";
  const password = process.env.SCRAPY_DEMO_PASSWORD;
  if (!password) {
    throw new Error("SCRAPY_DEMO_PASSWORD is required when PLAYWRIGHT_REAL_API=true");
  }

  await page.goto("/login");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test.describe("MVP workspace routes", () => {
  test("renders dashboard and intelligence evidence flow", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "全局仪表盘" })).toBeVisible();
    await expect(page.getByText("情报总量")).toBeVisible();

    await page.goto("/intelligence");
    await expect(page.getByRole("heading", { name: "情报中心", exact: true })).toBeVisible();
    await expect(page.getByText("Intelligence 列表")).toBeVisible();
    if (realApiMode) {
      await expect(page.getByText("竞品价格 20% 下探").first()).toBeVisible();
    } else {
      await expect(page.getByText("openai/codex is showing accelerated traction").first()).toBeVisible();
    }
    await expect(page.getByText("Evidence Timeline")).toBeVisible();
    await expect(page.getByText("Task Run").first()).toBeVisible();
    await expect(page.getByText("Raw Record").first()).toBeVisible();
    await page.getByRole("link", { name: "打开详情页" }).click();
    await expect(page).toHaveURL(/\/intelligence\/.+/);
    await expect(page.getByText("Content Hash").first()).toBeVisible();
    await expect(page.getByText("查看原始数据").first()).toBeVisible();
  });

  test("generates and sends a report", async ({ page }) => {
    await page.goto("/reports");
    await expect(page.getByRole("heading", { name: "报告中心" })).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: realApiMode ? /Data Achieve 每日情报摘要/ : /AI Scrapy Tools 日报/,
      }),
    ).toBeVisible();
    await expect(page.getByLabel("生成项目")).toBeVisible();
    await expect(page.getByLabel("报告筛选项目")).toBeVisible();
    await expect(page.getByRole("heading", { name: "自动分发", exact: true })).toBeVisible();
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
    await expect(page.getByText("订阅已手动执行")).toBeVisible();
    await expect(page.getByText(/部分成功|成功/).first()).toBeVisible();
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
    const reportIntelligenceLink = page.locator('a[href^="/intelligence/"]').first();
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
    await page.getByRole("button", { name: "下载 Markdown", exact: true }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.md$/);

    await page.getByRole("button", { name: "生成日报", exact: true }).click();
    await expect(page.getByRole("heading", { name: "核心发现", exact: true })).toBeVisible();

    const reportDetail = page.locator("section").filter({ hasText: "派发状态" });
    await reportDetail.getByRole("button", { name: "发送报告", exact: true }).click();
    await expect(reportDetail.getByRole("button", { name: "已发送", exact: true })).toBeDisabled();
    await expect(reportDetail.getByText("报告已进入通知链路")).toBeVisible();
    await expect(reportDetail.getByText("报告发送").first()).toBeVisible();
  });

  test("creates alert rule and displays alert events", async ({ page }, testInfo) => {
    await page.goto("/alerts");
    await expect(page.getByRole("heading", { name: "预警中心" })).toBeVisible();
    await expect(page.getByText("预警事件流")).toBeVisible();
    const ruleCards = page.locator("article").filter({ hasText: "High severity signal" });
    if (!realApiMode) {
      await expect(ruleCards).toHaveCount(1);
      await expect(page.getByRole("heading", { name: "page_changed" })).toBeVisible();
    }

    const ruleName = `High severity signal ${testInfo.project.name} ${Date.now()}`;
    await page.getByLabel("规则名称").fill(ruleName);
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByText(`${ruleName}: rule created`)).toBeVisible();
    await expect(page.locator("article").filter({ hasText: ruleName })).toHaveCount(1);
  });

  test("marks unread notifications as read", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "站内通知收件箱", exact: true })).toBeVisible();

    const notificationCard = realApiMode
      ? page.locator("article").filter({ hasText: /日报已生成|价格告警已触发/ }).first()
      : page.locator("article").filter({ hasText: "Data quality anomaly watch" }).first();
    await expect(notificationCard).toBeVisible();

    await notificationCard.getByRole("button", { name: "Read", exact: true }).click();
    await expect(page.getByText(/marked read/)).toBeVisible();
    if (!realApiMode) {
      await expect(page.locator("article").filter({ hasText: "Data quality anomaly watch" })).toHaveCount(0);
    }
  });
});

test.describe("mobile layout guard", () => {
  for (const route of ["/reports", "/alerts", "/notifications"]) {
    test(`${route} does not overflow horizontally`, async ({ page }, testInfo) => {
      test.skip(testInfo.project.name !== "mobile", "mobile-only layout assertion");
      await page.goto(route);
      const overflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth - document.documentElement.clientWidth;
      });
      expect(overflow).toBeLessThanOrEqual(1);
    });
  }
});
