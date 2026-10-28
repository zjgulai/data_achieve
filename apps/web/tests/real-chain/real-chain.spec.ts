import { test, expect } from "@playwright/test";

import {
  appPath,
  assertTargetAllowed,
  loginThroughUi,
  seedChain,
  waitForApiJson,
} from "./helpers";

/**
 * 真实链路 E2E。见 ADR-008。
 *
 * 覆盖：登录 → 选业务域 → 真实记录 → 洞察 → 证据 → 报告。
 *
 * 每个用例的通过条件都包含「观察到真实接口响应」（helpers.waitForApiJson 与
 * 显式 waitForResponse），因为 mock 分支根本不发 HTTP：只断言页面文本的话，
 * mock 与真实的区别是看不出来的。
 *
 * 用例按标签串行执行，前后依赖种子数据：@login 造种子，后续用例复用。
 * 因此本文件不能单独跑 @report —— 至少要从 @login 开始。
 */

test.beforeAll(() => {
  assertTargetAllowed();
});

test.describe.configure({ mode: "serial" });

// 整场链路共享的种子。beforeAll 里造，供四个用例依次使用。
let seed: Awaited<ReturnType<typeof seedChain>>;

test.beforeAll(async ({ request }) => {
  seed = await seedChain(request);
});

test("A 链路 @login 注册种子并按真实登录表单进入工作台", async ({ page }) => {
  // 种子的成立条件已在 seedChain 内部用同一会话核对过（见 helpers.ts 的说明：
  // Playwright 的 request fixture 每个 test 是独立 context，跨 test 拿不到 Cookie）。
  // 这里只断言链路本身：真实表单登录 → 落到工作台。
  expect(seed.recordCount, "种子应至少产生 2 条原始记录").toBeGreaterThanOrEqual(2);
  expect(
    seed.intelligenceCount,
    "种子应至少产生 1 条情报（entity_type 必须是 github_repo）",
  ).toBeGreaterThanOrEqual(1);

  // 走真实表单，不用 storageState，也不直接塞 Cookie：
  // 那样会绕过这条门禁唯一要验证的入口。
  await loginThroughUi(page, seed.email, seed.password);

  await expect(page).toHaveURL(new RegExp(`${appPath("/dashboard")}$`));
});

test("A 链路 @domain-records 域页展示真实采集记录", async ({ page }) => {
  await loginThroughUi(page, seed.email, seed.password);

  const payload = await waitForApiJson<unknown>(
    page,
    (url) => url.pathname.endsWith("/api/raw-records") && url.searchParams.get("domain") === "competitor",
    async () => {
      await page.goto(appPath("/domain/competitor"));
    },
  );

  // 接口返回非空，且页面把记录渲染出来。两者都断言，因为只看接口会漏掉
  // 「前端没渲染」这类缺陷，只看页面又分不清 mock 与真实。
  const records = Array.isArray(payload) ? payload : [];
  expect(records.length, "competitor 域应有真实采集记录").toBeGreaterThan(0);

  const panel = page.getByTestId("domain-records-panel");
  await expect(panel).toBeVisible();
  const list = page.getByTestId("domain-records-list");
  await expect(list).toBeVisible();
  await expect(list.getByRole("link").first()).toBeVisible();
});

test("A 链路 @insight-evidence 域筛选下的洞察与证据时间线", async ({ page }) => {
  await loginThroughUi(page, seed.email, seed.password);

  const payload = await waitForApiJson<unknown>(
    page,
    (url) => url.pathname.endsWith("/api/intelligence") && url.searchParams.get("domain") === "competitor",
    async () => {
      await page.goto(appPath("/intelligence?domain=competitor"));
    },
  );

  const items = Array.isArray(payload) ? payload : [];
  expect(items.length, "competitor 域应有真实情报").toBeGreaterThan(0);

  const first = items[0] as { id: string };
  const listItem = page.getByTestId(`intelligence-list-item-${first.id}`);
  await expect(listItem).toBeVisible();

  // 打开详情，并等证据接口。证据是「洞察可追溯」的唯一凭据，
  // 没有证据的情报只是文本。
  await waitForApiJson<unknown>(
    page,
    (url) => url.pathname.includes(`/api/intelligence/${first.id}/evidences`),
    async () => {
      await listItem.click();
    },
  );
});

test("A 链路 @report 从域入口生成报告并看到证据引用", async ({ page }) => {
  await loginThroughUi(page, seed.email, seed.password);

  // 域页的「培训报告」应带域参数，否则报告页拿不到当前域。
  await page.goto(appPath("/domain/competitor"));
  const reportLink = page.getByRole("link", { name: "培训报告" });
  await expect(reportLink).toHaveAttribute("href", /domain=competitor/);
  await reportLink.click();
  await page.waitForURL(/\/reports\?domain=competitor/);

  // 生成项目必须显式选当前种子项目。「全局」生成出来的报告 project_id 为空，
  // 而域筛选走 inner join projects，会把这种报告静默排除。
  await page.getByLabel("生成项目").selectOption(seed.projectId);

  // 只等生成接口。原先把 /api/reports 也用 OR 串进来，列表请求先到时会
  // 匹配错对象，断言就落在一份还没生成的列表上。
  const created = await waitForApiJson<{ id: string; project_id: string | null }>(
    page,
    (url) => url.pathname.endsWith("/api/reports/generate"),
    async () => {
      await page.getByRole("button", { name: "生成日报" }).click();
    },
  );
  expect(created.id, "生成报告应返回报告 id").toBeTruthy();
  // 显式选过项目，生成的报告就必须挂在该项目上。
  // project_id 为空时域筛选（inner join projects）会静默排除它。
  expect(created.project_id, "报告必须归属到所选项目，不能落成全局报告").toBe(seed.projectId);

  // 域内列表复核走 page.request：它与页面共享 Cookie，仍是真实 HTTP 请求
  // （因此照样能证明非 mock），但不经过页面渲染，也就不会被 reload 打断——
  // reload 会让 Playwright 丢掉响应体，读 json 时报
  // "No resource with given identifier found"。
  const listResp = await page.request.get(
    new URL(appPath("/api/reports?domain=competitor"), page.url()).toString(),
  );
  expect(listResp.status(), "域内报告列表接口未返回 2xx").toBeLessThan(300);
  const list = (await listResp.json()) as unknown;
  const reports = Array.isArray(list) ? list : [];
  expect(reports.length, "域内报告列表不应为空").toBeGreaterThan(0);
  expect(
    reports.map((item) => (item as { id: string }).id),
    "刚生成的报告必须出现在域内列表里",
  ).toContain(created.id);

  // 页面上也要真的能看到这份报告：接口通但页面不渲染同样是缺陷。
  // 用报告的详情链接定位，不用标题文本——标题是按内容生成的，不稳定。
  await page.goto(appPath("/reports?domain=competitor"));
  await expect(
    page.locator(`a[href$="/reports/${created.id}"]`).first(),
  ).toBeVisible();
});
