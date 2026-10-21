import { defineConfig, devices } from "@playwright/test";

/**
 * 控制台路由 E2E 配置。
 *
 * 默认连接本机 3001 端口的开发服务器。CI 或远端环境用
 * PLAYWRIGHT_BASE_URL 指定已启动的服务；此时本配置不再拉起 webServer。
 */

const DEFAULT_PORT = 3001;
const DEFAULT_BASE_URL = `http://127.0.0.1:${DEFAULT_PORT}`;

const externalBaseUrl = process.env.PLAYWRIGHT_BASE_URL;
const baseURL = externalBaseUrl ?? DEFAULT_BASE_URL;

/** 可选的已登录状态。存在时启用 authenticated 项目。 */
const storageState = process.env.PLAYWRIGHT_STORAGE_STATE;

/** 显式给了 PLAYWRIGHT_BASE_URL 时视为外部服务，不再自动启动。 */
const shouldStartWebServer =
  !externalBaseUrl && process.env.PLAYWRIGHT_SKIP_WEBSERVER !== "1";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../../tmp/playwright-console-results",
  fullyParallel: false,
  workers: 1,
  // 要求：CI 不重试。本地留一次重试，配合 trace 排查抖动。
  retries: process.env.CI ? 0 : 1,
  forbidOnly: Boolean(process.env.CI),
  timeout: 45_000,
  expect: {
    timeout: 10_000,
  },
  reporter: [
    ["list"],
    [
      "html",
      {
        outputFolder: "../../tmp/playwright-console-report",
        open: "never",
      },
    ],
  ],
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      // 需要登录状态的用例只在 authenticated 项目里跑。
      grepInvert: /@authenticated/,
    },
    // 可选项目：提供 PLAYWRIGHT_STORAGE_STATE 时才注册。
    ...(storageState
      ? [
          {
            name: "chromium-authenticated",
            use: {
              ...devices["Desktop Chrome"],
              storageState,
            },
            grep: /@authenticated/,
          },
        ]
      : []),
  ],
  ...(shouldStartWebServer
    ? {
        webServer: {
          command: `npm run dev -- --port ${DEFAULT_PORT}`,
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: {
            NEXT_PUBLIC_API_URL:
              process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000",
          },
        },
      }
    : {}),
});
