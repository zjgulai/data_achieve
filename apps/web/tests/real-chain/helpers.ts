import { expect, type APIRequestContext, type Page } from "@playwright/test";

/**
 * 真实链路 E2E 的公共设施。见 ADR-008。
 *
 * 这个文件的三个职责：
 *   1. 守卫：拒绝无边界地连到远程目标。
 *   2. 路径：在空 basePath 与 /insight 两种部署下都能拼出正确的页面路径。
 *   3. 种子：用一次性账号走真实服务路径造出可断言的数据。
 */

const DEPLOY_BASE_PATH = process.env.PLAYWRIGHT_BASE_PATH ?? "";
const ALLOW_REMOTE = process.env.PLAYWRIGHT_CHAIN_ALLOW_REMOTE === "true";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "";

/**
 * 页面路径拼接。
 *
 * Next 的 basePath 是构建期常量：生产挂在 /insight 时，产物里的所有路由都带前缀；
 * 本地一次性栈挂在根，前缀为空。
 * 直接 page.goto("/reports") 在带前缀的部署下会落到另一个应用（生产上是 console）。
 */
export function appPath(path: string): string {
  if (!DEPLOY_BASE_PATH) {
    return path;
  }
  return path === "/" ? DEPLOY_BASE_PATH : `${DEPLOY_BASE_PATH}${path}`;
}

/**
 * 远程目标守卫。
 *
 * 门禁的价值建立在「不写生产」上。一旦 base URL 指向非本机而调用方没有
 * 显式确认，用例必须立刻失败——而不是先跑一半再在写操作上出问题。
 */
export function assertTargetAllowed(): void {
  let host: string;
  try {
    host = new URL(BASE_URL).hostname;
  } catch {
    throw new Error(`PLAYWRIGHT_BASE_URL 不是合法 URL：${BASE_URL}`);
  }

  const isLoopback = host === "127.0.0.1" || host === "localhost" || host === "::1";
  if (!isLoopback && !ALLOW_REMOTE) {
    throw new Error(
      `目标 ${host} 不是本机。连远程必须显式设 PLAYWRIGHT_CHAIN_ALLOW_REMOTE=true，` +
        "并且只跑 @readonly 用例。门禁本身只允许连一次性本地栈。",
    );
  }
}

/** 断言当前是本地栈。写操作类用例在动手前必须调它。 */
export function assertLoopbackTarget(): void {
  const host = new URL(BASE_URL).hostname;
  if (host !== "127.0.0.1" && host !== "localhost" && host !== "::1") {
    throw new Error(
      `这是写操作，目标必须是本机栈，实际是 ${host}。生产写入未获授权（ADR-008 D5）。`,
    );
  }
}

// ---------- 种子 ----------

export type SeedContext = {
  email: string;
  password: string;
  projectId: string;
  sourceId: string;
  taskId: string;
  entityName: string;
  /** 种子落库后该域的原始记录数（在 seedChain 内部用同一会话核对）。 */
  recordCount: number;
  /** 种子落库后该域的情报数。 */
  intelligenceCount: number;
  /** 第一条情报的 id，供详情用例定位。 */
  firstIntelligenceId: string;
};

/**
 * 实体类型必须是 github_repo，不能随便写。
 *
 * signal_service._detect_star_growth 首行就 `if entity_type != "github_repo": return None`，
 * page_changed 则只认 web_page。用别的类型采集会成功、原始记录会入库，
 * 但永远不产生信号，于是情报列表是空的——链路看起来通了，实际断在归一化到信号之间。
 * 这个坑实测踩过一次：用 "repo" 时 raw_records 有 2 条、signals 是 0。
 */
const SEED_ENTITY_TYPE = "github_repo";
const SEED_ENTITY_NAME = "acme/e2e-chain";
const SEED_STARS_BEFORE = 100;
/** 360 - 100 = 260，超过 delta>100 且 ratio>2.0 的阈值，必须触发高严重度。 */
const SEED_STARS_AFTER = 360;

/** 每次运行唯一的一次性账号。不带时间戳，靠随机后缀区分。 */
export function newSeedIdentity(): { email: string; password: string } {
  const suffix = Math.random().toString(36).slice(2, 10);
  return {
    email: `e2e-chain-${suffix}@example.com`,
    password: `E2eChain-${suffix}-pw`,
  };
}

/**
 * 用 API 注册并造出「两次采集、有信号、有情报」的完整前置。
 *
 * 全部走真实接口，不走数据库直写：直写会绕过服务层，那样造出来的数据
 * 不能证明链路通，只能证明表结构对得上。
 */
export async function seedChain(
  request: APIRequestContext,
): Promise<SeedContext> {
  assertLoopbackTarget();

  const { email, password } = newSeedIdentity();

  // 注册即建立会话（Set-Cookie）。后续请求由 request context 自动携带。
  const register = await request.post(appPath("/api/auth/register"), {
    data: { email, password, name: "E2E Chain" },
  });
  expect(register.status(), `注册失败：${await register.text()}`).toBe(201);

  const projectResp = await request.post(appPath("/api/projects"), {
    data: {
      name: "E2E 竞品链路",
      description: "真实链路 E2E 种子项目（一次性）",
      domain: "competitor",
    },
  });
  expect(projectResp.status(), `建项目失败：${await projectResp.text()}`).toBe(201);
  const projectId = (await projectResp.json()).id as string;

  const sourceResp = await request.post(appPath("/api/sources"), {
    data: {
      project_id: projectId,
      name: "E2E GitHub stars",
      type: "manual_json",
      config: {
        entity_type: SEED_ENTITY_TYPE,
        json_data: { full_name: SEED_ENTITY_NAME, stars: SEED_STARS_BEFORE },
      },
    },
  });
  expect(sourceResp.status(), `建 source 失败：${await sourceResp.text()}`).toBe(201);
  const sourceId = (await sourceResp.json()).id as string;

  // enable 才会建出 CollectionTask；直接跑 source 没有入口。
  const enableResp = await request.post(appPath(`/api/sources/${sourceId}/enable`));
  expect(enableResp.status(), `启用 source 失败：${await enableResp.text()}`).toBe(200);
  const taskId = (await enableResp.json()).id as string;

  await runTask(request, taskId);

  // 改动 metrics 再跑一次。信号是「两次快照之间的差」，只有一次采集不会有信号。
  const patch = await request.patch(appPath(`/api/sources/${sourceId}`), {
    data: {
      config: {
        entity_type: SEED_ENTITY_TYPE,
        json_data: { full_name: SEED_ENTITY_NAME, stars: SEED_STARS_AFTER },
      },
    },
  });
  expect(patch.status(), `更新 source 失败：${await patch.text()}`).toBe(200);

  await runTask(request, taskId);

  // 在同一个 request context 内核对种子。Cookie 只在这个 context 里有效：
  // Playwright 的 request fixture 每个 test 是独立 context，跨 test 拿不到会话，
  // 所以「种子是否成立」的断言必须留在这里，不能挪到测试体里。
  const recordsResp = await request.get(
    appPath("/api/raw-records?domain=competitor&limit=50"),
  );
  expect(recordsResp.status(), "种子后的原始记录读取失败").toBe(200);
  const records = (await recordsResp.json()) as Array<{ id: string }>;

  const intelResp = await request.get(appPath("/api/intelligence?domain=competitor"));
  expect(intelResp.status(), "种子后的情报读取失败").toBe(200);
  const intelRaw = (await intelResp.json()) as
    | Array<{ id: string }>
    | { items?: Array<{ id: string }> };
  const intelItems = Array.isArray(intelRaw) ? intelRaw : (intelRaw.items ?? []);

  expect(
    records.length,
    "两次采集应至少产生 2 条原始记录；为 0 说明采集没落库",
  ).toBeGreaterThanOrEqual(2);
  expect(
    intelItems.length,
    "两次 stars 采集应产生情报；为 0 通常是 entity_type 不是 github_repo，信号判定直接 return None",
  ).toBeGreaterThanOrEqual(1);

  return {
    email,
    password,
    projectId,
    sourceId,
    taskId,
    entityName: SEED_ENTITY_NAME,
    recordCount: records.length,
    intelligenceCount: intelItems.length,
    firstIntelligenceId: intelItems[0].id,
  };
}

async function runTask(request: APIRequestContext, taskId: string): Promise<void> {
  const run = await request.post(appPath(`/api/tasks/${taskId}/run`));
  expect(run.status(), `采集运行失败：${await run.text()}`).toBe(201);
  const body = await run.json();
  expect(body.status, `采集未成功：${JSON.stringify(body).slice(0, 400)}`).toBe("success");
}

// ---------- UI 登录 ----------

/**
 * 走真实登录表单拿会话。
 *
 * 不用 storageState 或直接塞 Cookie：那样绕过的正是门禁要验证的那一段。
 */
export async function loginThroughUi(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto(appPath("/login"));
  await page.fill("#auth-email", email);
  await page.fill("#auth-password", password);

  const [loginResponse] = await Promise.all([
    page.waitForResponse(
      (resp) => resp.url().includes("/api/auth/login") && resp.request().method() === "POST",
    ),
    page.getByRole("button", { name: /^登录$/ }).last().click(),
  ]);
  expect(loginResponse.status(), "登录接口未返回 200").toBe(200);

  await page.waitForURL((url) => url.pathname.includes("/dashboard"), { timeout: 30_000 });
}

// ---------- 等待真实接口 ----------

/**
 * 等一个真实接口响应，并返回其 JSON。
 *
 * 这是「非 mock」的证明点（ADR-008 D3）：mock 分支在 API 模块里提前 return，
 * 根本不会发 HTTP。等不到响应就说明这一页还是 mock。
 */
export async function waitForApiJson<T>(
  page: Page,
  matcher: (url: URL) => boolean,
  action: () => Promise<void>,
): Promise<T> {
  const [response] = await Promise.all([
    page.waitForResponse((resp) => matcher(new URL(resp.url()))),
    action(),
  ]);
  // 只要求 2xx：创建类接口正常返回 201（例如 /api/reports/generate），
  // 把成功条件写死成 200 会让测试在功能正常时失败。
  const status = response.status();
  expect(
    status >= 200 && status < 300,
    `接口 ${response.url()} 返回 ${status}，期望 2xx`,
  ).toBe(true);
  return (await response.json()) as T;
}
