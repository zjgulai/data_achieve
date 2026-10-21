import { expect, test, type Page } from "@playwright/test";

/**
 * 控制台路由 E2E 冒烟。
 *
 * 覆盖三类路由：
 * 1. 公开与受保护页面。没有登录状态时，middleware 会把页面送到 /login，
 *    这按受保护路由的有效结果处理。
 * 2. 旧路由重定向。必须返回 3xx，且跟随重定向后不能落到 404。
 * 3. 可选的登录态路由。只有提供 PLAYWRIGHT_STORAGE_STATE 时才跑，
 *    用项目名 chromium-authenticated 与 @authenticated 标签隔离。
 */

/** 公开与受保护页面路由。 */
const PAGE_ROUTES = [
  "/",
  "/tools",
  "/docs",
  "/connect",
  "/assets",
  "/assets/records",
  "/projects",
  "/tasks",
  "/runs",
  "/dashboard",
  "/settings/credentials",
  "/settings/providers",
  "/settings/members",
  "/tools/tiktok",
] as const;

/** 旧路由与目标路径。来源见 src/lib/routes.ts 的冻结表。 */
const REDIRECT_ROUTES: ReadonlyArray<{
  readonly source: string;
  readonly destination: string;
}> = [
  { source: "/platforms", destination: "/tools" },
  { source: "/skills", destination: "/tools" },
  { source: "/datasets", destination: "/assets" },
  { source: "/raw-records", destination: "/assets/records" },
  { source: "/collector-docs", destination: "/docs" },
  // 带参数的重定向。参数值本身不影响 3xx 判定。
  { source: "/skills/tiktok", destination: "/tools/tiktok" },
  {
    source: "/collect/00000000-0000-0000-0000-000000000000",
    destination: "/runs/00000000-0000-0000-0000-000000000000",
  },
];

const LOGIN_PATH = "/login";
const MIN_BODY_TEXT_LENGTH = 50;

type ConsoleError = {
  readonly text: string;
  readonly url: string;
};

type PageProblems = {
  /** type=error 的 console 消息。 */
  consoleErrors: ConsoleError[];
  /** 未捕获的页面异常。 */
  pageErrors: string[];
  /** 状态码 >= 500 的 /api 响应。 */
  apiServerErrors: string[];
  /** 返回 401 的 /api URL。这些响应允许出现。 */
  authDeniedUrls: Set<string>;
};

/** 挂上监听器。在 goto 之前调用。 */
function watchPage(page: Page): PageProblems {
  const problems: PageProblems = {
    consoleErrors: [],
    pageErrors: [],
    apiServerErrors: [],
    authDeniedUrls: new Set<string>(),
  };

  page.on("console", message => {
    if (message.type() !== "error") return;
    problems.consoleErrors.push({
      text: message.text(),
      url: message.location().url,
    });
  });

  page.on("pageerror", error => {
    problems.pageErrors.push(error.message);
  });

  page.on("response", response => {
    let url: URL;
    try {
      url = new URL(response.url());
    } catch {
      return;
    }
    if (!url.pathname.includes("/api/")) return;

    if (response.status() === 401) {
      problems.authDeniedUrls.add(response.url());
      return;
    }
    if (response.status() >= 500) {
      problems.apiServerErrors.push(
        `${response.status()} ${response.request().method()} ${url.pathname}`
      );
    }
  });

  return problems;
}

/** 允许出现的 console 噪音：401 资源错误与开发服务器 HMR 握手失败。 */
function isAllowedConsoleNoise(
  problem: ConsoleError,
  authDeniedUrls: ReadonlySet<string>
): boolean {
  if (problem.url && authDeniedUrls.has(problem.url)) return true;
  if (
    /status of 401\b/i.test(problem.text) ||
    /\b401 \(Unauthorized\)/i.test(problem.text)
  ) {
    return true;
  }
  // next dev 的 HMR WebSocket 在某些代理或容器网络下握手失败。
  // 这不是页面功能错误，生产构建没有该连接。
  return /WebSocket connection to .*\/_next\/(?:webpack-)?hmr/i.test(
    problem.text
  );
}

/** 等待页面出现 main 区域，或正文超过最小长度。 */
async function waitForRenderableContent(
  page: Page,
  route: string
): Promise<void> {
  await expect
    .poll(
      async () => {
        try {
          if ((await page.locator("main").count()) > 0) return true;
          const text = (await page.locator("body").innerText()).trim();
          return text.length > MIN_BODY_TEXT_LENGTH;
        } catch {
          // 客户端重定向期间执行上下文可能失效。下一轮再试。
          return false;
        }
      },
      {
        message: `${route}: no <main> region and body text shorter than ${MIN_BODY_TEXT_LENGTH} characters`,
        timeout: 10_000,
      }
    )
    .toBe(true);
}

/** 一条路由的完整断言。 */
async function assertRoute(page: Page, route: string): Promise<void> {
  const problems = watchPage(page);

  const response = await page.goto(route, { waitUntil: "domcontentloaded" });
  if (!response) {
    throw new Error(`${route}: navigation returned no HTTP response`);
  }
  expect(response.status(), `${route}: HTTP status`).toBeLessThan(400);

  await waitForRenderableContent(page, route);

  const finalPath = new URL(page.url()).pathname;
  if (finalPath === LOGIN_PATH) {
    // 受保护路由无登录状态时的门禁结果。按有效结果处理。
    test.info().annotations.push({
      type: "auth-redirect",
      description: `${route} -> ${LOGIN_PATH}: accepted as a protected route.`,
    });
  }

  // 给客户端请求一点收尾时间，避免漏掉晚到的 console 或 5xx。
  await page
    .waitForLoadState("networkidle", { timeout: 2_000 })
    .catch(() => undefined);
  await page.waitForTimeout(200);

  const unexpectedConsoleErrors = problems.consoleErrors.filter(
    problem => !isAllowedConsoleNoise(problem, problems.authDeniedUrls)
  );
  expect(unexpectedConsoleErrors, `${route}: console errors`).toEqual([]);
  expect(problems.pageErrors, `${route}: uncaught page errors`).toEqual([]);
  expect(problems.apiServerErrors, `${route}: 5xx /api responses`).toEqual([]);
}

test.describe("route smoke", () => {
  for (const route of PAGE_ROUTES) {
    test(`${route} loads without page errors`, async ({ page }) => {
      await assertRoute(page, route);
    });
  }
});

test.describe("legacy redirects", () => {
  for (const { source, destination } of REDIRECT_ROUTES) {
    test(`${source} redirects to ${destination}`, async ({ request }) => {
      const redirect = await request.get(source, { maxRedirects: 0 });
      const status = redirect.status();
      expect(status, `${source}: expected 3xx, got ${status}`).toBeGreaterThanOrEqual(300);
      expect(status, `${source}: expected 3xx, got ${status}`).toBeLessThan(400);

      const location = redirect.headers()["location"];
      if (!location) {
        throw new Error(`${source}: missing Location header`);
      }
      const locationPath = new URL(location, "http://placeholder.invalid").pathname;
      expect(locationPath, `${source}: Location`).toBe(destination);

      // 跟随重定向后不得落到 404。
      const followed = await request.get(source, { maxRedirects: 10 });
      expect(
        followed.status(),
        `${source}: redirect chain ended with HTTP ${followed.status()}`
      ).toBeLessThan(400);
    });
  }
});

test.describe("@authenticated signed-in route smoke", () => {
  for (const route of PAGE_ROUTES) {
    test(`${route} renders with a storage state`, async ({ page }) => {
      await assertRoute(page, route);
    });
  }
});
