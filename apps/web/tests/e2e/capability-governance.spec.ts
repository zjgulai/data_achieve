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

async function openFirstGovernanceDossier(page: Page) {
  const trigger = page
    .locator("[data-governance-candidate-key]")
    .first()
    .getByRole("button", { name: "审查档案" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", {
    name: /content · search discover/,
  });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "关闭治理档案" }),
  ).toBeFocused();
  return { dialog, trigger };
}

test.beforeAll(() => {
  if (process.env.PLAYWRIGHT_BASE_URL) {
    throw new Error(
      "Capability Governance acceptance requires PLAYWRIGHT_BASE_URL to be unset so Playwright owns the local mock server.",
    );
  }
});

test("governance reviewer publishes twice and appends rollback Revision", async ({
  page,
}, testInfo) => {
  const mobile = testInfo.project.name === "mobile";
  await page.setViewportSize(
    mobile ? { width: 375, height: 812 } : { width: 1440, height: 900 },
  );
  const externalRequests = await installLocalOnlyRequestGuard(page);

  await page.goto("/api-market/discovery");
  const previewHeading = page.getByRole("heading", {
    name: "能力发现 Preview",
  });
  const governanceHeading = page.getByRole("heading", { name: "治理审计台" });
  await expect(previewHeading).toBeVisible();
  await expect(governanceHeading).toBeVisible();
  expect(
    await previewHeading.evaluate((preview, governanceId) => {
      const governance = document.getElementById(governanceId);
      return governance
        ? Boolean(
            preview.compareDocumentPosition(governance) &
            Node.DOCUMENT_POSITION_FOLLOWING,
          )
        : false;
    }, "governance-heading"),
  ).toBe(true);
  await expect(page.locator("[data-governance-candidate-key]")).toHaveCount(7);

  const { dialog, trigger } = await openFirstGovernanceDossier(page);
  await expect(
    dialog.getByRole("heading", { name: "Evidence Dossier" }),
  ).toBeVisible();
  await expect(dialog.locator("[data-governance-evidence-id]")).toHaveCount(4);
  await dialog.getByRole("button", { name: "核验通过" }).click();
  await expect(page.getByRole("status")).toContainText("核验已记录");
  await expect(dialog.getByText("已核验", { exact: true })).toBeVisible();

  await dialog.getByRole("button", { name: "发布到 Catalog" }).click();
  await expect(page.getByRole("status")).toContainText("Revision #1 已发布");
  await dialog.getByRole("button", { name: "发布到 Catalog" }).click();
  await expect(page.getByRole("status")).toContainText("Revision #2 已发布");
  await expect(page.locator("[data-governance-revision-id]")).toHaveCount(2);

  await dialog.getByRole("button", { name: "关闭治理档案" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await page.getByRole("button", { name: "回滚到 Revision #1" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Revision #3 已回滚到 Revision #1",
  );
  await expect(page.locator("[data-governance-revision-id]")).toHaveCount(3);

  if (mobile) {
    await page.getByRole("button", { name: "打开导航" }).click();
    await expect(page.getByTestId("mobile-primary-nav-link")).toHaveCount(6);
    await page.keyboard.press("Escape");
  } else {
    await expect(page.getByTestId("primary-nav-link")).toHaveCount(6);
  }
  await page.goto("/api-market");
  await expect(
    page.getByRole("group", { name: "视图切换" }).getByRole("button"),
  ).toHaveCount(3);
  await expectNoHorizontalOverflow(page);
  expect(externalRequests()).toEqual([]);
});

test("governance forbidden fixture fails closed without mock fallback facts", async ({
  page,
}, testInfo) => {
  await page.setViewportSize(
    testInfo.project.name === "mobile"
      ? { width: 375, height: 812 }
      : { width: 1440, height: 900 },
  );
  const externalRequests = await installLocalOnlyRequestGuard(page);

  await page.goto("/api-market/discovery?governance_fixture=forbidden");
  await expect(page.getByLabel("离线快照边界")).toBeVisible();
  await expect(
    page
      .locator('[role="alert"]')
      .filter({ hasText: "capability_governance_forbidden" }),
  ).toContainText("capability_governance_forbidden");
  await expect(page.locator("[data-governance-candidate-key]")).toHaveCount(0);
  await expect(page.locator("[data-discovery-candidate-id]")).toHaveCount(7);
  await expectNoHorizontalOverflow(page);
  expect(externalRequests()).toEqual([]);
});

test("governance review conflict reloads the authoritative open Task", async ({
  page,
}, testInfo) => {
  await page.setViewportSize(
    testInfo.project.name === "mobile"
      ? { width: 375, height: 812 }
      : { width: 1440, height: 900 },
  );
  const externalRequests = await installLocalOnlyRequestGuard(page);

  await page.goto("/api-market/discovery?governance_fixture=review-conflict");
  const { dialog } = await openFirstGovernanceDossier(page);
  await dialog.getByRole("button", { name: "核验通过" }).click();
  await expect(
    page
      .locator('[role="alert"]')
      .filter({ hasText: "verification_task_conflict" }),
  ).toContainText("verification_task_conflict · 已重新加载权威状态");
  await expect(dialog.getByText("Task v1", { exact: true })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "核验通过" })).toBeEnabled();
  await expect(page.locator("[data-governance-revision-id]")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);
  expect(externalRequests()).toEqual([]);
});
