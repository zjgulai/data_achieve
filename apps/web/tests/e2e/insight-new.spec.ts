import { expect, test, type Page } from "@playwright/test";

async function navigationFor(page: Page, projectName: string) {
  if (projectName === "mobile") {
    await page.getByRole("button", { name: "打开导航" }).click();
    return page.getByRole("dialog", { name: "移动主导航" });
  }
  return page.getByRole("navigation", { name: "主导航" });
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

test.beforeAll(() => {
  const baseUrl = process.env.PLAYWRIGHT_BASE_URL;
  if (baseUrl && !/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\/?$/.test(baseUrl)) {
    throw new Error(
      "Insight page acceptance requires a local mock server; PLAYWRIGHT_BASE_URL must point at localhost or be unset.",
    );
  }
});

test("shows the honest mock empty state and highlights New Insight", async ({
  page,
}, testInfo) => {
  await page.setViewportSize(
    testInfo.project.name === "mobile"
      ? { width: 375, height: 812 }
      : { width: 1440, height: 900 },
  );

  await page.goto("/new");

  await expect(page.getByRole("heading", { name: "新建洞察" })).toBeVisible();
  await expect(
    page.getByTestId("insight-analysis-type-tiktok_viral_topic"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "本地测试模式没有归档报告" }),
  ).toBeVisible();
  await expect(
    page.getByText(/测试模式不返回示例报告/).first(),
  ).toBeVisible();
  await expect(page.getByTestId("insight-report-card")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /开始分析/ })).toHaveCount(0);
  await expect(page.getByText("数据源已连接")).toHaveCount(0);

  await expectNoHorizontalOverflow(page);

  const navigation = await navigationFor(page, testInfo.project.name);
  await expect(
    navigation.getByRole("link", { name: "洞察与交付" }),
  ).toHaveAttribute("aria-current", "page");
  await expect(
    navigation.getByRole("link", { name: "新建洞察" }),
  ).toHaveAttribute("aria-current", "page");
});

test("keeps navigation active on a report detail path and never renders a fake frame in mock mode", async ({
  page,
}, testInfo) => {
  await page.setViewportSize(
    testInfo.project.name === "mobile"
      ? { width: 375, height: 812 }
      : { width: 1440, height: 900 },
  );

  await page.goto("/new/0f7d9c2e-5a1b-4c3d-8e9f-1a2b3c4d5e6f");

  await expect(page.getByRole("heading", { name: "报告详情" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "本地测试模式没有归档报告" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "返回新建洞察" })).toBeVisible();
  await expect(page.locator("iframe")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /开始分析/ })).toHaveCount(0);

  await expectNoHorizontalOverflow(page);

  const navigation = await navigationFor(page, testInfo.project.name);
  await expect(
    navigation.getByRole("link", { name: "新建洞察" }),
  ).toHaveAttribute("aria-current", "page");
  await expect(
    navigation.getByRole("link", { name: "洞察与交付" }),
  ).toHaveAttribute("aria-current", "page");
});
