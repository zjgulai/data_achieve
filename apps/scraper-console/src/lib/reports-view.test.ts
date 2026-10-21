import assert from "node:assert/strict";
import test from "node:test";

import {
  BELOW_L4_FORBIDDEN_WORDS,
  CLAIM_STATUSES,
  EVIDENCE_GRADES,
  LIST_CONTRACT_PENDING_LABEL,
  claimDistribution,
  claimDistributionText,
  claimStatusDisplay,
  classifyContract404,
  contractAbsenceText,
  contractEndpointPath,
  contractGapView,
  contractRenderBranch,
  findForbiddenWords,
  gateLine,
  gradeBadgeText,
  hashSummaryLabel,
  isSafeLink,
  isBelowL4,
  lowestEvidenceGrade,
  reportHashRows,
  resolveReportDetailState,
  resolveReportListState,
  templateLabel,
  type ClaimStatus,
  type EvidenceGrade,
} from "./reports-view.ts";

/** 一条只带等级的 claim。测试最低等级时不需要其他字段。 */
function claimWithGrade(grade: EvidenceGrade) {
  return { evidence_grade: grade };
}

test("lowest evidence grade is the minimum over claims", () => {
  assert.equal(
    lowestEvidenceGrade([
      claimWithGrade("L4_authorized_live"),
      claimWithGrade("L3_live_single"),
      claimWithGrade("L2_fixture_local"),
    ]),
    "L2_fixture_local",
  );
});

test("lowest evidence grade ignores claim order", () => {
  assert.equal(
    lowestEvidenceGrade([
      claimWithGrade("L1_contract"),
      claimWithGrade("L4_authorized_live"),
    ]),
    "L1_contract",
  );
  assert.equal(
    lowestEvidenceGrade([
      claimWithGrade("L4_authorized_live"),
      claimWithGrade("L1_contract"),
    ]),
    "L1_contract",
  );
});

test("lowest evidence grade is null when there is no claim", () => {
  assert.equal(lowestEvidenceGrade([]), null);
});

test("below L4 forbids the three conclusion words", () => {
  assert.deepEqual(
    findForbiddenWords("本次确认了问题，证明假设成立，必然复现", "L3_live_single"),
    ["确认", "证明", "必然"],
  );
});

test("L4 allows the three conclusion words", () => {
  assert.deepEqual(
    findForbiddenWords("本次确认了问题，证明假设成立，必然复现", "L4_authorized_live"),
    [],
  );
});

test("an unknown grade is treated as below L4", () => {
  assert.equal(isBelowL4("L9_unknown" as EvidenceGrade), true);
  assert.equal(gradeBadgeText("L9_unknown" as EvidenceGrade), "L9_unknown");
});

test("below L4 badge copy never contains the forbidden words", () => {
  // 这条断言对应用户硬要求：等级低于 L4 时，文案不得用三个结论词。
  for (const grade of EVIDENCE_GRADES) {
    if (grade === "L4_authorized_live") continue;
    const texts = [gradeBadgeText(grade)];
    for (const status of CLAIM_STATUSES) {
      texts.push(claimStatusDisplay(status, grade).label);
    }
    for (const text of texts) {
      for (const word of BELOW_L4_FORBIDDEN_WORDS) {
        assert.equal(
          text.includes(word),
          false,
          `等级 ${grade} 的文案「${text}」含禁用词「${word}」`,
        );
      }
    }
  }
});

test("a confirmed claim below L4 is shown as a grade violation", () => {
  const display = claimStatusDisplay("confirmed", "L3_live_single");
  assert.equal(display.label, "状态越级");
  assert.equal(display.downgraded, true);
  assert.equal(display.tone, "danger");
});

test("a confirmed claim at L4 keeps the label", () => {
  const display = claimStatusDisplay("confirmed", "L4_authorized_live");
  assert.equal(display.label, "已确认");
  assert.equal(display.downgraded, false);
});

test("claim distribution keeps all five statuses and zero values", () => {
  const rows = claimDistribution([
    { claim_status: "confirmed" },
    { claim_status: "directional" },
    { claim_status: "directional" },
  ]);
  assert.equal(rows.length, 5);
  assert.deepEqual(
    rows.map(row => [row.status, row.count]),
    [
      ["confirmed", 1],
      ["directional", 2],
      ["hypothesis", 0],
      ["evidence_gap", 0],
      ["blocked", 0],
    ],
  );
});

test("claim distribution text uses the PRD short labels", () => {
  const text = claimDistributionText([
    { claim_status: "confirmed" },
    { claim_status: "evidence_gap" },
  ]);
  assert.equal(
    text,
    "confirmed 1 · directional 0 · hypothesis 0 · gap 1 · blocked 0",
  );
});

test("three hash rows always show contract, data and render", () => {
  const rows = reportHashRows({
    contract: {
      artifact: {
        contract_sha256: "a".repeat(64),
        report_html_sha256: "b".repeat(64),
        sop_html_sha256: "c".repeat(64),
      },
    },
    dataSha256: "d".repeat(64),
  });
  assert.deepEqual(
    rows.map(row => [row.key, row.label, row.value]),
    [
      ["contract", "合同哈希", "a".repeat(64)],
      ["data", "数据哈希", "d".repeat(64)],
      ["render", "渲染哈希", "b".repeat(64)],
    ],
  );
});

test("missing hashes name the reason and are never invented", () => {
  // 合同接口可用但数据没生成，显示「未生成」。
  // 产物接口没有挂载，数据哈希显示「接口未提供」。
  const rows = reportHashRows({ contract: null });
  assert.equal(rows.length, 3);
  assert.deepEqual(
    rows.map(row => [row.key, row.status, row.value, row.display]),
    [
      ["contract", "not_generated", null, "未生成"],
      ["data", "endpoint_missing", null, "接口未提供"],
      ["render", "not_generated", null, "未生成"],
    ],
  );
});

test("a missing contract endpoint makes both contract hashes say so", () => {
  // 端点是没挂，不是数据没生成。三行都必须写「接口未提供」。
  const rows = reportHashRows({
    contract: null,
    contractEndpointAvailable: false,
  });
  assert.equal(rows.length, 3);
  for (const row of rows) {
    assert.equal(row.value, null);
    assert.equal(row.status, "endpoint_missing");
    assert.equal(row.display, "接口未提供");
  }
});

test("hash summary reports how many hashes are missing", () => {
  const rows = reportHashRows({ contract: null });
  assert.equal(
    hashSummaryLabel(rows),
    "三个哈希（2 项未生成，1 项接口未提供）",
  );
});

test("hash summary says the interface is missing when it is", () => {
  const rows = reportHashRows({
    contract: null,
    contractEndpointAvailable: false,
  });
  assert.equal(hashSummaryLabel(rows), "三个哈希接口未提供");
});

test("hash summary is plain when all three hashes exist", () => {
  const rows = reportHashRows({
    contract: {
      artifact: {
        contract_sha256: "a".repeat(64),
        report_html_sha256: "b".repeat(64),
        sop_html_sha256: "c".repeat(64),
      },
    },
    dataSha256: "d".repeat(64),
  });
  assert.equal(hashSummaryLabel(rows), "三个哈希");
});

test("the report list state tells loading, empty, forbidden and error apart", () => {
  // 三种空态文案不同。401 与 403 都归入无权限。
  assert.equal(
    resolveReportListState({ isLoading: true, error: null, count: undefined }),
    "loading",
  );
  assert.equal(
    resolveReportListState({ isLoading: false, error: null, count: 0 }),
    "empty",
  );
  assert.equal(
    resolveReportListState({
      isLoading: false,
      error: { status: 401 },
      count: undefined,
    }),
    "forbidden",
  );
  assert.equal(
    resolveReportListState({
      isLoading: false,
      error: { status: 403 },
      count: undefined,
    }),
    "forbidden",
  );
  assert.equal(
    resolveReportListState({
      isLoading: false,
      error: { status: 500 },
      count: undefined,
    }),
    "error",
  );
  assert.equal(
    resolveReportListState({ isLoading: false, error: null, count: 2 }),
    "ready",
  );
});

test("the report detail state treats 404 as a missing report", () => {
  assert.equal(
    resolveReportDetailState({
      isLoading: true,
      error: null,
      report: undefined,
    }),
    "loading",
  );
  assert.equal(
    resolveReportDetailState({
      isLoading: false,
      error: { status: 404 },
      report: undefined,
    }),
    "empty",
  );
  assert.equal(
    resolveReportDetailState({
      isLoading: false,
      error: null,
      report: undefined,
    }),
    "empty",
  );
  assert.equal(
    resolveReportDetailState({
      isLoading: false,
      error: { status: 500 },
      report: undefined,
    }),
    "error",
  );
  assert.equal(
    resolveReportDetailState({
      isLoading: false,
      error: null,
      report: { id: "r1" },
    }),
    "ready",
  );
});

test("the first screen gate prefers G-Publish", () => {
  assert.equal(
    gateLine([
      { gate_id: "G7", status: "pass" },
      { gate_id: "G-Publish", status: "pending" },
    ]),
    "G-Publish PENDING",
  );
  assert.equal(gateLine([]), null);
});

test("an expired gate says the authorization expired", () => {
  assert.equal(
    gateLine([{ gate_id: "G-Publish", status: "expired" }]),
    "G-Publish 授权已过期，门禁失效",
  );
});

test("only http, https and relative links are safe", () => {
  assert.equal(isSafeLink("https://example.com/a"), true);
  assert.equal(isSafeLink("http://example.com/a"), true);
  assert.equal(isSafeLink("/reports/r1"), true);
  assert.equal(isSafeLink("javascript:alert(1)"), false);
  assert.equal(isSafeLink("//evil.example/a"), false);
  assert.equal(isSafeLink("data:text/html,x"), false);
  assert.equal(isSafeLink(null), false);
});

test("template labels fall back to the raw id", () => {
  assert.equal(templateLabel("t1_voc"), "T1 VOC");
  assert.equal(templateLabel("t9_unknown"), "t9_unknown");
  assert.equal(templateLabel(null), "未生成合同");
});

test("every claim status returns a display label", () => {
  for (const status of CLAIM_STATUSES as readonly ClaimStatus[]) {
    const display = claimStatusDisplay(status, "L4_authorized_live");
    assert.notEqual(display.label, "");
  }
});

test("a bare Not Found detail means the contract endpoint is missing", () => {
  // FastAPI 对没有挂载的路由返回 {"detail": "Not Found"}。
  assert.equal(classifyContract404("Not Found"), "endpoint_missing");
  assert.equal(classifyContract404("  Not Found  "), "endpoint_missing");
});

test("a business detail means the contract is not generated", () => {
  // 路由已挂载、资源不存在时，后端返回业务文案。
  assert.equal(classifyContract404("Report not found"), "not_generated");
  assert.equal(classifyContract404("report_not_found"), "not_generated");
});

test("an ambiguous 404 defaults to endpoint_missing", () => {
  // 无法可靠区分时不得谎报「数据未生成」。
  assert.equal(classifyContract404(null), "endpoint_missing");
  assert.equal(classifyContract404(undefined), "endpoint_missing");
  assert.equal(classifyContract404(""), "endpoint_missing");
  assert.equal(classifyContract404("API error 404"), "endpoint_missing");
});

test("the three contract results take three distinct render branches", () => {
  // ok 渲染合同正文。两个缺口各走一条分支，文案不同。
  assert.equal(contractRenderBranch({ kind: "ok" }), "contract");
  assert.equal(
    contractRenderBranch({ kind: "not_generated" }),
    "not_generated",
  );
  assert.equal(
    contractRenderBranch({ kind: "endpoint_missing" }),
    "endpoint_missing",
  );
  assert.equal(contractRenderBranch(undefined), null);

  const branches = new Set([
    contractRenderBranch({ kind: "ok" }),
    contractRenderBranch({ kind: "not_generated" }),
    contractRenderBranch({ kind: "endpoint_missing" }),
  ]);
  assert.equal(branches.size, 3);

  // endpoint_missing 必须用 alert，用户要看到这是接口缺口。
  assert.equal(
    contractGapView({ kind: "endpoint_missing", endpoint: "/x" }).role,
    "alert",
  );
});

test("the two contract gaps render with different copy and roles", () => {
  const endpoint = contractEndpointPath("r1");
  const notGenerated = contractGapView({ kind: "not_generated", endpoint });
  const missing = contractGapView({ kind: "endpoint_missing", endpoint });

  assert.notEqual(notGenerated.title, missing.title);
  assert.notEqual(notGenerated.hint, missing.hint);
  assert.equal(notGenerated.role, "status");
  assert.equal(notGenerated.retryable, true);
  assert.equal(missing.role, "alert");
  assert.equal(missing.retryable, false);
});

test("the endpoint_missing gap names the missing endpoint", () => {
  const view = contractGapView({
    kind: "endpoint_missing",
    endpoint: "/api/reports/r1/contract",
  });
  assert.equal(view.role, "alert");
  assert.equal(view.hint.includes("/api/reports/r1/contract"), true);
  assert.equal(view.hint.includes("不表示报告数据缺失"), true);
});

test("contract absence text separates missing data from a missing endpoint", () => {
  assert.equal(contractAbsenceText("not_generated"), "本合同尚未生成");
  assert.equal(contractAbsenceText("endpoint_missing"), "合同接口未提供");
});

test("the report list waits for the contract interface", () => {
  // 列表三列不得显示「未生成合同」。
  assert.equal(LIST_CONTRACT_PENDING_LABEL, "待合同接口");
  assert.equal(LIST_CONTRACT_PENDING_LABEL.includes("未生成"), false);
});

test("the contract endpoint path encodes the report id", () => {
  assert.equal(contractEndpointPath("r 1"), "/api/reports/r%201/contract");
});
