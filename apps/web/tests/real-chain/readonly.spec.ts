import { test, expect, type Page } from "@playwright/test";

import {
  apiPath,
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
 *     --project=readonly
 *
 * 计数不在 beforeAll/afterAll 里取：Playwright 的 page/context fixture 是
 * 每个 test 新建的，钩子里拿不到。基线在第一个用例里取，recount 在最后
 * 一个用例里做，靠 serial 模式保证顺序。
 */

test.describe.configure({ mode: "serial" });

/** 读 competitor 域的原始记录条数。只发 GET。 */
async function countCompetitorRecords(page: Page): Promise<number> {
  const resp = await page.request.get(
    new URL(apiPath("/api/raw-records?domain=competitor&limit=200"), page.url()).toString(),
  );
  expect(resp.status(), "读取原始记录失败").toBeLessThan(300);
  const list = (await resp.json()) as unknown;
  return Array.isArray(list) ? list.length : 0;
}

// 冒烟基线。第一个用例写入，最后一个用例比对。
let baselineRecords = -1;

test("A 冒烟 @readonly 生产登录与业务域真实记录", async ({ page }) => {
  assertReadonlyTarget();
  const { email, password } = readonlyCredentials();

  // 守卫必须先装，再有任何导航。
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

  baselineRecords = await countCompetitorRecords(page);
  expect(baselineRecords, "基线记录数不应为 0").toBeGreaterThan(0);
});

test("A 冒烟 @readonly 生产洞察与证据可追溯", async ({ page }) => {
  assertReadonlyTarget();
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

test("A 冒烟 @readonly recount：只读冒烟没有写入", async ({ page }) => {
  assertReadonlyTarget();
  const { email, password } = readonlyCredentials();
  await installReadOnlyGuard(page);
  await loginThroughUi(page, email, password);

  // 第一个用例没跑成时基线是 -1，此时无法比对。直接失败而不是跳过：
  // 少了这条校验，冒烟就只剩「读出来了」，不能证明「没写进去」。
  expect(baselineRecords, "基线未建立，recount 无法比对").toBeGreaterThanOrEqual(0);

  const after = await countCompetitorRecords(page);
  expect(
    after,
    `冒烟前后原始记录数不一致（${baselineRecords} → ${after}）。只读冒烟发生了写入。`,
  ).toBe(baselineRecords);
});
