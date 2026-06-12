import { expect, test } from "@playwright/test";

test.describe("MVP workspace routes", () => {
  test("renders dashboard and intelligence evidence flow", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "全局仪表盘" })).toBeVisible();
    await expect(page.getByText("情报总量")).toBeVisible();

    await page.goto("/intelligence");
    await expect(page.getByRole("heading", { name: "情报中心" })).toBeVisible();
    await expect(page.getByText("Intelligence 列表")).toBeVisible();
    await expect(page.getByRole("button", { name: /example\/repo is showing/ })).toBeVisible();
    await expect(page.getByText("Evidence Timeline")).toBeVisible();
  });

  test("generates and sends a report", async ({ page }) => {
    await page.goto("/reports");
    await expect(page.getByRole("heading", { name: "报告中心" })).toBeVisible();
    await expect(page.getByRole("button", { name: /AI Scrapy Tools 日报/ })).toBeVisible();
    await expect(page.getByText("证据数").first()).toBeVisible();

    await page.getByRole("button", { name: "Generate", exact: true }).click();
    await expect(page.getByText("## 核心发现")).toBeVisible();

    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByText("sent").first()).toBeVisible();
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
    await expect(page.getByRole("heading", { name: "站内通知" })).toBeVisible();
    await expect(page.getByText("预警命中：High severity signal")).toBeVisible();

    await page.getByRole("button", { name: "Read", exact: true }).click();
    await expect(page.getByText("暂无通知")).toBeVisible();
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
