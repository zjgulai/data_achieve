import assert from "node:assert/strict";
import test from "node:test";
import {
  classifyReason,
  resolveReachability,
  stateColor,
  stateOrder,
} from "./reachability.ts";

/* ── 原因分类 ── */

test("the permanent reason is recognised", () => {
  assert.equal(
    classifyReason("collection_policy_denied: aliens_eye_basic 未具备受控出口，禁止执行"),
    "permanent"
  );
});

test("the offline reason is recognised as an environment gate", () => {
  assert.equal(
    classifyReason("collection_policy_denied: 当前执行环境为离线模式"),
    "environment"
  );
});

test("a missing domain approval is a configuration reason", () => {
  assert.equal(
    classifyReason("collection_policy_denied: 缺少唯一的服务端域名批准配置"),
    "configuration"
  );
});

test("an unapproved target host is a configuration reason", () => {
  // 后端在请求发出前逐主机校验。固定目标不在批准列表时返回这个原因。
  assert.equal(
    classifyReason("outbound_domain_denied: 目标主机未获批准：www.mumsnet.com"),
    "configuration"
  );
});

test("an unknown reason defaults to configuration", () => {
  assert.equal(classifyReason("something new"), "configuration");
});

/* ── 三态 ── */

test("a permanently blocked tool is not runnable and shows no action", () => {
  const r = resolveReachability({
    catalogStatus: "verified",
    permanentlyBlocked: true,
    policyBlockReason: "collection_policy_denied: x 未具备受控出口，禁止执行",
    executableNow: false,
  });
  assert.equal(r.state, "permanently_blocked");
  assert.equal(r.canRun, false);
  assert.equal(r.showAction, false);
});

test("the offline mode gate is an environment gate", () => {
  const r = resolveReachability({
    catalogStatus: "verified",
    permanentlyBlocked: false,
    policyBlockReason: "collection_policy_denied: 当前执行环境为离线模式",
    executableNow: false,
  });
  assert.equal(r.state, "env_gated");
  assert.equal(r.canRun, false);
  // 环境门控可显示操作入口。换环境即通。
  assert.equal(r.showAction, true);
});

test("a missing key is a configuration gate", () => {
  const r = resolveReachability({
    catalogStatus: "verified",
    permanentlyBlocked: false,
    policyBlockReason: null,
    missingConfiguration: ["APIFY_API_TOKEN"],
    executableNow: false,
  });
  assert.equal(r.state, "config_gated");
  assert.equal(r.canRun, false);
  assert.equal(r.showAction, true);
  assert.match(r.blockers[0].detail, /APIFY_API_TOKEN/);
});

test("a disabled catalog row is not runnable", () => {
  const r = resolveReachability({ catalogStatus: "disabled" });
  assert.equal(r.state, "disabled");
  assert.equal(r.canRun, false);
  assert.equal(r.showAction, false);
});

test("an executable endpoint is available", () => {
  const r = resolveReachability({
    catalogStatus: "verified",
    permanentlyBlocked: false,
    policyBlockReason: null,
    missingConfiguration: [],
    executableNow: true,
    availability: "verified",
  });
  assert.equal(r.state, "available");
  assert.equal(r.canRun, true);
  assert.deepEqual(r.blockers, []);
});

test("untested is runnable but is not labelled verified", () => {
  // 无实测证据不等于验证通过。状态标为未验证，但不得阻断。
  const r = resolveReachability({
    catalogStatus: "verified",
    permanentlyBlocked: false,
    policyBlockReason: null,
    missingConfiguration: [],
    executableNow: true,
    availability: "untested",
  });
  assert.equal(r.state, "unverified");
  assert.equal(r.label, "未验证");
  assert.equal(r.canRun, true);
  assert.equal(r.showAction, true);
  assert.equal(r.blockers.length, 1);
  assert.equal(r.blockers[0].kind, "catalog");
});

/* ── 检查顺序 ── */

test("permanent outranks the environment gate", () => {
  // 服务端先判 unsupported，再看网络模式。
  const r = resolveReachability({
    catalogStatus: "verified",
    permanentlyBlocked: true,
    policyBlockReason: "collection_policy_denied: 当前执行环境为离线模式",
    executableNow: false,
  });
  assert.equal(r.state, "permanently_blocked");
});

test("configuration is reported alongside an environment gate", () => {
  // 两者独立成立。都要显示。
  const r = resolveReachability({
    catalogStatus: "verified",
    permanentlyBlocked: false,
    policyBlockReason: "collection_policy_denied: 当前执行环境为离线模式",
    missingConfiguration: ["TIKHUB_API_KEY"],
    executableNow: false,
  });
  assert.equal(r.state, "env_gated");
  assert.equal(r.blockers.length, 2);
  assert.equal(r.blockers[0].kind, "environment");
  assert.equal(r.blockers[1].kind, "configuration");
});

test("a disabled row reports the catalog blocker", () => {
  const r = resolveReachability({
    catalogStatus: "disabled",
    policyBlockReason: null,
  });
  assert.equal(r.blockers.length, 1);
  assert.equal(r.blockers[0].kind, "catalog");
});

test("a missing domain approval surfaces as a configuration blocker", () => {
  const r = resolveReachability({
    catalogStatus: "verified",
    permanentlyBlocked: false,
    policyBlockReason: "collection_policy_denied: 缺少唯一的服务端域名批准配置",
    executableNow: false,
  });
  assert.equal(r.state, "config_gated");
  assert.equal(r.blockers[0].kind, "configuration");
});

/* ── 标签与颜色 ── */

test("every state has a label and a colour", () => {
  const states = [
    "available", "env_gated", "config_gated",
    "permanently_blocked", "disabled", "unverified",
  ] as const;
  for (const s of states) {
    const r = resolveReachability({});
    assert.equal(typeof r.label, "string");
    assert.ok(stateColor(s).startsWith("var("));
  }
});

test("the state order lists blocking states first", () => {
  const order = stateOrder();
  assert.equal(order[0], "disabled");
  assert.equal(order[1], "permanently_blocked");
  assert.equal(order[order.length - 1], "available");
});

test("two calls with the same input agree", () => {
  const input = {
    catalogStatus: "verified",
    permanentlyBlocked: false,
    policyBlockReason: "collection_policy_denied: 当前执行环境为离线模式",
    missingConfiguration: ["A"],
  };
  assert.deepEqual(resolveReachability(input), resolveReachability(input));
});
