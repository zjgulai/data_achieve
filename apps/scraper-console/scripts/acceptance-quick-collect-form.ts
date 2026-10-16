/**
 * 批次 1 验收脚本。
 * 用真实契约快照，逐端点比对表单字段与后端必填参数。
 *
 * 运行：node --experimental-strip-types scripts/acceptance-quick-collect-form.ts
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  buildForm,
  buildInitialValues,
  hasEmptyRequired,
  serializeParams,
} from "../src/lib/quick-collect-form.ts";
import type { PublicTool } from "../src/lib/api/tools.ts";

type Snapshot = {
  tools: PublicTool[];
  endpoints: {
    endpoint_type: string;
    label: string;
    status: string;
    required_params: string[];
    optional_params: string[];
    policy_block_reason: string | null;
    param_fields: Record<string, string>;
  }[];
};

// 默认读 generated/ 下的快照。可用第一个参数覆盖路径。
// 该目录不入库。快照由 scripts/gen-contract-snapshot.py 生成。
// 一条命令同时生成并比对：pnpm acceptance
const SNAPSHOT = new URL("../../../generated/console-contract-snapshot.json", import.meta.url);
const snap: Snapshot = JSON.parse(
  readFileSync(process.argv[2] ?? SNAPSHOT, "utf8")
);

/** 服务端保留键。表单不渲染。 */
const RESERVED = new Set([
  "execution_origin",
  "schedule_policy",
  "schedule_cron",
  "freshness_target_hours",
  "max_retry_attempts",
  "retry_delay_minutes",
  "retry_attempts_used",
]);

const problems: string[] = [];
const toolById = new Map(snap.tools.map((t) => [t.tool_id, t]));

/** 契约外的预设。来自端点提示。 */
const presets: { endpoint: string; key: string; value: unknown }[] = [];
const injectedKeys = new Set<string>();

let checkedEndpoints = 0;
let checkedFields = 0;
let withForms = 0;
let emptyForms = 0;

for (const ep of snap.endpoints) {
  const tool = toolById.get(ep.endpoint_type);
  if (!tool) {
    problems.push(`[缺契约] ${ep.endpoint_type} 在 /api/tools 里不存在`);
    continue;
  }
  checkedEndpoints++;

  const form = buildForm(tool, ep.param_fields);
  if (form.fields.length === 0) emptyForms++;
  else withForms++;

  // 1) 字段名集合 == 契约参数名 - 保留键
  const expected = tool.parameters
    .map((p) => p.name)
    .filter((n) => !RESERVED.has(n));
  const actual = form.fields.map((f) => f.name);

  if (expected.length !== actual.length) {
    problems.push(
      `[字段数] ${ep.endpoint_type}: 契约 ${expected.length} 个，表单 ${actual.length} 个`
    );
  }
  for (const n of expected) {
    if (!actual.includes(n)) problems.push(`[缺字段] ${ep.endpoint_type}.${n}`);
  }
  for (const n of actual) {
    if (!expected.includes(n)) problems.push(`[多字段] ${ep.endpoint_type}.${n}`);
  }

  // 2) 必填标记与契约一致
  for (const p of tool.parameters) {
    if (RESERVED.has(p.name)) continue;
    const f = form.fields.find((x) => x.name === p.name);
    if (!f) continue;
    checkedFields++;
    if (f.required !== p.required) {
      problems.push(
        `[必填不符] ${ep.endpoint_type}.${p.name}: 契约 ${p.required}，表单 ${f.required}`
      );
    }
  }

  // 3) 表单字段集合必须覆盖端点声明的必填参数
  for (const n of ep.required_params) {
    if (RESERVED.has(n)) continue;
    if (!actual.includes(n)) {
      problems.push(`[必填未渲染] ${ep.endpoint_type}.${n} 在 required_params 里，但表单没有该字段`);
    }
  }

  // 4) enum 字段的选项不得为空
  for (const f of form.fields) {
    if (f.kind === "enum" && f.options.length === 0) {
      problems.push(`[空下拉] ${ep.endpoint_type}.${f.name}`);
    }
  }

  // 5) 空表单不应出现在有必填参数的端点上
  if (form.fields.length === 0 && ep.required_params.length > 0) {
    problems.push(`[空表单] ${ep.endpoint_type} 有 ${ep.required_params.length} 个必填，却渲染空表单`);
  }

  // 6) 初始值：必填已预填的不得判为空
  const values = buildInitialValues(form);
  const prefilled = form.fields.filter(
    (f) => f.required && f.defaultValue !== "" && f.defaultValue !== false
  );
  for (const f of prefilled) {
    if (hasEmptyRequired(form, values) && f.name === form.fields.find((x) => x.required)?.name) {
      problems.push(`[预填无效] ${ep.endpoint_type}.${f.name} 有默认值却仍判为空`);
    }
  }

  // 7) 序列化白名单。
  //    规则：载荷键必须来自契约或端点提示。保留键不得出现。
  const emptySerialized = serializeParams(form, {});
  const contractNames = new Set(tool.parameters.map((p) => p.name));
  const hintNames = new Set(Object.keys(ep.param_fields ?? {}));
  for (const key of Object.keys(emptySerialized)) {
    if (RESERVED.has(key)) {
      problems.push(`[保留键泄漏] ${ep.endpoint_type} 发出了 ${key}`);
      continue;
    }
    if (contractNames.has(key)) continue;
    // 契约外键只能来自端点提示。这是有意的语义预设。
    if (!hintNames.has(key)) {
      problems.push(`[越界键] ${ep.endpoint_type} 产出无来源的键 ${key}`);
      continue;
    }
    presets.push({ endpoint: ep.endpoint_type, key, value: emptySerialized[key] });
    injectedKeys.add(key);
  }
}

// 8) 契约外预设必须是合法值。查采集器的白名单。
const VALID: Record<string, Set<string>> = {
  search_type: new Set(["instant", "fast", "auto", "deep-lite", "deep", "deep-reasoning"]),
  category: new Set(["company", "people", "publication", "news", "personal site", "financial report"]),
};
for (const p of presets) {
  const allowed = VALID[p.key];
  if (allowed && typeof p.value === "string" && !allowed.has(p.value)) {
    problems.push(`[预设非法值] ${p.endpoint}.${p.key} = ${JSON.stringify(p.value)}`);
  }
}

console.log("=== 批次 1 验收：表单字段 vs 后端契约 ===");
console.log(`端点行       : ${snap.endpoints.length}`);
console.log(`有契约的端点 : ${checkedEndpoints}`);
console.log(`比对字段数   : ${checkedFields}`);
console.log(`有字段的表单 : ${withForms}`);
console.log(`空表单       : ${emptyForms}`);
console.log(`问题数       : ${problems.length}`);

if (problems.length) {
  console.log("\n=== 问题（前 40 条）===");
  for (const p of problems.slice(0, 40)) console.log("  " + p);
  if (problems.length > 40) console.log(`  …另有 ${problems.length - 40} 条`);
  process.exit(1);
}

assert.equal(problems.length, 0);
console.log("\n验收通过。");
