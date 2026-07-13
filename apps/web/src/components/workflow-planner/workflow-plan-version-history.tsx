"use client";

import type { Route } from "next";
import Link from "next/link";

import type { ProjectStatus } from "@/types/project";
import type {
  WorkflowPlan,
  WorkflowVersionSummary,
} from "@/types/workflow-plan-persistence";

function plannerSourceHref(plan: WorkflowPlan, sourceVersionId: string): Route {
  const query = new URLSearchParams();
  query.set("mode", plan.flowMode);
  query.set("project_id", plan.projectId);
  query.set("plan_id", plan.id);
  query.set("source_version_id", sourceVersionId);
  return `/automation/planner?${query.toString()}` as Route;
}

export function WorkflowPlanVersionHistory({
  plan,
  projectStatus,
  versions,
  total,
  hasMore,
  loadingMore,
  loadMoreError,
  onLoadMore,
}: {
  plan: WorkflowPlan;
  projectStatus: ProjectStatus;
  versions: WorkflowVersionSummary[];
  total: number;
  hasMore: boolean;
  loadingMore: boolean;
  loadMoreError: string | null;
  onLoadMore: () => void;
}) {
  const archived = projectStatus === "archived";

  return (
    <section
      aria-labelledby="workflow-plan-version-history-heading"
      className="min-w-0 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 sm:p-5"
      data-testid="workflow-plan-version-history"
    >
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9A7467]">
            Immutable Versions
          </p>
          <h2
            className="mt-1 text-lg font-semibold text-[#2E201C]"
            id="workflow-plan-version-history-heading"
          >
            Version History
          </h2>
        </div>
        <p className="text-sm text-[#716562]">
          已加载 {versions.length} / {total}
        </p>
      </div>

      <ol className="mt-4 grid min-w-0 gap-3">
        {versions.map((version) => {
          const current = version.id === plan.currentVersionId;
          return (
            <li
              className="min-w-0 rounded-xl border border-[#E9E1DC] bg-white p-4"
              key={version.id}
            >
              <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold text-[#392823]">
                      v{version.versionNumber}
                    </h3>
                    {current ? (
                      <span className="rounded-full bg-[#EAF8EE] px-2 py-1 text-xs font-semibold text-[#277F49]">
                        当前
                      </span>
                    ) : null}
                    <span className="rounded-full bg-[#FBF1EC] px-2 py-1 text-xs font-semibold text-[#8A4436]">
                      {version.planningStatus}
                    </span>
                  </div>
                  <dl className="mt-3 grid min-w-0 gap-2 text-xs text-[#716562] sm:grid-cols-2 lg:grid-cols-4">
                    <VersionFact label="创建时间" value={version.createdAt} />
                    <VersionFact
                      label="创建者 ID"
                      value={version.createdByUserId}
                    />
                    <VersionFact
                      label="Planner Contract"
                      value={version.plannerContractVersion}
                    />
                    <VersionFact
                      label="Catalog Snapshot"
                      value={version.catalogSnapshotId}
                    />
                  </dl>
                </div>

                <Link
                  className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-xl border border-[#C97865] bg-white px-4 py-2 text-sm font-semibold text-[#8A4436]"
                  href={plannerSourceHref(plan, version.id)}
                >
                  {archived
                    ? "在 Planner 中查看（只读）"
                    : `从 v${version.versionNumber} 在 Planner 中继续`}
                </Link>
              </div>
            </li>
          );
        })}
      </ol>

      {loadMoreError ? (
        <p
          className="mt-4 rounded-xl border border-[#E4B9A7] bg-[#FFF5EF] px-4 py-3 text-sm font-semibold text-[#803F32]"
          role="alert"
        >
          {loadMoreError}
        </p>
      ) : null}

      {hasMore ? (
        <button
          aria-label="加载更多 Version"
          className="mt-4 rounded-xl border border-[#DCCFC8] bg-white px-4 py-2 text-sm font-semibold text-[#6D514A] disabled:cursor-not-allowed disabled:opacity-50"
          disabled={loadingMore}
          onClick={onLoadMore}
          type="button"
        >
          {loadingMore ? "正在加载更多…" : "加载更多 Version"}
        </button>
      ) : null}
    </section>
  );
}

function VersionFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg bg-[#FBF8F5] px-3 py-2">
      <dt className="font-semibold text-[#9A7467]">{label}</dt>
      <dd className="mt-1 break-all text-[#4D3B36]">{value}</dd>
    </div>
  );
}
