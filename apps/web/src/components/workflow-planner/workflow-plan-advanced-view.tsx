import type { WorkflowPlanPreview } from "@/types/workflow-planner";

function EmptyValue() {
  return <span className="text-[#9A8A85]">none</span>;
}

export function WorkflowPlanAdvancedView({
  preview,
}: {
  preview: WorkflowPlanPreview;
}) {
  const primaries = preview.routePlans.flatMap((route) =>
    route.primaryImplementation
      ? [{ requirementRef: route.requirementRef, ...route.primaryImplementation }]
      : [],
  );
  const fallbacks = preview.routePlans.flatMap((route) =>
    route.fallbackImplementations.map((fallback) => ({
      requirementRef: route.requirementRef,
      ...fallback,
    })),
  );
  const shadows = preview.routePlans;

  return (
    <div className="min-w-0 space-y-6 text-sm">
      <section className="min-w-0">
        <h3 className="font-semibold text-[#392823]">Query Terms</h3>
        <div className="mt-2 max-w-full overflow-x-auto rounded-xl border border-[#E8DDD6]">
          <table className="min-w-full divide-y divide-[#E8DDD6] text-left">
            <thead className="bg-[#FBF8F5] text-xs text-[#765B54]">
              <tr>
                <th className="px-3 py-2">Term</th>
                <th className="px-3 py-2">Origin</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Scope key</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EEE6E1] bg-white">
              {preview.queryTerms.map((term, index) => (
                <tr key={`${term.scopeKey}-${term.normalizedTerm}-${index}`}>
                  <td className="break-words px-3 py-2">{term.term}</td>
                  <td className="px-3 py-2">{term.origin}</td>
                  <td className="px-3 py-2">{term.status}</td>
                  <td className="break-all px-3 py-2 font-mono text-xs">
                    {term.scopeKey}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="min-w-0">
        <h3 className="font-semibold text-[#392823]">Compiled Queries</h3>
        <div className="mt-2 max-w-full overflow-x-auto rounded-xl border border-[#E8DDD6]">
          <table className="min-w-full divide-y divide-[#E8DDD6] text-left">
            <thead className="bg-[#FBF8F5] text-xs text-[#765B54]">
              <tr>
                <th className="px-3 py-2">Platform</th>
                <th className="px-3 py-2">Resource / Operation</th>
                <th className="px-3 py-2">Expression</th>
                <th className="px-3 py-2">Query version</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EEE6E1] bg-white">
              {preview.compiledQueries.map((query, index) => (
                <tr
                  key={`${query.platform}-${query.resourceType}-${query.operation}-${index}`}
                >
                  <td className="px-3 py-2">{query.platform}</td>
                  <td className="px-3 py-2">
                    {query.resourceType} / {query.operation}
                  </td>
                  <td className="max-w-lg break-words px-3 py-2">
                    {query.normalizedExpression}
                  </td>
                  <td className="break-all px-3 py-2 font-mono text-xs">
                    {query.queryVersion}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="min-w-0 rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-4">
        <h3 className="font-semibold text-[#392823]">Workflow Steps</h3>
        <div className="mt-3 grid min-w-0 gap-3">
          {preview.steps.map((step) => (
            <article
              className="min-w-0 rounded-lg border border-[#EEE6E1] bg-white p-3"
              key={step.stepRef}
            >
              <p className="break-all font-mono text-xs text-[#765B54]">
                {step.stepRef}
              </p>
              <p className="mt-1 font-semibold text-[#463530]">
                {step.sequence}. {step.label} · {step.planningStatus}
              </p>
              <p className="mt-1 break-words text-xs text-[#716562]">
                depends_on: {step.dependsOn.join(", ") || "none"}
              </p>
              <p className="mt-1 break-words text-xs text-[#716562]">
                input: {step.inputContract.fields.map((field) => field.name).join(", ") || "none"}
              </p>
              <p className="mt-1 break-words text-xs text-[#716562]">
                output: {step.outputContract.fields.map((field) => field.name).join(", ") || "none"}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="min-w-0 rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-4">
        <h3 className="font-semibold text-[#392823]">Route Requirements</h3>
        <div className="mt-3 grid min-w-0 gap-3">
          {preview.routeRequirements.map((requirement) => (
            <article
              className="min-w-0 rounded-lg border border-[#EEE6E1] bg-white p-3"
              key={requirement.requirementRef}
            >
              <p className="break-all font-mono text-xs text-[#765B54]">
                {requirement.requirementRef}
              </p>
              <p className="mt-1 text-[#463530]">
                {requirement.platform} · {requirement.resourceType} / {requirement.operation}
              </p>
              <p className="mt-1 break-words text-xs text-[#716562]">
                Required: {requirement.requiredFields.join(", ") || "none"} · Optional: {requirement.optionalFields.join(", ") || "none"}
              </p>
              {requirement.preconditionFailures.length > 0 ? (
                <p className="mt-1 break-words text-xs text-[#9B5143]">
                  Precondition failures: {requirement.preconditionFailures.map((reason) => `${reason.code}: ${reason.reason}`).join("; ")}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      <section className="min-w-0 rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-4">
        <h3 className="font-semibold text-[#392823]">Route Plans</h3>
        <div className="mt-3 grid min-w-0 gap-3">
          {preview.routePlans.map((route) => (
            <article
              className="min-w-0 rounded-lg border border-[#EEE6E1] bg-white p-3"
              key={route.requirementRef}
            >
              <p className="break-all font-mono text-xs text-[#765B54]">
                {route.requirementRef}
              </p>
              <p className="mt-1 font-semibold text-[#463530]">
                {route.status} · budget={route.budgetStatus} · readiness={route.readinessStatus ?? "none"}
              </p>
              <p className="mt-1 break-words text-xs text-[#716562]">
                Required: {route.requiredFields.join(", ") || "none"} · Optional: {route.optionalFields.join(", ") || "none"} · Missing optional: {route.missingOptionalFields.join(", ") || "none"}
              </p>
              <p className="mt-1 break-words text-xs text-[#716562]">
                Gates: {route.policyGates.map((reason) => `${reason.code}: ${reason.reason}`).join("; ") || "none"}
              </p>
              <p className="mt-1 break-words text-xs text-[#716562]">
                Exclusions: {route.exclusionReasons.map((reason) => `${reason.code}: ${reason.reason}`).join("; ") || "none"}
              </p>
              {route.scoreBreakdown ? (
                <div className="mt-2 min-w-0 space-y-1 font-mono text-xs text-[#716562]">
                  <p className="break-words">
                    weighted_score={route.scoreBreakdown.weightedScore}
                  </p>
                  <p className="break-all">
                    raw_dimensions={JSON.stringify(route.scoreBreakdown.rawDimensions)}
                  </p>
                  <p className="break-all">
                    effective_dimensions={JSON.stringify(route.scoreBreakdown.effectiveDimensions)}
                  </p>
                  <p className="break-all">
                    weights={JSON.stringify(route.scoreBreakdown.weights)}
                  </p>
                  <p className="break-words">
                    trace_codes={route.scoreBreakdown.traceCodes.join(", ") || "none"}
                  </p>
                </div>
              ) : (
                <p className="mt-1 text-xs text-[#716562]">score_breakdown=none</p>
              )}
              <p className="mt-1 font-mono text-xs text-[#716562]">
                route_execution_authorized={String(route.executionAuthorized)}
              </p>
            </article>
          ))}
        </div>
      </section>

      {primaries.length > 0 ? (
        <section
          className="min-w-0 rounded-xl border border-[#BFD4C5] bg-[#F3FAF5] p-4"
          data-testid="workflow-planner-primary"
        >
          <h3 className="font-semibold text-[#31583E]">Primary</h3>
          {primaries.map((primary) => (
            <div className="mt-2 min-w-0" key={primary.requirementRef}>
              <p className="break-all font-mono text-xs">
                {primary.implementationId}
              </p>
              <p className="mt-1 text-xs">
                score={primary.weightedScore ?? "none"} · status={primary.capabilityStatus} · readiness={primary.readinessStatus}
              </p>
              <p className="mt-1 break-words text-xs">
                Evidence: {primary.evidenceRefs.join(", ") || "none"}
              </p>
            </div>
          ))}
        </section>
      ) : null}

      {fallbacks.length > 0 ? (
        <section
          className="min-w-0 rounded-xl border border-[#D7CBE4] bg-[#FAF7FD] p-4"
          data-testid="workflow-planner-fallback"
        >
          <h3 className="font-semibold text-[#58436D]">Fallback</h3>
          {fallbacks.map((fallback) => (
            <div
              className="mt-2 min-w-0"
              key={`${fallback.requirementRef}-${fallback.implementationId}`}
            >
              <p className="break-all font-mono text-xs">
                {fallback.implementationId}
              </p>
              <p className="mt-1 text-xs">
                score={fallback.weightedScore ?? "none"} · approval_required={String(fallback.approvalRequired)}
              </p>
              <p className="mt-1 break-words text-xs">
                Evidence: {fallback.evidenceRefs.join(", ") || "none"}
              </p>
            </div>
          ))}
        </section>
      ) : null}

      {shadows.length > 0 ? (
        <section
          className="min-w-0 rounded-xl border border-[#D4D0C4] bg-[#FAF9F4] p-4"
          data-testid="workflow-planner-shadow"
        >
          <h3 className="font-semibold text-[#5F5948]">Shadow</h3>
          {shadows.map((route) => (
            <p
              className="mt-2 break-all font-mono text-xs"
              key={route.requirementRef}
            >
              {route.requirementRef}: enabled={String(route.shadowRule.enabled)} · fallback={route.shadowRule.fallbackImplementationId ?? "none"} · sample_rate={route.shadowRule.sampleRate ?? "none"} · reason={route.shadowRule.reason} · shadow_execution_authorized={String(route.shadowRule.executionAuthorized)}
            </p>
          ))}
        </section>
      ) : null}

      <section className="min-w-0 rounded-xl border border-[#E8DDD6] bg-[#FFFDFC] p-4">
        <h3 className="font-semibold text-[#392823]">Versions and flags</h3>
        <dl className="mt-3 grid min-w-0 gap-2 sm:grid-cols-2">
          <div className="min-w-0">
            <dt className="text-xs font-semibold text-[#765B54]">Catalog snapshot</dt>
            <dd className="break-all font-mono text-xs">{preview.catalogSnapshotId}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-xs font-semibold text-[#765B54]">Policy</dt>
            <dd className="break-all font-mono text-xs">{preview.policyVersion}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-xs font-semibold text-[#765B54]">Template</dt>
            <dd className="break-all font-mono text-xs">{preview.modeTemplateVersion}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-xs font-semibold text-[#765B54]">Query versions</dt>
            <dd className="break-all font-mono text-xs">
              {Object.entries(preview.queryVersions)
                .map(([platform, version]) => `${platform}:${version}`)
                .join(", ") || <EmptyValue />}
            </dd>
          </div>
        </dl>
        <p className="mt-3 break-words font-mono text-xs text-[#765B54]">
          execution_authorized={String(preview.executionAuthorized)} · provider_call={String(preview.providerCall)} · actor_run={String(preview.actorRun)} · browser_run={String(preview.browserRun)} · llm_call={String(preview.llmCall)} · workflow_run_created={String(preview.workflowRunCreated)} · database_write={String(preview.databaseWrite)}
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
