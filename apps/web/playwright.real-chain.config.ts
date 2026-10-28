import { defineConfig, devices } from "@playwright/test";

/**
 * 真实链路 E2E 配置。见 docs/architecture/decisions/ADR-008-real-chain-e2e-gate.md
 *
 * 与 playwright.config.ts 的三处关键差别：
 *   1. 没有 webServer。目标是一个已经在跑的真实栈（本地一次性栈或生产只读冒烟），
 *      由调用方保证它存在。自带 webServer 会让 CI 静默起一个 mock 前端，
 *      那正好是这条门禁要排除的东西。
 *   2. 必须显式提供 PLAYWRIGHT_BASE_URL。没有默认值——默认到某一台生产
 *      就等于把门禁指向别人的数据。
 *   3. 只跑 desktop。链路断言与视口无关，跑两遍只是让门禁慢一倍。
 *
 * 两个 project 的分工是硬边界，不是偏好：
 *   - desktop：门禁。跑 real-chain.spec.ts，连一次性本地栈，CI 必过。
 *   - readonly：owner-run 冒烟。只跑 readonly.spec.ts，连生产 A。
 *     desktop 用 testIgnore 排除了它，所以 `--project=desktop`（门禁脚本用的
 *     就是这个）永远不会碰生产，也不会因为缺凭据而红。
 *
 * 注意：**不带 --project 时会两个 project 都跑**（Playwright 的
 * --project 默认值是 run all projects）。所以任何调用都必须显式指定
 * --project=desktop 或 --project=readonly，裸跑会把生产冒烟带进来，
 * 缺凭据时那三条会失败。
 */

const baseURL = process.env.PLAYWRIGHT_BASE_URL;

if (!baseURL) {
  throw new Error(
    "PLAYWRIGHT_BASE_URL 未设置。真实链路 E2E 必须显式指定目标：" +
      "本地栈用 bash scripts/e2e-real-stack.sh up 后取 http://127.0.0.1:8090；" +
      "生产只读冒烟用 https://scrapy.luteos.com 并同时设 PLAYWRIGHT_BASE_PATH=/insight。",
  );
}

export default defineConfig({
  testDir: "./tests/real-chain",
  outputDir: "../../tmp/playwright-real-chain-results",
  // 整场链路串行：种子的每一步都在为下一步准备前置，并行会互相踩。
  fullyParallel: false,
  workers: 1,
  // 真实网络往返比 mock 慢，但也不该慢到分钟级。超过 90s 说明栈本身有问题。
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  use: {
    baseURL,
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop",
      // 门禁绝不跑只读冒烟：后者需要生产凭据，且断言的是生产数据形态。
      testIgnore: /readonly\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "readonly",
      // 只读冒烟单独一个 project，只能被 --project=readonly 显式选中。
      testMatch: /readonly\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
