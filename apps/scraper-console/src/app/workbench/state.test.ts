/**
 * 工作台页面状态测试。
 *
 * 只测纯函数。测试不启动浏览器，也不发请求。
 */

import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { KEPT_ROUTES, NEW_ROUTES } from "../../lib/routes.ts";
import {
  buildWorkbenchSteps,
  currentStepKey,
  MISSING_WORKBENCH_ENDPOINTS,
  MISSING_WORKBENCH_ENDPOINT_LIST,
  readProjectParam,
  readQuestionParam,
  summarizeTasks,
  workbenchDataState,
} from "./state.ts";
import type { WorkbenchStepStatus } from "./state.ts";

/** 取指定步骤。 */
function stepStatus(steps: ReturnType<typeof buildWorkbenchSteps>, key: string): WorkbenchStepStatus {
  const step = steps.find(item => item.key === key);
  assert.ok(step, `缺少步骤 ${key}`);
  return step.status;
}

test("readQuestionParam prefills the form from ?q=", () => {
  const params = new URLSearchParams("q=%E6%AF%8D%E5%A9%B4%20%E6%8E%A8%E8%8D%90");
  assert.equal(readQuestionParam(params), "母婴 推荐");
});

test("readQuestionParam returns an empty string when q is missing", () => {
  assert.equal(readQuestionParam(new URLSearchParams()), "");
});

test("readQuestionParam keeps an empty value as an empty string", () => {
  assert.equal(readQuestionParam(new URLSearchParams("q=")), "");
});

test("readProjectParam reads the project filter", () => {
  assert.equal(readProjectParam(new URLSearchParams("project=p1")), "p1");
  assert.equal(readProjectParam(new URLSearchParams()), "");
});

test("workbenchDataState returns loading while the first request runs", () => {
  assert.equal(
    workbenchDataState({ isLoading: true, hasError: false, hasData: false }),
    "loading"
  );
});

test("workbenchDataState returns error before stale data", () => {
  assert.equal(
    workbenchDataState({ isLoading: false, hasError: true, hasData: true }),
    "error"
  );
});

test("workbenchDataState returns empty when every list is empty", () => {
  assert.equal(
    workbenchDataState({ isLoading: false, hasError: false, hasData: false }),
    "empty"
  );
});

test("workbenchDataState returns ready when any list has data", () => {
  assert.equal(
    workbenchDataState({ isLoading: false, hasError: false, hasData: true }),
    "ready"
  );
});

test("the five steps keep the contract order", () => {
  const steps = buildWorkbenchSteps({
    question: "",
    latestRun: null,
    latestReport: null,
  });
  assert.deepEqual(
    steps.map(step => step.key),
    ["question", "plan", "collect", "analyze", "report"]
  );
});

test("an empty question leaves the first step pending", () => {
  const steps = buildWorkbenchSteps({
    question: "   ",
    latestRun: null,
    latestReport: null,
  });
  assert.equal(stepStatus(steps, "question"), "pending");
});

test("a filled question makes the first step active", () => {
  const steps = buildWorkbenchSteps({
    question: "Fit 与支撑，哪个是主要摩擦？",
    latestRun: null,
    latestReport: null,
  });
  assert.equal(stepStatus(steps, "question"), "active");
});

test("the plan step is blocked because the preview endpoint is missing", () => {
  const steps = buildWorkbenchSteps({
    question: "q",
    latestRun: null,
    latestReport: null,
  });
  const plan = steps.find(step => step.key === "plan");
  assert.ok(plan);
  assert.equal(plan.status, "blocked");
  assert.equal(plan.detail.includes(MISSING_WORKBENCH_ENDPOINTS.previewPlan), true);
});

test("the collect step is pending without a run", () => {
  const steps = buildWorkbenchSteps({
    question: "q",
    latestRun: null,
    latestReport: null,
  });
  assert.equal(stepStatus(steps, "collect"), "pending");
});

test("a running run makes the collect step active", () => {
  const steps = buildWorkbenchSteps({
    question: "q",
    latestRun: {
      id: "11111111-2222-3333-4444-555555555555",
      status: "running",
      records_count: 0,
      error_message: null,
    },
    latestReport: null,
  });
  assert.equal(stepStatus(steps, "collect"), "active");
});

test("a successful run completes the collect step", () => {
  const steps = buildWorkbenchSteps({
    question: "q",
    latestRun: {
      id: "11111111-2222-3333-4444-555555555555",
      status: "partial_success",
      records_count: 42,
      error_message: null,
    },
    latestReport: null,
  });
  const collect = steps.find(step => step.key === "collect");
  assert.ok(collect);
  assert.equal(collect.status, "done");
  assert.equal(collect.detail.includes("42"), true);
});

test("a failed run fails the collect step and shows the error", () => {
  const steps = buildWorkbenchSteps({
    question: "q",
    latestRun: {
      id: "11111111-2222-3333-4444-555555555555",
      status: "failed",
      records_count: 0,
      error_message: "provider timeout",
    },
    latestReport: null,
  });
  const collect = steps.find(step => step.key === "collect");
  assert.ok(collect);
  assert.equal(collect.status, "failed");
  assert.equal(collect.detail, "provider timeout");
});

test("the analyze step is blocked because no run list endpoint exists", () => {
  const steps = buildWorkbenchSteps({
    question: "q",
    latestRun: null,
    latestReport: null,
  });
  const analyze = steps.find(step => step.key === "analyze");
  assert.ok(analyze);
  assert.equal(analyze.status, "blocked");
  assert.equal(analyze.detail.includes(MISSING_WORKBENCH_ENDPOINTS.listRuns), true);
});

test("the report step is pending without a report", () => {
  const steps = buildWorkbenchSteps({
    question: "q",
    latestRun: null,
    latestReport: null,
  });
  assert.equal(stepStatus(steps, "report"), "pending");
});

test("the report step completes when a report exists", () => {
  const steps = buildWorkbenchSteps({
    question: "q",
    latestRun: null,
    latestReport: {
      id: "r1",
      title: "母婴出海周报",
      status: "published",
    },
  });
  const report = steps.find(step => step.key === "report");
  assert.ok(report);
  assert.equal(report.status, "done");
  assert.equal(report.detail.includes("母婴出海周报"), true);
});

test("currentStepKey returns the first unfinished step", () => {
  const steps = buildWorkbenchSteps({
    question: "q",
    latestRun: {
      id: "11111111-2222-3333-4444-555555555555",
      status: "success",
      records_count: 3,
      error_message: null,
    },
    latestReport: null,
  });
  assert.equal(currentStepKey(steps), "question");
});

test("the missing endpoint list only names workbench or run paths", () => {
  for (const endpoint of MISSING_WORKBENCH_ENDPOINT_LIST) {
    assert.equal(
      endpoint.includes("/api/workbench/") || endpoint.includes("/api/runs"),
      true,
      `${endpoint} 不在工作台契约内`
    );
  }
});

test("the missing endpoint list avoids forbidden names", () => {
  for (const endpoint of MISSING_WORKBENCH_ENDPOINT_LIST) {
    assert.equal(endpoint.includes("automation_"), false);
    assert.equal(endpoint.includes("cost_ledger_entries"), false);
    assert.equal(endpoint.includes("evidence_grade_cap"), false);
  }
});

test("summarizeTasks counts all tasks and enabled tasks", () => {
  const summary = summarizeTasks([
    { status: "enabled" },
    { status: "enabled" },
    { status: "paused" },
  ]);
  assert.deepEqual(summary, { total: 3, enabled: 2 });
});

test("the workbench route is registered as new", () => {
  // /workbench 是 B5 新建的页面，与 /capabilities、/reports 同组。
  // 放进 KEPT_ROUTES 会让「保持」组混入新增项，分组断言就失去意义。
  assert.equal(NEW_ROUTES.includes("/workbench"), true);
  assert.equal(KEPT_ROUTES.includes("/workbench"), false);
});

test("the workbench page file exists", () => {
  const appDir = fileURLToPath(new URL("../", import.meta.url));
  assert.equal(existsSync(`${appDir}workbench/page.tsx`), true);
});
