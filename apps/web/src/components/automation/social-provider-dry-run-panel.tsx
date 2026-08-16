"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileSearch,
  Globe2,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  checkSocialProviderReadiness,
  getSocialProviderCatalog,
  previewSocialProviderAdapterPlan,
  previewSocialDataset,
  previewSocialProviderSourceTemplate,
  previewSocialTaskRunApprovalTemplate,
  runSocialExecutionDryRun,
} from "@/lib/api/social-provider";
import {
  getDefaultEndpointForPlatform,
  getSocialProviderUiConfig,
  socialProviderUiConfigs,
} from "@/lib/social-provider-config";
import { cn } from "@/lib/utils";
import {
  WorkbenchFact,
  WorkbenchMetricPill,
  WorkbenchPanel,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import type {
  SocialDatasetPreview,
  SocialExecutionDryRun,
  SocialProviderAdapterPlan,
  SocialProviderCatalogItem,
  SocialProviderPlatform,
  SocialProviderReadiness,
  SocialProviderSourceTemplate,
  SocialTaskRunApprovalTemplate,
} from "@/types/social-provider";

const stageLabels: Record<SocialExecutionDryRun["executionPlan"][number]["stage"], string> = {
  dataset_preview: "Dataset Preview",
  normalization_preview: "Normalization",
  raw_preview: "Raw Preview",
  readiness: "Readiness",
  source_template: "Source Template",
  task_run_approval_template: "TaskRun Packet",
};

export function SocialProviderDryRunPanel() {
  const [platform, setPlatform] = useState<SocialProviderPlatform>("youtube");
  const [endpoint, setEndpoint] = useState(getDefaultEndpointForPlatform("youtube"));
  const [fixtureLimit, setFixtureLimit] = useState("2");
  const [credentialReference, setCredentialReference] = useState(
    "vault:overseas-social-readonly",
  );
  const [catalogProvider, setCatalogProvider] = useState<SocialProviderCatalogItem | null>(null);
  const [readiness, setReadiness] = useState<SocialProviderReadiness | null>(null);
  const [adapterPlan, setAdapterPlan] = useState<SocialProviderAdapterPlan | null>(null);
  const [datasetPreview, setDatasetPreview] = useState<SocialDatasetPreview | null>(null);
  const [sourceTemplate, setSourceTemplate] = useState<SocialProviderSourceTemplate | null>(null);
  const [approvalTemplate, setApprovalTemplate] = useState<SocialTaskRunApprovalTemplate | null>(
    null,
  );
  const [result, setResult] = useState<SocialExecutionDryRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedProviderConfig = getSocialProviderUiConfig(platform);
  const sideEffectFacts = useMemo(() => {
    if (!result) {
      return [];
    }
    return [
      ["provider_call_attempted", String(result.providerCallAttempted)],
      ["credential_read_attempted", String(result.credentialReadAttempted)],
      ["task_run_allowed", String(result.taskRunAllowed)],
      ["dataset_write_allowed", String(result.datasetWriteAllowed)],
      ["production_write_allowed", String(result.productionWriteAllowed)],
    ];
  }, [result]);
  const readinessFacts = useMemo(() => {
    if (!readiness) {
      return [];
    }
    return [
      ["readiness", String(readiness.ready)],
      ["declared_readiness", String(readiness.declaredReadiness)],
      ["readiness_basis", readiness.readinessBasis],
      ["execution_enabled", String(readiness.executionEnabled)],
      ["provider_call_allowed", String(readiness.providerCallAllowed)],
      ["provider_call_attempted", String(readiness.providerCallAttempted)],
      ["missing_credentials", joinOrNone(readiness.missingCredentials)],
      ["missing_scope", joinOrNone(readiness.missingScope)],
      ["budget_status", readiness.rateLimitProfile.budgetStatus],
    ];
  }, [readiness]);
  const catalogFacts = useMemo(() => {
    if (!catalogProvider) {
      return [];
    }
    return [
      ["provider_id", catalogProvider.providerId],
      ["stability", catalogProvider.stability],
      ["self_host_priority", catalogProvider.selfHostPriority],
      ["sdk_status", catalogProvider.sdkSelection?.status ?? "none"],
      ["api_version", catalogProvider.apiVersion],
      ["auth_mode", catalogProvider.authMode],
    ];
  }, [catalogProvider]);
  const adapterPlanFacts = useMemo(() => {
    if (!adapterPlan) {
      return [];
    }
    return [
      ["provider_id", adapterPlan.providerId],
      ["sdk_package", adapterPlan.sdkSelection?.package ?? "none"],
      ["dependency_present", String(adapterPlan.dependencyPresent)],
      ["adapter_ready", String(adapterPlan.adapterReady)],
      ["fixture_replay_supported", String(adapterPlan.fixtureReplaySupported)],
      ["live_client_created", String(adapterPlan.liveClientCreated)],
      ["provider_call_attempted", String(adapterPlan.providerCallAttempted)],
      ["credential_read_attempted", String(adapterPlan.credentialReadAttempted)],
      ["production_write_allowed", String(adapterPlan.productionWriteAllowed)],
    ];
  }, [adapterPlan]);
  const datasetGateFacts = useMemo(() => {
    if (!datasetPreview) {
      return [];
    }
    return [
      ["row_count", String(datasetPreview.rowCount)],
      ["source_item_count", String(datasetPreview.sourceItemCount)],
      ["max_rows", String(datasetPreview.maxRows)],
      ["truncated", String(datasetPreview.truncated)],
      ["dataset_write_allowed", String(datasetPreview.datasetWriteAllowed)],
      ["dataset_created", String(datasetPreview.datasetCreated)],
      ["export_created", String(datasetPreview.exportCreated)],
      ["provider_call_attempted", String(datasetPreview.providerCallAttempted)],
    ];
  }, [datasetPreview]);
  const sourceTemplateFacts = useMemo(() => {
    if (!sourceTemplate) {
      return [];
    }
    return [
      ["source_type", sourceTemplate.sourceType],
      ["template_strategy", sourceTemplate.templateStrategy],
      ["source_create_allowed", String(sourceTemplate.sourceCreateAllowed)],
      ["source_created", String(sourceTemplate.sourceCreated)],
      ["task_created", String(sourceTemplate.taskCreated)],
      ["payload_present", String(sourceTemplate.payloadPresent)],
    ];
  }, [sourceTemplate]);
  const approvalTemplateFacts = useMemo(() => {
    if (!approvalTemplate) {
      return [];
    }
    return [
      ["task_run_allowed", String(approvalTemplate.taskRunAllowed)],
      ["dataset_write_allowed", String(approvalTemplate.datasetWriteAllowed)],
      ["export_allowed", String(approvalTemplate.exportAllowed)],
      ["production_write_allowed", String(approvalTemplate.productionWriteAllowed)],
      ["packet_schema", recordString(approvalTemplate.approvalPacket, "schema_version")],
      ["next_authorization", approvalTemplate.nextRequiredAuthorization],
    ];
  }, [approvalTemplate]);

  async function submitDryRun() {
    setLoading(true);
    setError(null);
    try {
      const parsedFixtureLimit = Number.parseInt(fixtureLimit, 10);
      const safeFixtureLimit = Number.isFinite(parsedFixtureLimit) ? parsedFixtureLimit : 2;
      const datasetName = `${selectedProviderConfig.label} ${endpoint} VOC fixture`;
      const sourceName = `${selectedProviderConfig.label} ${endpoint} fixture source`;
      const taskName = `${selectedProviderConfig.label} ${endpoint} fixture task`;
      const credentialRef = credentialReference.trim() || undefined;
      const catalog = await getSocialProviderCatalog(platform);
      setCatalogProvider(catalog.providers[0] ?? null);
      const nextReadiness = await checkSocialProviderReadiness({
        platform,
        endpoints: [endpoint],
      });
      setReadiness(nextReadiness);
      const nextAdapterPlan = await previewSocialProviderAdapterPlan({
        platform,
        endpoints: [endpoint],
        fixtureLimit: safeFixtureLimit,
        maxRequests: 5,
      });
      setAdapterPlan(nextAdapterPlan);
      const nextDatasetPreview = await previewSocialDataset({
        platform,
        endpoint,
        fixtureLimit: safeFixtureLimit,
        datasetName,
        maxRows: 20,
      });
      setDatasetPreview(nextDatasetPreview);
      const nextSourceTemplate = await previewSocialProviderSourceTemplate({
        platform,
        endpoints: [endpoint],
        sourceName,
        fixtureLimit: safeFixtureLimit,
      });
      setSourceTemplate(nextSourceTemplate);
      const nextApprovalTemplate = await previewSocialTaskRunApprovalTemplate({
        platform,
        endpoints: [endpoint],
        intendedUse: `fixture-only ${platform} ${endpoint} social review`,
        sourceName,
        taskName,
        datasetName,
        credentialReference: credentialRef,
        maxItems: 20,
        maxRequests: 5,
        maxRows: 20,
      });
      setApprovalTemplate(nextApprovalTemplate);
      const dryRun = await runSocialExecutionDryRun({
        platform,
        endpoint,
        fixtureLimit: safeFixtureLimit,
        intendedUse: `fixture-only ${platform} ${endpoint} social review`,
        datasetName,
        sourceName,
        taskName,
        credentialReference: credentialRef,
        maxItems: 20,
        maxRequests: 5,
        maxRows: 20,
      });
      setResult(dryRun);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "social execution dry-run unavailable");
    } finally {
      setLoading(false);
    }
  }

  function selectPlatform(nextPlatform: SocialProviderPlatform) {
    setPlatform(nextPlatform);
    setEndpoint(getDefaultEndpointForPlatform(nextPlatform));
    setCatalogProvider(null);
    setReadiness(null);
    setAdapterPlan(null);
    setDatasetPreview(null);
    setSourceTemplate(null);
    setApprovalTemplate(null);
    setResult(null);
    setError(null);
  }

  return (
    <WorkbenchPanel
      action={<WorkbenchTag tone="green">provider_call=false</WorkbenchTag>}
      icon={Globe2}
      label="Social API"
      subtitle="Overseas official API fixture-only execution review"
      title="海外社媒采集预案"
    >
      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        <form
          className="grid min-w-0 gap-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3"
          onSubmit={(event) => {
            event.preventDefault();
            void submitDryRun();
          }}
        >
          <div className="grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-1">
            <label className="grid min-w-0 gap-2 text-sm font-semibold text-[#3B2924]">
              <span>平台</span>
              <select
                className="h-11 w-full min-w-0 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                onChange={(event) => {
                  selectPlatform(event.target.value as SocialProviderPlatform);
                }}
                value={platform}
              >
                {socialProviderUiConfigs.map((config) => (
                  <option key={config.platform} value={config.platform}>
                    {config.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="grid min-w-0 gap-2 text-sm font-semibold text-[#3B2924]">
              <span>Endpoint</span>
              <select
                className="h-11 w-full min-w-0 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                onChange={(event) => setEndpoint(event.target.value)}
                value={endpoint}
              >
                {selectedProviderConfig.endpoints.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="grid min-w-0 gap-2 text-sm font-semibold text-[#3B2924]">
            <span>Fixture limit</span>
            <input
              className="h-11 w-full min-w-0 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
              max={10}
              min={1}
              onChange={(event) => setFixtureLimit(event.target.value)}
              type="number"
              value={fixtureLimit}
            />
          </label>

          <label className="grid min-w-0 gap-2 text-sm font-semibold text-[#3B2924]">
            <span>Credential reference</span>
            <input
              className="h-11 w-full min-w-0 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
              onChange={(event) => setCredentialReference(event.target.value)}
              value={credentialReference}
            />
          </label>

          <button
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white shadow-[0_8px_18px_rgba(201,111,92,0.2)] transition hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:bg-[#D9B3AA]"
            disabled={loading}
            type="submit"
          >
            {loading ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <FileSearch size={16} aria-hidden="true" />}
            生成预案
          </button>
        </form>

        <div className="grid min-w-0 gap-4">
          {error ? (
            <div className="rounded-xl border border-[#FFD0C8] bg-[#FFF1EC] p-3 text-sm font-semibold text-[#B85F4F]">
              {error}
            </div>
          ) : null}

          {result ? (
            <>
              <div className="grid min-w-0 gap-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[#2E201C]">Readiness Review</p>
                  <WorkbenchTag tone={readiness?.executionEnabled ? "green" : "amber"}>
                    {readiness
                      ? `execution_enabled=${String(readiness.executionEnabled)}`
                      : "execution=pending"}
                  </WorkbenchTag>
                </div>
                <div className="grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {readinessFacts.map(([label, value]) => (
                    <WorkbenchFact key={label} label={label} value={value} />
                  ))}
                </div>
              </div>

              <div className="grid min-w-0 gap-3 rounded-xl border border-[#F0E1D9] bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[#2E201C]">Catalog Boundary</p>
                  <WorkbenchTag tone="neutral">provider_call=false</WorkbenchTag>
                </div>
                <div className="grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {catalogFacts.map(([label, value]) => (
                    <WorkbenchFact key={label} label={label} value={value} />
                  ))}
                </div>
                {catalogProvider?.policyFlags.length ? (
                  <div className="flex flex-wrap gap-2">
                    {catalogProvider.policyFlags.slice(0, 4).map((flag) => (
                      <WorkbenchTag key={flag} tone="rose">
                        {flag}
                      </WorkbenchTag>
                    ))}
                  </div>
                ) : null}
              </div>

              {adapterPlan ? (
                <div className="grid min-w-0 gap-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="break-words text-sm font-semibold text-[#2E201C]">
                      Adapter Plan Gate
                    </p>
                    <WorkbenchTag tone="neutral">live_client_created=false</WorkbenchTag>
                  </div>
                  <div className="grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {adapterPlanFacts.map(([label, value]) => (
                      <WorkbenchFact key={label} label={label} value={value} />
                    ))}
                  </div>
                  {adapterPlan.adapterModule ? (
                    <p className="break-all text-xs font-semibold text-[#7A625A]">
                      {adapterPlan.adapterModule}
                    </p>
                  ) : null}
                  <div className="grid min-w-0 gap-2">
                    {adapterPlan.plannedOperations.slice(0, 3).map((operation, index) => (
                      <div
                        className="grid min-w-0 gap-2 rounded-lg bg-white px-3 py-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_120px]"
                        key={`${operation.endpoint}-${index}`}
                      >
                        <p className="break-words text-sm font-semibold text-[#3B2924]">
                          {operation.operation || "fixture_replay"}
                        </p>
                        <p className="break-words text-sm text-[#7A625A]">
                          {operation.endpoint || "unknown endpoint"}
                        </p>
                        <p className="text-xs font-semibold text-[#B47767]">
                          {operation.mode || "fixture"} / provider_call=
                          {String(operation.providerCall)} / limit={operation.fixtureLimit}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {datasetPreview ? (
                <div className="grid min-w-0 gap-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="break-words text-sm font-semibold text-[#2E201C]">
                      Dataset Preview Gate
                    </p>
                    <WorkbenchTag tone="neutral">dataset_write=false</WorkbenchTag>
                  </div>
                  <p className="break-words text-sm font-semibold text-[#3B2924]">
                    {datasetPreview.datasetName}
                  </p>
                  <div className="grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-4">
                    {datasetGateFacts.map(([label, value]) => (
                      <WorkbenchFact key={label} label={label} value={value} />
                    ))}
                  </div>
                  <div className="grid min-w-0 gap-2">
                    {datasetPreview.rows.slice(0, 3).map((row) => (
                      <div className="rounded-lg bg-white px-3 py-2" key={row.rowId}>
                        <p className="break-words text-sm font-semibold text-[#3B2924]">
                          {row.textExcerpt || row.sourceSchemaVersion}
                        </p>
                        <p className="mt-1 break-all text-xs text-[#86868B]">
                          {row.rawRecordId} / {row.evidenceRef}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {sourceTemplate ? (
                <div className="grid min-w-0 gap-3 rounded-xl border border-[#F0E1D9] bg-white p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="break-words text-sm font-semibold text-[#2E201C]">
                      Source Template Gate
                    </p>
                    <WorkbenchTag tone="neutral">source_created=false</WorkbenchTag>
                  </div>
                  <div className="grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {sourceTemplateFacts.map(([label, value]) => (
                      <WorkbenchFact key={label} label={label} value={value} />
                    ))}
                  </div>
                  {sourceTemplate.blockedReasons.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {sourceTemplate.blockedReasons.slice(0, 4).map((reason) => (
                        <WorkbenchTag key={reason} tone="amber">
                          {reason}
                        </WorkbenchTag>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {approvalTemplate ? (
                <div className="grid min-w-0 gap-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="break-words text-sm font-semibold text-[#2E201C]">
                      L4 Approval Packet Gate
                    </p>
                    <WorkbenchTag tone="amber">review_only</WorkbenchTag>
                  </div>
                  <div className="grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {approvalTemplateFacts.map(([label, value]) => (
                      <WorkbenchFact key={label} label={label} value={value} />
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {approvalTemplate.requiredConfirmations.slice(0, 4).map((confirmation) => (
                      <WorkbenchTag key={confirmation} tone="rose">
                        {confirmation}
                      </WorkbenchTag>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="grid min-w-0 gap-3 sm:grid-cols-3">
                <WorkbenchMetricPill
                  icon={ClipboardCheck}
                  label="阶段"
                  value={`${result.executionPlan.length}`}
                  valueSize="large"
                />
                <WorkbenchMetricPill
                  icon={Database}
                  label="预览行"
                  value={`${result.datasetPreview.rowCount}`}
                  valueSize="large"
                />
                <WorkbenchMetricPill
                  icon={ShieldCheck}
                  label="阻断项"
                  value={`${result.blockedReasons.length}`}
                  valueSize="large"
                />
              </div>

              <div className="grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {sideEffectFacts.map(([label, value]) => (
                  <WorkbenchFact key={label} label={label} value={value} />
                ))}
              </div>

              <div className="grid min-w-0 gap-2">
                {result.executionPlan.map((stage) => (
                  <div
                    className="grid min-w-0 gap-2 rounded-xl border border-[#F0E1D9] bg-white px-3 py-2 sm:grid-cols-[160px_96px_minmax(0,1fr)] sm:items-center"
                    key={stage.stage}
                  >
                    <span className="text-sm font-semibold text-[#2E201C]">
                      {stageLabels[stage.stage]}
                    </span>
                    <span
                      className={cn(
                        "inline-flex w-fit items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold",
                        stage.status === "blocked"
                          ? "bg-[#FFF4DE] text-[#FF9800]"
                          : "bg-[#EAF8EE] text-[#2EBA62]",
                      )}
                    >
                      {stage.status === "blocked" ? (
                        <AlertTriangle size={13} aria-hidden="true" />
                      ) : (
                        <CheckCircle2 size={13} aria-hidden="true" />
                      )}
                      {stage.status}
                    </span>
                    <span className="break-words text-sm text-[#7A625A]">
                      {stage.blockedReasons.length > 0
                        ? stage.blockedReasons.join(" / ")
                        : "provider_call=false / production_write=false"}
                    </span>
                  </div>
                ))}
              </div>

              <div className="grid min-w-0 gap-2 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[#2E201C]">
                    {result.datasetPreview.datasetName}
                  </p>
                  <WorkbenchTag tone={result.datasetPreview.truncated ? "amber" : "green"}>
                    {result.datasetPreview.truncated ? "truncated" : "full fixture"}
                  </WorkbenchTag>
                </div>
                {result.datasetPreview.rows.slice(0, 3).map((row) => (
                  <div className="rounded-lg bg-white px-3 py-2" key={row.rowId}>
                    <p className="text-sm font-semibold text-[#3B2924]">
                      {row.textExcerpt || row.sourceSchemaVersion}
                    </p>
                    <p className="mt-1 break-all text-xs text-[#86868B]">
                      {row.rawRecordId} / {row.evidenceRef}
                    </p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="grid min-h-64 place-items-center rounded-xl border border-dashed border-[#E8D4CB] bg-[#FFFDFC] p-6 text-center">
              <div>
                <ShieldCheck className="mx-auto text-[#C96F5C]" size={28} aria-hidden="true" />
                <p className="mt-3 text-sm font-semibold text-[#2E201C]">
                  fixture-only review bundle
                </p>
                <p className="mt-1 text-sm text-[#7A625A]">
                  provider_call=false / credential_read=false / production_write=false
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </WorkbenchPanel>
  );
}

function joinOrNone(values: string[]): string {
  return values.length > 0 ? values.join(" / ") : "none";
}

function recordString(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value : "unknown";
}
