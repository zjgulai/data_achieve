import { defineConfig, devices } from "@playwright/test";

const port = 3100;
const externalBaseUrl = process.env.PLAYWRIGHT_BASE_URL;
const localBaseUrl = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "../../tmp/playwright-results",
  timeout: 30_000,
  expect: {
    timeout: 8_000,
  },
  workers: 1,
  use: {
    baseURL: externalBaseUrl ?? localBaseUrl,
    trace: "retain-on-failure",
  },
  ...(externalBaseUrl
    ? {}
    : {
        webServer: {
          command: `NEXT_PUBLIC_MOCK_API=true pnpm exec next dev --port ${port}`,
          url: localBaseUrl,
          reuseExistingServer: true,
          timeout: 60_000,
        },
      }),
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
