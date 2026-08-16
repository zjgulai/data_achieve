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

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

test.beforeAll(() => {
  if (process.env.PLAYWRIGHT_BASE_URL) {
    throw new Error(
      "Platform credential acceptance requires the local mock server; PLAYWRIGHT_BASE_URL must be unset.",
    );
  }
});

test("Workspace Owner can configure and remove a platform credential without secret echo or external calls", async ({
  page,
}, testInfo) => {
  await page.setViewportSize(
    testInfo.project.name === "mobile"
      ? { width: 375, height: 812 }
      : { width: 1440, height: 900 },
  );
  const externalRequests = await installLocalOnlyRequestGuard(page);

  await page.goto("/settings/platforms");
  await expect(page.getByRole("heading", { name: "平台设置" })).toBeVisible();
  await expect(page.getByText("配置不等于授权调用")).toBeVisible();
  await expect(
    page.locator('[data-testid^="platform-credential-row-"]'),
  ).toHaveCount(7);
  await expect(page.getByText("0 / 7")).toBeVisible();

  await page.getByTestId("platform-credential-row-youtube").click();
  const credentialInput = page.getByLabel("API key", { exact: true });
  await expect(credentialInput).toHaveAttribute("type", "password");
  await credentialInput.fill("local-fixture-value-never-echoed");
  await page.getByRole("button", { name: "保存凭证" }).click();

  await expect(page.getByText(/YouTube 凭证已加密保存/)).toBeVisible();
  await expect(credentialInput).toHaveValue("");
  await expect(
    page
      .getByTestId("platform-credential-row-youtube")
      .getByText("已配置", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("body")).not.toContainText(
    "local-fixture-value-never-echoed",
  );
  await page.getByText("Advanced diagnostics").click();
  await expect(page.getByText("disabled", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "移除凭证" }).click();
  await expect(page.getByText("确认移除该平台全部凭证？")).toBeVisible();
  await page.getByRole("button", { name: "确认移除" }).click();
  await expect(page.getByText(/YouTube 凭证已移除/)).toBeVisible();
  await expect(
    page
      .getByTestId("platform-credential-row-youtube")
      .getByText("未配置", { exact: true }),
  ).toBeVisible();

  await expectNoHorizontalOverflow(page);
  expect(externalRequests()).toEqual([]);
});
