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

import { runSocialExecutionDryRun } from "@/lib/api/social-provider";
import { cn } from "@/lib/utils";
import {
  WorkbenchFact,
  WorkbenchMetricPill,
  WorkbenchPanel,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import type {
  SocialExecutionDryRun,
  SocialProviderPlatform,
} from "@/types/social-provider";

const endpointOptions: Record<SocialProviderPlatform, Array<{ label: string; value: string }>> = {
  reddit: [
    { label: "comments.new", value: "comments.new" },
    { label: "search", value: "search" },
    { label: "hot.list", value: "hot.list" },
    { label: "new.list", value: "new.list" },
  ],
  youtube: [
    { label: "videos.list", value: "videos.list" },
    { label: "search.list", value: "search.list" },
    { label: "channels.list", value: "channels.list" },
    { label: "commentThreads.list", value: "commentThreads.list" },
  ],
};

const platformLabels: Record<SocialProviderPlatform, string> = {
  reddit: "Reddit",
  youtube: "YouTube",
};

const stageLabels: Record<SocialExecutionDryRun["executionPlan"][number]["stage"], string> = {
  dataset_preview: "Dataset Preview",
  normalization_preview: "Normalization",
  raw_preview: "Raw Preview",
  readiness: "Readiness",
  source_template: "Source Template",
  task_run_approval_template: "TaskRun Packet",
};

export function SocialProviderDryRunPanel() {
  const [platform, setPlatform] = useState<SocialProviderPlatform>("reddit");
  const [endpoint, setEndpoint] = useState("comments.new");
  const [fixtureLimit, setFixtureLimit] = useState("2");
  const [credentialReference, setCredentialReference] = useState(
    "vault:overseas-social-readonly",
  );
  const [result, setResult] = useState<SocialExecutionDryRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentEndpointOptions = endpointOptions[platform];
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

  async function submitDryRun() {
    setLoading(true);
    setError(null);
    try {
      const parsedFixtureLimit = Number.parseInt(fixtureLimit, 10);
      const dryRun = await runSocialExecutionDryRun({
        platform,
        endpoint,
        fixtureLimit: Number.isFinite(parsedFixtureLimit) ? parsedFixtureLimit : 2,
        intendedUse: `fixture-only ${platform} ${endpoint} social review`,
        datasetName: `${platformLabels[platform]} ${endpoint} VOC fixture`,
        sourceName: `${platformLabels[platform]} ${endpoint} fixture source`,
        taskName: `${platformLabels[platform]} ${endpoint} fixture task`,
        credentialReference: credentialReference.trim() || undefined,
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

  return (
    <WorkbenchPanel
      action={<WorkbenchTag tone="green">provider_call=false</WorkbenchTag>}
      icon={Globe2}
      label="Social API"
      subtitle="YouTube / Reddit fixture-only execution review"
      title="海外社媒采集预案"
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        <form
          className="grid gap-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3"
          onSubmit={(event) => {
            event.preventDefault();
            void submitDryRun();
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
              <span>平台</span>
              <select
                className="h-11 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                onChange={(event) => {
                  const nextPlatform = event.target.value as SocialProviderPlatform;
                  setPlatform(nextPlatform);
                  setEndpoint(endpointOptions[nextPlatform][0]?.value ?? "");
                }}
                value={platform}
              >
                <option value="reddit">Reddit</option>
                <option value="youtube">YouTube</option>
              </select>
            </label>

            <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
              <span>Endpoint</span>
              <select
                className="h-11 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                onChange={(event) => setEndpoint(event.target.value)}
                value={endpoint}
              >
                {currentEndpointOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
            <span>Fixture limit</span>
            <input
              className="h-11 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
              max={10}
              min={1}
              onChange={(event) => setFixtureLimit(event.target.value)}
              type="number"
              value={fixtureLimit}
            />
          </label>

          <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
            <span>Credential reference</span>
            <input
              className="h-11 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
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

        <div className="grid gap-4">
          {error ? (
            <div className="rounded-xl border border-[#FFD0C8] bg-[#FFF1EC] p-3 text-sm font-semibold text-[#B85F4F]">
              {error}
            </div>
          ) : null}

          {result ? (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
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

              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                {sideEffectFacts.map(([label, value]) => (
                  <WorkbenchFact key={label} label={label} value={value} />
                ))}
              </div>

              <div className="grid gap-2">
                {result.executionPlan.map((stage) => (
                  <div
                    className="grid gap-2 rounded-xl border border-[#F0E1D9] bg-white px-3 py-2 sm:grid-cols-[160px_96px_minmax(0,1fr)] sm:items-center"
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

              <div className="grid gap-2 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
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
