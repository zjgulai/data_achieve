"use client";

import {
  AlertTriangle,
  ArrowLeft,
  ArrowUpRight,
  Check,
  Clipboard,
  ClipboardCheck,
  Database,
  DatabaseZap,
  FileJson2,
  KeyRound,
  LockKeyhole,
  Loader2,
  Route as RouteIcon,
  ShieldCheck,
  SlidersHorizontal,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { type ReactNode, useMemo, useState } from "react";

import type { Route } from "next";
import {
  WorkbenchFact,
  WorkbenchMetricPill,
  WorkbenchPanel,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import { buildApiMarketPreviewChainInputs } from "@/lib/api-market-preview-chain";
import {
  checkSocialProviderReadiness,
  previewSocialDataset,
  previewSocialProviderAdapterPlan,
  previewSocialProviderSourceTemplate,
  previewSocialTaskRunApprovalTemplate,
  runSocialExecutionDryRun,
} from "@/lib/api/social-provider";
import type { ApiMarketEndpoint } from "@/types/api-market";
import type {
  SocialDatasetPreview,
  SocialExecutionDryRun,
  SocialProviderAdapterPlan,
  SocialProviderReadiness,
  SocialProviderSourceTemplate,
  SocialTaskRunApprovalTemplate,
} from "@/types/social-provider";

type ApiMarketPreviewChainState = {
  adapterPlan: SocialProviderAdapterPlan;
  datasetPreview: SocialDatasetPreview;
  dryRun: SocialExecutionDryRun;
  readiness: SocialProviderReadiness;
  sourceTemplate: SocialProviderSourceTemplate;
  taskRunApprovalTemplate: SocialTaskRunApprovalTemplate;
};

export function ApiMarketDetailWorkspace({ endpoint }: { endpoint: ApiMarketEndpoint }) {
  const [copied, setCopied] = useState(false);
  const [previewChain, setPreviewChain] = useState<ApiMarketPreviewChainState | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const responsePreview = useMemo(
    () => JSON.stringify(endpoint.responsePreview.sample, null, 2),
    [endpoint.responsePreview.sample],
  );
  const requestBodyPreview = endpoint.request.requestBodyExample
    ? JSON.stringify(endpoint.request.requestBodyExample, null, 2)
    : null;

  async function copyFixture() {
    if (!navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(responsePreview);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  async function generatePreviewChain() {
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const inputs = buildApiMarketPreviewChainInputs(endpoint, { fixtureLimit: 2 });
      const [
        readiness,
        adapterPlan,
        datasetPreview,
        sourceTemplate,
        taskRunApprovalTemplate,
        dryRun,
      ] = await Promise.all([
        checkSocialProviderReadiness(inputs.readiness),
        previewSocialProviderAdapterPlan(inputs.adapterPlan),
        previewSocialDataset(inputs.datasetPreview),
        previewSocialProviderSourceTemplate(inputs.sourceTemplate),
        previewSocialTaskRunApprovalTemplate(inputs.taskRunApprovalTemplate),
        runSocialExecutionDryRun(inputs.executionDryRun),
      ]);
      setPreviewChain({
        adapterPlan,
        datasetPreview,
        dryRun,
        readiness,
        sourceTemplate,
        taskRunApprovalTemplate,
      });
    } catch (caught) {
      setPreviewError(
        caught instanceof Error ? caught.message : "api market preview chain unavailable",
      );
    } finally {
      setPreviewLoading(false);
    }
  }

  return (
    <div className="grid min-w-0 gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7A625A]"
          href="/api-market"
        >
          <ArrowLeft size={15} aria-hidden="true" />
          返回 API市场
        </Link>
        <Link
          className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white"
          href={typedRoute(
            `/automation?platform=${endpoint.platform}&endpoint=${encodeURIComponent(endpoint.endpoint)}`,
          )}
        >
          生成预案
          <ArrowUpRight size={15} aria-hidden="true" />
        </Link>
      </div>

      <WorkbenchPanel
        action={<WorkbenchTag tone="neutral">provider_call=false</WorkbenchTag>}
        icon={RouteIcon}
        label={endpoint.platformLabel}
        subtitle={endpoint.summary}
        title={endpoint.title}
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <WorkbenchFact label="provider_id" value={endpoint.providerId} />
          <WorkbenchFact label="method" value={endpoint.method} />
          <WorkbenchFact label="endpoint" value={endpoint.endpoint} />
          <WorkbenchFact label="api_version" value={endpoint.apiVersion} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <WorkbenchTag tone={endpoint.priority === "p0" ? "green" : "amber"}>
            {endpoint.priority}
          </WorkbenchTag>
          <WorkbenchTag tone={stabilityTone(endpoint.stability)}>
            {endpoint.stability}
          </WorkbenchTag>
          <WorkbenchTag tone="muted">{endpoint.category}</WorkbenchTag>
          <WorkbenchTag tone="neutral">{endpoint.executionMode}</WorkbenchTag>
          <WorkbenchTag tone="rose">{endpoint.sdkStatus}</WorkbenchTag>
        </div>
      </WorkbenchPanel>

      <WorkbenchPanel
        action={
          <button
            className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-[#D9B3AA]"
            disabled={previewLoading}
            onClick={generatePreviewChain}
            type="button"
          >
            {previewLoading ? (
              <Loader2 className="animate-spin" size={15} aria-hidden="true" />
            ) : (
              <ClipboardCheck size={15} aria-hidden="true" />
            )}
            生成本页预案
          </button>
        }
        icon={ClipboardCheck}
        label="Preview Chain"
        subtitle="复用现有 social-provider fixture endpoints，生成本页 readiness、adapter、dataset、source 和 approval 预览"
        title="API Market Preview Chain"
      >
        {previewError ? (
          <div className="mb-3 rounded-xl border border-[#FFD0C8] bg-[#FFF1EC] p-3 text-sm font-semibold text-[#B85F4F]">
            {previewError}
          </div>
        ) : null}

        {previewChain ? (
          <PreviewChainReview chain={previewChain} />
        ) : (
          <div className="grid min-h-32 place-items-center rounded-xl border border-dashed border-[#E8D4CB] bg-[#FFFDFC] p-5 text-center">
            <div>
              <ShieldCheck className="mx-auto text-[#C96F5C]" size={26} aria-hidden="true" />
              <p className="mt-3 text-sm font-semibold text-[#2E201C]">
                fixture-only review bundle
              </p>
              <p className="mt-1 text-sm text-[#7A625A]">
                provider_call=false / credential_read=false / production_write=false
              </p>
            </div>
          </div>
        )}
      </WorkbenchPanel>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="grid min-w-0 gap-5">
          <WorkbenchPanel
            icon={SlidersHorizontal}
            label="Contract"
            subtitle="只展示官方/授权 API 合同字段，后续 adapter 只能按这些字段做最小 glue code"
            title="请求合同与参数"
          >
            <div className="overflow-x-auto rounded-2xl border border-[#F0E1D9]">
              <table className="w-full min-w-[720px] border-collapse text-left text-sm">
                <thead className="bg-[#FBF8F5] text-xs uppercase text-[#B47767]">
                  <tr>
                    <th className="px-3 py-3">name</th>
                    <th className="px-3 py-3">in</th>
                    <th className="px-3 py-3">type</th>
                    <th className="px-3 py-3">required</th>
                    <th className="px-3 py-3">example</th>
                    <th className="px-3 py-3">description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F0E1D9] bg-white">
                  {endpoint.request.parameters.map((param) => (
                    <tr key={`${param.in}:${param.name}`}>
                      <td className="break-all px-3 py-3 font-semibold text-[#2E201C]">
                        {param.name}
                      </td>
                      <td className="px-3 py-3 text-[#7A625A]">{param.in}</td>
                      <td className="px-3 py-3 text-[#7A625A]">{param.type}</td>
                      <td className="px-3 py-3">
                        <WorkbenchTag tone={param.required ? "rose" : "muted"}>
                          {param.required ? "required" : "optional"}
                        </WorkbenchTag>
                      </td>
                      <td className="break-all px-3 py-3 text-[#7A625A]">
                        {param.example ?? "-"}
                      </td>
                      <td className="min-w-56 px-3 py-3 leading-6 text-[#7A625A]">
                        {param.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {requestBodyPreview ? (
              <JsonPanel label="request_body_example" value={requestBodyPreview} />
            ) : null}
          </WorkbenchPanel>

          <WorkbenchPanel
            icon={FileJson2}
            label="Fixture Replay"
            subtitle="本页只使用本地静态 fixture 样例，不读取环境变量、不创建真实 provider client"
            title="Fixture 响应预览"
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                <WorkbenchTag tone="neutral">{endpoint.responsePreview.schemaVersion}</WorkbenchTag>
                <WorkbenchTag tone="green">social schema linked</WorkbenchTag>
              </div>
              <button
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7A625A]"
                onClick={copyFixture}
                type="button"
              >
                {copied ? <Check size={15} aria-hidden="true" /> : <Clipboard size={15} aria-hidden="true" />}
                {copied ? "已复制" : "复制 fixture"}
              </button>
            </div>
            <JsonPanel label="response_preview" value={responsePreview} />
          </WorkbenchPanel>
        </section>

        <aside className="grid min-w-0 content-start gap-5">
          <WorkbenchPanel
            icon={ShieldCheck}
            label="Policy Gate"
            subtitle="live gate 未授权前只能 dry-run 或 fixture replay"
            title="私有化部署边界"
          >
            <div className="grid gap-2">
              <BoundaryRow label="provider_call" value={String(endpoint.providerCall)} tone="green" />
              <BoundaryRow
                label="provider_call_attempted"
                value={String(endpoint.providerCallAttempted)}
                tone="green"
              />
              <BoundaryRow
                label="credential_read_attempted"
                value={String(endpoint.credentialReadAttempted)}
                tone="green"
              />
              <BoundaryRow
                label="live_client_created"
                value={String(endpoint.liveClientCreated)}
                tone="green"
              />
              <BoundaryRow
                label="production_write_allowed"
                value={String(endpoint.productionWriteAllowed)}
                tone="green"
              />
            </div>
          </WorkbenchPanel>

          <WorkbenchPanel
            icon={KeyRound}
            label="Authorization"
            subtitle={endpoint.authMode}
            title="凭据与权限"
          >
            <TagList icon={KeyRound} items={endpoint.requiredCredentials} tone="muted" />
            <div className="mt-3 grid gap-2 rounded-2xl border border-[#F0E1D9] bg-[#FFFDFC] p-3 text-sm">
              <span className="text-xs font-semibold uppercase text-[#B47767]">quota</span>
              <p className="leading-6 text-[#3B2924]">{endpoint.quotaHint}</p>
            </div>
            <div className="mt-3 grid gap-2 rounded-2xl border border-[#F0E1D9] bg-[#FFFDFC] p-3 text-sm">
              <span className="text-xs font-semibold uppercase text-[#B47767]">cost</span>
              <p className="leading-6 text-[#3B2924]">{endpoint.costHint}</p>
            </div>
          </WorkbenchPanel>

          <WorkbenchPanel icon={LockKeyhole} label="Blocked" title="禁止实现项">
            <TagList icon={LockKeyhole} items={endpoint.blockedActions} tone="rose" />
            <div className="mt-4 grid gap-2">
              {endpoint.policyFlags.map((flag) => (
                <span
                  className="inline-flex min-w-0 items-center gap-2 break-all rounded-xl bg-[#FBF8F5] px-3 py-2 text-xs font-semibold text-[#7A625A]"
                  key={flag}
                >
                  <ShieldCheck size={13} className="shrink-0" aria-hidden="true" />
                  {flag}
                </span>
              ))}
            </div>
          </WorkbenchPanel>

          <WorkbenchPanel
            icon={DatabaseZap}
            label="SDK"
            subtitle="优先复用成熟官方/流行 SDK，页面仅记录选型，不安装运行时采集依赖"
            title="开源复用候选"
          >
            <div className="grid gap-2">
              <BoundaryRow label="package" value={endpoint.sdkPackage} tone="neutral" />
              <BoundaryRow label="status" value={endpoint.sdkStatus} tone="neutral" />
              <BoundaryRow label="data_domain" value={endpoint.dataDomain.join(", ")} tone="neutral" />
            </div>
            <div className="mt-4 grid gap-2">
              {endpoint.officialDocs.map((doc) => (
                <a
                  className="inline-flex min-w-0 items-center gap-2 break-all rounded-xl border border-[#E8D4CB] bg-white px-3 py-2 text-sm font-semibold text-[#7A625A]"
                  href={doc}
                  key={doc}
                  rel="noreferrer"
                  target="_blank"
                >
                  <Zap size={14} className="shrink-0" aria-hidden="true" />
                  {doc}
                </a>
              ))}
            </div>
          </WorkbenchPanel>
        </aside>
      </div>
    </div>
  );
}

function PreviewChainReview({ chain }: { chain: ApiMarketPreviewChainState }) {
  return (
    <div className="grid min-w-0 gap-4">
      <div className="flex flex-wrap gap-2">
        <WorkbenchTag tone="neutral">
          provider_call_attempted={String(chain.dryRun.providerCallAttempted)}
        </WorkbenchTag>
        <WorkbenchTag tone="neutral">
          credential_read_attempted={String(chain.dryRun.credentialReadAttempted)}
        </WorkbenchTag>
        <WorkbenchTag tone="neutral">
          live_client_created={String(chain.adapterPlan.liveClientCreated)}
        </WorkbenchTag>
        <WorkbenchTag tone="neutral">
          production_write_allowed={String(chain.dryRun.productionWriteAllowed)}
        </WorkbenchTag>
      </div>

      <div className="grid min-w-0 gap-3 sm:grid-cols-3">
        <WorkbenchMetricPill
          icon={ClipboardCheck}
          label="阶段"
          value={String(chain.dryRun.executionPlan.length)}
          valueSize="large"
        />
        <WorkbenchMetricPill
          icon={Database}
          label="预览行"
          value={String(chain.datasetPreview.rowCount)}
          valueSize="large"
        />
        <WorkbenchMetricPill
          icon={AlertTriangle}
          label="阻断项"
          value={String(chain.dryRun.blockedReasons.length)}
          valueSize="large"
        />
      </div>

      <PreviewCard tag="dry_run=true" title="Readiness Review">
        <FactGrid
          facts={[
            ["readiness", String(chain.readiness.ready)],
            ["provider_id", chain.readiness.providerId],
            ["provider_call_allowed", String(chain.readiness.providerCallAllowed)],
            ["provider_call_attempted", String(chain.readiness.providerCallAttempted)],
            ["missing_credentials", joinOrNone(chain.readiness.missingCredentials)],
            ["missing_scope", joinOrNone(chain.readiness.missingScope)],
          ]}
        />
      </PreviewCard>

      <PreviewCard tag="live_client_created=false" title="Adapter Plan Gate">
        <FactGrid
          facts={[
            ["provider_id", chain.adapterPlan.providerId],
            ["sdk_package", chain.adapterPlan.sdkSelection?.package ?? "none"],
            ["dependency_present", String(chain.adapterPlan.dependencyPresent)],
            ["adapter_ready", String(chain.adapterPlan.adapterReady)],
            ["fixture_replay_supported", String(chain.adapterPlan.fixtureReplaySupported)],
            ["provider_call_attempted", String(chain.adapterPlan.providerCallAttempted)],
          ]}
        />
        {chain.adapterPlan.adapterModule ? (
          <p className="mt-2 break-all text-xs font-semibold text-[#7A625A]">
            {chain.adapterPlan.adapterModule}
          </p>
        ) : null}
        <div className="mt-2 grid min-w-0 gap-2">
          {chain.adapterPlan.plannedOperations.slice(0, 3).map((operation, index) => (
            <div
              className="grid min-w-0 gap-2 rounded-lg bg-white px-3 py-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_130px]"
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
      </PreviewCard>

      <PreviewCard tag="dataset_write_allowed=false" title="Dataset Preview Gate">
        <FactGrid
          facts={[
            ["dataset_name", chain.datasetPreview.datasetName],
            ["row_count", String(chain.datasetPreview.rowCount)],
            ["source_item_count", String(chain.datasetPreview.sourceItemCount)],
            ["dataset_write_allowed", String(chain.datasetPreview.datasetWriteAllowed)],
            ["dataset_created", String(chain.datasetPreview.datasetCreated)],
            ["export_created", String(chain.datasetPreview.exportCreated)],
          ]}
        />
        <div className="mt-2 grid min-w-0 gap-2">
          {chain.datasetPreview.rows.slice(0, 2).map((row) => (
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
      </PreviewCard>

      <PreviewCard tag="source_created=false" title="Source Template Gate">
        <FactGrid
          facts={[
            ["source_type", chain.sourceTemplate.sourceType],
            ["template_strategy", chain.sourceTemplate.templateStrategy],
            ["source_create_allowed", String(chain.sourceTemplate.sourceCreateAllowed)],
            ["source_created", String(chain.sourceTemplate.sourceCreated)],
            ["task_created", String(chain.sourceTemplate.taskCreated)],
            ["payload_present", String(chain.sourceTemplate.payloadPresent)],
          ]}
        />
      </PreviewCard>

      <PreviewCard tag="review_only" title="L4 Approval Packet Gate">
        <FactGrid
          facts={[
            ["task_run_allowed", String(chain.taskRunApprovalTemplate.taskRunAllowed)],
            ["dataset_write_allowed", String(chain.taskRunApprovalTemplate.datasetWriteAllowed)],
            ["export_allowed", String(chain.taskRunApprovalTemplate.exportAllowed)],
            ["production_write_allowed", String(chain.taskRunApprovalTemplate.productionWriteAllowed)],
            [
              "packet_schema",
              recordString(chain.taskRunApprovalTemplate.approvalPacket, "schema_version"),
            ],
            ["next_authorization", chain.taskRunApprovalTemplate.nextRequiredAuthorization],
          ]}
        />
        <div className="mt-2 flex flex-wrap gap-2">
          {chain.taskRunApprovalTemplate.requiredConfirmations.slice(0, 4).map((confirmation) => (
            <WorkbenchTag key={confirmation} tone="rose">
              {confirmation}
            </WorkbenchTag>
          ))}
        </div>
      </PreviewCard>

      <PreviewCard tag="execution_dry_run" title="Execution Dry Run">
        <FactGrid
          facts={[
            ["raw_record_count", String(chain.dryRun.rawRecordCount)],
            ["normalized_item_count", String(chain.dryRun.normalizedItemCount)],
            ["task_run_allowed", String(chain.dryRun.taskRunAllowed)],
            ["dataset_write_allowed", String(chain.dryRun.datasetWriteAllowed)],
            ["export_allowed", String(chain.dryRun.exportAllowed)],
            ["next_authorization", chain.dryRun.nextRequiredAuthorization],
          ]}
        />
        <div className="mt-2 grid min-w-0 gap-2">
          {chain.dryRun.executionPlan.map((stage) => (
            <div
              className="grid min-w-0 gap-2 rounded-lg bg-white px-3 py-2 sm:grid-cols-[150px_90px_minmax(0,1fr)] sm:items-center"
              key={stage.stage}
            >
              <p className="break-words text-sm font-semibold text-[#3B2924]">{stage.stage}</p>
              <WorkbenchTag tone={stage.status === "blocked" ? "amber" : "green"}>
                {stage.status}
              </WorkbenchTag>
              <p className="break-words text-xs text-[#7A625A]">
                {stage.blockedReasons.length
                  ? stage.blockedReasons.join(" / ")
                  : "provider_call=false / production_write=false"}
              </p>
            </div>
          ))}
        </div>
      </PreviewCard>
    </div>
  );
}

function PreviewCard({
  children,
  tag,
  title,
}: {
  children: ReactNode;
  tag: string;
  title: string;
}) {
  return (
    <section className="grid min-w-0 gap-2 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="break-words text-sm font-semibold text-[#2E201C]">{title}</h3>
        <WorkbenchTag tone="neutral">{tag}</WorkbenchTag>
      </div>
      {children}
    </section>
  );
}

function FactGrid({ facts }: { facts: Array<[string, string]> }) {
  return (
    <div className="grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-3">
      {facts.map(([label, value]) => (
        <WorkbenchFact key={label} label={label} value={value} />
      ))}
    </div>
  );
}

function BoundaryRow({
  label,
  tone,
  value,
}: {
  label: string;
  tone: "green" | "neutral";
  value: string;
}) {
  const valueClass = tone === "green" ? "text-[#2EBA62]" : "text-[#3B2924]";
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2">
      <span className="break-all text-sm font-semibold text-[#7A625A]">{label}</span>
      <span className={`shrink-0 text-sm font-semibold ${valueClass}`}>{value}</span>
    </div>
  );
}

function JsonPanel({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-w-0 gap-2">
      <p className="text-xs font-semibold uppercase text-[#B47767]">{label}</p>
      <pre className="max-h-[420px] overflow-auto rounded-2xl border border-[#F0E1D9] bg-[#2E201C] p-4 text-xs leading-5 text-[#FFF8F5]">
        <code>{value}</code>
      </pre>
    </div>
  );
}

function TagList({
  icon: Icon,
  items,
  tone,
}: {
  icon: typeof KeyRound;
  items: string[];
  tone: "muted" | "rose";
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          className="inline-flex min-w-0 items-center gap-2 break-all rounded-xl bg-[#FBF8F5] px-3 py-2 text-xs font-semibold text-[#7A625A]"
          key={item}
        >
          <Icon size={13} className="shrink-0" aria-hidden="true" />
          <WorkbenchTag tone={tone}>{item}</WorkbenchTag>
        </span>
      ))}
    </div>
  );
}

function joinOrNone(values: string[]): string {
  return values.length > 0 ? values.join(" / ") : "none";
}

function recordString(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value : "unknown";
}

function stabilityTone(stability: ApiMarketEndpoint["stability"]): "amber" | "green" | "rose" {
  if (stability === "high") {
    return "green";
  }
  if (stability === "medium") {
    return "amber";
  }
  return "rose";
}

function typedRoute(href: string): Route {
  return href as Route;
}
