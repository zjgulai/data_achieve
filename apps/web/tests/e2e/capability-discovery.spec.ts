import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test, type Page } from "@playwright/test";

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

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

test("API Market Discovery replays four offline sources through Candidate and Evidence review", async ({
  page,
}, testInfo) => {
  const mobile = testInfo.project.name === "mobile";
  await page.setViewportSize(
    mobile ? { width: 375, height: 812 } : { width: 1440, height: 900 },
  );
  const externalRequests = await installLocalOnlyRequestGuard(page);

  await page.goto("/api-market");
  await expect(
    page.getByRole("heading", { name: "能力事实审查台" }),
  ).toBeVisible();
  const discoveryEntry = page.getByRole("link", {
    name: "打开能力发现 Preview",
  });
  await expect(discoveryEntry).toHaveAttribute("href", "/api-market/discovery");
  await discoveryEntry.click();
  await expect(page).toHaveURL(/\/api-market\/discovery$/);

  await expect(
    page.getByRole("heading", { name: "能力发现 Preview" }),
  ).toBeVisible();
  await expect(page.getByLabel("离线快照边界")).toContainText("待核验");
  await expect(page.getByLabel("离线快照边界")).toContainText("不可执行");
  await expect(page.getByLabel("离线快照边界")).toContainText("不可发布");
  await expect(
    page.locator("span").filter({ hasText: /^provider_call=false$/ }),
  ).toBeVisible();
  await expect(
    page.locator("span").filter({ hasText: /^browser_run=false$/ }),
  ).toBeVisible();

  const sources = page.locator("[data-discovery-source-id]");
  await expect(sources).toHaveCount(4);
  await expect(sources.getByText("公开市场来源", { exact: true })).toHaveCount(
    2,
  );
  await expect(sources.getByText("官方文档来源", { exact: true })).toHaveCount(
    2,
  );
  await expect(page.locator("[data-discovery-candidate-id]")).toHaveCount(7);
  await expect(page.locator("[data-discovery-warning]")).toHaveCount(2);

  const sourceTrigger = page.getByRole("button", {
    name: "查看 TikHub YouTube API public page 的 Candidate",
  });
  await sourceTrigger.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-discovery-candidate-id]")).toHaveCount(3);

  const candidateTrigger = page
    .locator("[data-discovery-candidate-id]")
    .first()
    .getByRole("button", { name: "审查 Candidate 证据" });
  await candidateTrigger.focus();
  await page.keyboard.press("Enter");

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByText("Candidate 详情", { exact: true }),
  ).toBeVisible();
  const closeButton = dialog.getByRole("button", {
    name: "关闭 Candidate 详情",
  });
  await expect(closeButton).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.locator(":focus")).toHaveCount(1);
  await page.keyboard.press("Tab");
  await expect(closeButton).toBeFocused();

  const evidenceButton = dialog.getByRole("button", {
    name: /查看 Evidence/,
  });
  await evidenceButton.focus();
  await page.keyboard.press("Enter");
  await expect(
    dialog.getByRole("heading", { name: "Evidence 详情" }),
  ).toBeVisible();
  await expect(
    dialog.getByText("L2-fixture-or-dry-run", { exact: true }),
  ).toBeVisible();

  const dialogBox = await dialog.boundingBox();
  const viewportWidth = page.viewportSize()?.width ?? 0;
  expect(dialogBox).not.toBeNull();
  expect(dialogBox?.x ?? -1).toBeGreaterThanOrEqual(-1);
  expect((dialogBox?.x ?? 0) + (dialogBox?.width ?? 0)).toBeLessThanOrEqual(
    viewportWidth + 1,
  );
  await expectNoHorizontalOverflow(page);

  await closeButton.focus();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(candidateTrigger).toBeFocused();

  for (const forbiddenName of [
    "核验",
    "发布",
    "执行",
    "运行",
    "激活",
    "重试 Provider",
    "刷新 Web",
    "浏览器抓取",
  ]) {
    await expect(
      page.getByRole("button", { name: forbiddenName, exact: true }),
    ).toHaveCount(0);
  }

  await sourceTrigger.click();
  await expect(page.locator("[data-discovery-candidate-id]")).toHaveCount(7);
  await expectNoHorizontalOverflow(page);
  expect(externalRequests()).toEqual([]);

  if (process.env.CAPTURE_DISCOVERY_SCREENSHOTS === "true") {
    const outputDir = resolve(
      process.cwd(),
      "../../output/playwright/v2-route-a-capability-discovery",
    );
    mkdirSync(outputDir, { recursive: true });
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      fullPage: true,
      path: resolve(
        outputDir,
        mobile ? "03-discovery-mobile.png" : "02-discovery-desktop.png",
      ),
    });

    if (mobile) {
      await page.getByRole("button", { name: "打开导航" }).click();
      const navigationDialog = page.getByRole("dialog", { name: "移动主导航" });
      await expect(
        navigationDialog.getByTestId("mobile-primary-nav-link"),
      ).toHaveCount(6);
      await page.screenshot({
        path: resolve(outputDir, "04-six-entry-navigation-mobile.png"),
      });
    } else {
      await page.goto("/api-market?view=matrix");
      await expect(
        page.locator('[data-testid="capability-matrix-cell"]:visible'),
      ).toHaveCount(42);
      await page.screenshot({
        fullPage: true,
        path: resolve(outputDir, "01-api-market-matrix-desktop.png"),
      });
    }
  }
});
