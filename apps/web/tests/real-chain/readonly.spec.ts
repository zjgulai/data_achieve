import { test, expect } from "@playwright/test";

import {
  appPath,
  assertReadonlyTarget,
  installReadOnlyGuard,
  loginThroughUi,
  readonlyCredentials,
  waitForApiJson,
} from "./helpers";

/**
 * 生产 A 只读真实数据冒烟。见 ADR-008 D7。
 *
 * 这条用例**不是门禁**，是 owner-run 的检查：它连的是真实生产库，
 * 只看不写。门禁（real-chain.spec.ts）跑一次性本地栈，两者回答不同问题：
 *   - 门禁回答「链路机制有没有断」；
 *   - 冒烟回答「生产上那批真实数据现在还能不能读出这条链」。
 *
 * 三条硬约束，全部由运行时代码强制，不靠自觉：
 *   1. 必须显式设 PLAYWRIGHT_BASE_URL、PLAYWRIGHT_BASE_PATH=/insight、
 *      PLAYWRIGHT_CHAIN_ALLOW_REMOTE=true（assertReadonlyTarget）。
 *   2. 除 POST /api/auth/login 外只许 GET（installReadOnlyGuard）。
 *   3. 不自建账号、不自建项目、不生成报告。生产只有一个真实用户，
 *      没有清理账本，写进去就收不回来。
 *
 * 执行：
 *   PLAYWRIGHT_BASE_URL=https://scrapy.luteos.com \
 *   PLAYWRIGHT_BASE_PATH=/insight \
 *   PLAYWRIGHT_CHAIN_ALLOW_REMOTE=true \
 *   SCRAPY_DEMO_EMAIL=... SCRAPY_DEMO_PASSWORD=... \
 *     pnpm -C apps/web exec playwright test -c playwright.real-chain.config.ts \
 *     --project=desktop --grep "@readonly"
 */

test.describe.configure({ mode: "serial" });

// 冒烟前后的实体计数。只读用例的价值一半在于「读出来了」，
// 另一半在于「确实什么都没写进去」。
let beforeCounts: { records: number; intelligence: number } | null = null;

test.beforeAll(async ({ page }) => {
  assertReadonlyTarget();
  const { email, password } = readonlyCredentials();

  // 守卫必须先装，再有任何导航。
  await installReadOnlyGuard(page);
  await loginThroughUi(page, email, password);

  const records = await page.request.get(
    new URL(appPath("/api/raw-records?domain=competitor&limit=200"), page.url()).toString(),
  );
  expect(records.status(), "冒烟前读取原始记录失败").toBeLessThan(300);
  const recordList = (await records.json()) as unknown[];
  beforeCounts = {
    records: Array.isArray(recordList) ? recordList.length : 0,
    intelligence: 0,
  };
});

test("A 冒烟 @readonly 生产登录与业务域真实记录", async ({ page }) => {
  const { email, password } = readonlyCredentials();
  await installReadOnlyGuard(page);
  await loginThroughUi(page, email, password);
  await expect(page).toHaveURL(new RegExp(`${appPath("/dashboard")}$`));

  const payload = await waitForApiJson<unknown>(
    page,
    (url) =>
      url.pathname.endsWith("/api/raw-records") &&
      url.searchParams.get("domain") === "competitor",
    async () => {
      await page.goto(appPath("/domain/competitor"));
    },
  );

  const records = Array.isArray(payload) ? payload : [];
  expect(records.length, "生产 competitor 域应有真实采集记录").toBeGreaterThan(0);

  await expect(page.getByTestId("domain-records-panel")).toBeVisible();
  await expect(page.getByTestId("domain-records-list")).toBeVisible();
  await expect(page.getByTestId("domain-records-list").getByRole("link").first()).toBeVisible();
});

test("A 冒烟 @readonly 生产洞察与证据可追溯", async ({ page }) => {
  const { email, password } = readonlyCredentials();
  await installReadOnlyGuard(page);
  await loginThroughUi(page, email, password);

  const payload = await waitForApiJson<unknown>(
    page,
    (url) =>
      url.pathname.endsWith("/api/intelligence") &&
      url.searchParams.get("domain") === "competitor",
    async () => {
      await page.goto(appPath("/intelligence?domain=competitor"));
    },
  );

  const items = Array.isArray(payload) ? payload : [];
  expect(items.length, "生产 competitor 域应有真实情报").toBeGreaterThan(0);

  if (beforeCounts) {
    beforeCounts.intelligence = items.length;
  }

  const first = items[0] as { id: string };
  await page.getByTestId(`intelligence-list-item-${first.id}`).click();
  const openDetail = page.getByTestId("intelligence-open-detail");
  await expect(openDetail).toBeVisible();

  const evidences = await waitForApiJson<unknown>(
    page,
    (url) => url.pathname.includes(`/api/intelligence/${first.id}/evidences`),
    async () => {
      await openDetail.click();
    },
  );
  expect(
    Array.isArray(evidences) ? evidences.length : 0,
    "生产洞察必须带证据，否则不可追溯",
  ).toBeGreaterThan(0);
});

test("A 冒烟 @readonly 生产报告段跳过并说明原因", async () => {
  // 明确 skip 而不是假装通过。生产只有 1 条报告且 project_id 为 NULL
  // （2026-10-09 生成），域筛选走 inner join projects 会排除它；
  // 而生成新报告是写操作，未获授权。
  //
  // 用 skip 而不是隐藏这条用例：留下一行显式的「没覆盖」，比让人以为
  // 报告段已经验过要好。
  test.skip(
    true,
    "生产报告段未覆盖：现有 1 条报告 project_id 为 NULL，域筛选会排除；" +
      "生成新报告属于生产写入，未获授权（ADR-008 D5）。待 RC-09 定稿报告口径后再补。",
  );
});

test.afterAll(async ({ page }) => {
  if (!beforeCounts) {
    return;
  }
  // recount：读操作不该改变任何东西。数量变了说明守卫漏了某个写路径。
  const records = await page.request.get(
    new URL(appPath("/api/raw-records?domain=competitor&limit=200"), page.url()).toString(),
  );
  if (records.status() >= 300) {
    return;
  }
  const recordList = (await records.json()) as unknown[];
  const after = Array.isArray(recordList) ? recordList.length : 0;
  expect(
    after,
    `冒烟前后原始记录数不一致（${beforeCounts.records} → ${after}）。只读冒烟发生了写入。`,
  ).toBe(beforeCounts.records);
});
