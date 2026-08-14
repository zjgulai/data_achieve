import type { WorkflowPlanPreview } from "@/types/workflow-planner";

function unclassifiedSeedUrls(preview: WorkflowPlanPreview): string[] {
  return preview.decisionTrace.inputDiagnostics.flatMap((entry) => {
    const seedUrl = entry.details.seed_url;
    return entry.code === "seed_url_unclassified" && typeof seedUrl === "string"
      ? [seedUrl]
      : [];
  });
}

export function WorkflowPlanSimpleView({
  preview,
}: {
  preview: WorkflowPlanPreview;
}) {
  const approvalRoutes = preview.routePlans.filter(
    (route) => route.approvalRequired,
  );
  const seedUrls = unclassifiedSeedUrls(preview);
  const knownCost = preview.budgetSummary.knownSelectedUnitCost;

  return (
    <div className="min-w-0 space-y-5">
      <section className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#8B7770]">
            Planning status
          </p>
          <p className="mt-1 break-words font-semibold text-[#392823]">
            {preview.planningStatus}
          </p>
        </div>
        <div className="rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#8B7770]">
            Coverage
          </p>
          <p className="mt-1 break-words font-mono text-xs font-semibold text-[#392823]">
            total={preview.coverage.totalRequirements} · resolved=
            {preview.coverage.resolvedRequirements} · partial=
            {preview.coverage.partialRequirements} · held=
            {preview.coverage.heldRequirements}
          </p>
        </div>
        <div className="rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#8B7770]">
            预算状态
          </p>
          <p className="mt-1 font-semibold text-[#392823]">
            {preview.budgetSummary.budgetStatus}
          </p>
        </div>
        <div className="rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#8B7770]">
            已知成本
          </p>
          <p className="mt-1 font-semibold text-[#392823]">
            {knownCost === null
              ? "未知"
              : `${knownCost} ${preview.budgetSummary.currency}`}
          </p>
          {preview.budgetSummary.unknownCount > 0 ? (
            <p className="mt-1 text-xs text-[#7A625A]">
              另有 {preview.budgetSummary.unknownCount} 条成本未知
            </p>
          ) : null}
        </div>
      </section>

      <section className="min-w-0 rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-4">
        <h3 className="font-semibold text-[#392823]">Scope 与平台覆盖</h3>
        <div className="mt-3 grid min-w-0 gap-2">
          {preview.normalizedInput.scopes.map((scope) => (
            <article
              className="min-w-0 rounded-lg border border-[#EEE6E1] bg-white px-3 py-2"
              key={scope.scopeKey}
            >
              <p className="break-words text-sm font-semibold text-[#463530]">
                {scope.scopeType} · {scope.canonicalTerm ?? "Seed-URL-only"}
              </p>
              <p className="mt-1 break-words text-xs text-[#716562]">
                平台：{scope.effectivePlatforms.join("、") || "未分类"}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="min-w-0 rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-4">
        <h3 className="font-semibold text-[#392823]">计划步骤</h3>
        <ol className="mt-3 grid min-w-0 gap-2">
          {preview.steps.map((step) => (
            <li
              className="min-w-0 rounded-lg border border-[#EEE6E1] bg-white px-3 py-2 text-sm"
              key={step.stepRef}
            >
              <span className="font-semibold text-[#463530]">
                {step.sequence}. {step.label}
              </span>
              <span className="ml-2 text-[#7A625A]">
                {step.planningStatus}
              </span>
            </li>
          ))}
        </ol>
      </section>

      {approvalRoutes.length > 0 ? (
        <section className="min-w-0 rounded-xl border border-[#E4B9A7] bg-[#FFF5EF] p-4">
          <h3 className="font-semibold text-[#803F32]">仍需审批</h3>
          <p className="mt-2 text-sm leading-6 text-[#6F514A]">
            当前只预览降级路线，不构成执行授权。
          </p>
          {approvalRoutes.map((route) => (
            <div className="mt-3 min-w-0" key={route.requirementRef}>
              <p className="break-all text-xs font-semibold text-[#765B54]">
                {route.requirementRef}
              </p>
              {route.missingOptionalFields.length > 0 ? (
                <p className="mt-1 break-words text-sm text-[#765B54]">
                  缺少 Optional Fields：
                  {route.missingOptionalFields.join("、")}
                </p>
              ) : null}
              {route.approvalReasons.map((reason) => (
                <p
                  className="mt-1 break-words text-sm text-[#765B54]"
                  key={`${route.requirementRef}-${reason.code}`}
                >
                  {reason.code}: {reason.reason}
                </p>
              ))}
            </div>
          ))}
        </section>
      ) : null}

      {seedUrls.length > 0 ? (
        <section
          className="min-w-0 rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-4"
          data-testid="workflow-planner-unclassified-url"
        >
          <h3 className="font-semibold text-[#392823]">未分类 Seed URL</h3>
          <ul className="mt-2 grid min-w-0 gap-1">
            {seedUrls.map((seedUrl) => (
              <li className="break-all text-sm text-[#765B54]" key={seedUrl}>
                {seedUrl}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="min-w-0 rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-4">
        <h3 className="font-semibold text-[#392823]">限制与未来执行</h3>
        <div className="mt-2 grid min-w-0 gap-2">
          {preview.routePlans.map((route) => (
            <div className="min-w-0" key={route.requirementRef}>
              {route.exclusionReasons.map((reason) => (
                <p
                  className="break-words text-sm leading-6 text-[#716562]"
                  key={`${route.requirementRef}-exclusion-${reason.code}`}
                >
                  {reason.code}: {reason.reason}
                </p>
              ))}
              {route.approvalReasons.map((reason) => (
                <p
                  className="break-words text-sm leading-6 text-[#716562]"
                  key={`${route.requirementRef}-approval-${reason.code}`}
                >
                  {reason.code}: {reason.reason}
                </p>
              ))}
              {route.limitations.map((limitation) => (
                <p
                  className="break-words text-sm leading-6 text-[#716562]"
                  key={`${route.requirementRef}-limitation-${limitation}`}
                >
                  {limitation}
                </p>
              ))}
            </div>
          ))}
        </div>
        {preview.limitations.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-[#716562]">
            {preview.limitations.map((limitation) => (
              <li className="break-words" key={limitation}>
                {limitation}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-[#716562]">响应未声明额外限制。</p>
        )}
        <p className="mt-3 text-sm font-semibold text-[#803F32]">
          {preview.planningStatus === "held"
            ? "当前没有可进入未来执行的路线。"
            : "路线仅完成规划资格判断，仍未获得执行授权。"}
        </p>
        <p className="mt-1 font-mono text-xs text-[#765B54]">
          execution_authorized={String(preview.executionAuthorized)}
        </p>
      </section>

      <p
        className="min-w-0 break-all rounded-lg bg-[#F6F1EE] px-3 py-2 font-mono text-xs text-[#765B54]"
        data-testid="workflow-planner-fingerprint"
      >
        {preview.previewFingerprint}
      </p>
    </div>
  );
}
