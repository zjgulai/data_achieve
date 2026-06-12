import { expect, test } from "@playwright/test";

test.describe("MVP workspace routes", () => {
  test("renders dashboard and intelligence evidence flow", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "全局仪表盘" })).toBeVisible();
    await expect(page.getByText("情报总量")).toBeVisible();

    await page.goto("/intelligence");
    await expect(page.getByRole("heading", { name: "情报中心", exact: true })).toBeVisible();
    await expect(page.getByText("Intelligence 列表")).toBeVisible();
    await expect(page.getByText("openai/codex is showing accelerated traction").first()).toBeVisible();
    await expect(page.getByText("Evidence Timeline")).toBeVisible();
  });

  test("generates and sends a report", async ({ page }) => {
    await page.goto("/reports");
    await expect(page.getByRole("heading", { name: "报告中心" })).toBeVisible();
    await expect(page.getByRole("button", { name: /AI Scrapy Tools 日报/ })).toBeVisible();
    await expect(page.getByText("证据引用").first()).toBeVisible();

    await page.getByRole("button", { name: "生成日报", exact: true }).click();
    await expect(page.getByRole("heading", { name: "核心发现", exact: true })).toBeVisible();

    const reportDetail = page.locator("section").filter({ hasText: "派发状态" });
    await reportDetail.getByRole("button", { name: "发送报告", exact: true }).click();
    await expect(reportDetail.getByRole("button", { name: "已发送", exact: true })).toBeDisabled();
    await expect(reportDetail.getByText("报告已进入通知链路")).toBeVisible();
  });

  test("creates alert rule and displays alert events", async ({ page }) => {
    await page.goto("/alerts");
    await expect(page.getByRole("heading", { name: "预警中心" })).toBeVisible();
    await expect(page.locator("article").filter({ hasText: "High severity signal" })).toHaveCount(
      1,
    );
    await expect(page.getByRole("heading", { name: "page_changed" })).toBeVisible();

    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.locator("article").filter({ hasText: "High severity signal" })).toHaveCount(
      2,
    );
  });

  test("marks unread notifications as read", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "站内通知收件箱", exact: true })).toBeVisible();

    const notificationCard = page
      .locator("article")
      .filter({ hasText: "Data quality anomaly watch" })
      .first();
    await expect(notificationCard).toBeVisible();

    await notificationCard.getByRole("button", { name: "Read", exact: true }).click();
    await expect(page.getByText(/Data quality anomaly watch: marked read/)).toBeVisible();
    await expect(page.locator("article").filter({ hasText: "Data quality anomaly watch" })).toHaveCount(0);
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
