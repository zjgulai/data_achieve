"use client";

import { Grid3X3, ShieldCheck } from "lucide-react";

import {
  WorkbenchFact,
  WorkbenchPanel,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import {
  capabilityAccessChannels,
  capabilityPlatforms,
  capabilityPlatformLabel,
  capabilityStatusLabel,
} from "@/lib/capability-market";
import type {
  CapabilityAccessChannel,
  CapabilityMatrix,
  CapabilityMatrixCell,
  CapabilityPlatform,
} from "@/types/capability";

type CapabilityMatrixViewProps = {
  cells: CapabilityMatrixCell[];
  evidenceLevel: string;
  generatedAt: string;
  mobilePlatform: CapabilityPlatform;
  onMobilePlatformChange: (platform: CapabilityPlatform) => void;
  onSelectCell: (cell: CapabilityMatrixCell, trigger: HTMLElement) => void;
  summary: CapabilityMatrix["summary"];
};

const accessChannelLabels: Record<CapabilityAccessChannel, string> = {
  authorized_browser: "授权浏览器",
  authorized_export_import: "授权导入",
  licensed_partner_data_service: "持牌数据服务",
  managed_opaque_collector: "托管采集器",
  official_authorized_api: "官方授权 API",
  public_web_feed: "公开 Web / Feed",
};

export function CapabilityMatrixView({
  cells,
  evidenceLevel,
  generatedAt,
  mobilePlatform,
  onMobilePlatformChange,
  onSelectCell,
  summary,
}: CapabilityMatrixViewProps) {
  const visiblePlatforms = capabilityPlatforms.filter((platform) =>
    cells.some((cell) => cell.platform === platform),
  );
  const visibleAccessChannels = capabilityAccessChannels.filter(
    (accessChannel) =>
      cells.some((cell) => cell.accessChannel === accessChannel),
  );
  const cellByKey = new Map(
    cells.map((cell) => [cellKey(cell.platform, cell.accessChannel), cell]),
  );
  const mobileCells = capabilityAccessChannels.flatMap((accessChannel) => {
    const cell = cellByKey.get(cellKey(mobilePlatform, accessChannel));
    return cell ? [cell] : [];
  });

  return (
    <div className="grid min-w-0 gap-4">
      <WorkbenchPanel
        action={<WorkbenchTag tone="neutral">{evidenceLevel}</WorkbenchTag>}
        icon={Grid3X3}
        label="Coverage matrix"
        subtitle="固定单元尺寸用于横向比较；unknown 表示尚无事实，不等于 unsupported。"
        title="7×6 能力矩阵"
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          <WorkbenchFact label="generated" value={generatedAt} />
          <WorkbenchFact label="evidence" value={String(summary.evidenceCount)} />
          <WorkbenchFact label="cells" value={String(summary.cellCount)} />
          <WorkbenchFact label="populated" value={String(summary.populatedCellCount)} />
          <WorkbenchFact label="unknown" value={String(summary.unknownCellCount)} />
          <WorkbenchFact label="visible" value={String(cells.length)} />
          <WorkbenchFact label="provider_call" value="false" />
          <WorkbenchFact
            label="production_write_allowed"
            value="false"
          />
        </div>
      </WorkbenchPanel>

      {cells.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-[#D9C4BA] bg-[#FFFDFC] p-8 text-center">
          <p className="text-sm font-semibold text-[#7A625A]">
            当前筛选条件下没有矩阵单元格；未将空结果解释为不支持。
          </p>
        </section>
      ) : (
        <>
          <section className="hidden min-w-0 overflow-hidden rounded-2xl border border-[#E8D4CB] bg-white md:block">
            <div className="max-w-full overflow-x-auto">
              <table className="w-[74rem] table-fixed border-collapse text-left">
                <thead className="bg-[#FBF8F5]">
                  <tr>
                    <th className="w-32 border-b border-r border-[#E8D4CB] px-3 py-3 text-xs font-semibold uppercase text-[#B47767]">
                      Platform
                    </th>
                    {visibleAccessChannels.map((accessChannel) => (
                      <th
                        className="w-44 border-b border-r border-[#E8D4CB] px-3 py-3 text-xs font-semibold text-[#7A625A] last:border-r-0"
                        key={accessChannel}
                        scope="col"
                      >
                        {accessChannelLabels[accessChannel]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visiblePlatforms.map((platform) => {
                    return (
                      <tr key={platform}>
                        <th
                          className="w-32 border-b border-r border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm font-semibold text-[#2E201C]"
                          scope="row"
                        >
                          {capabilityPlatformLabel(platform)}
                        </th>
                        {visibleAccessChannels.map((accessChannel) => {
                          const cell = cellByKey.get(
                            cellKey(platform, accessChannel),
                          );
                          return (
                            <td
                              className="h-28 w-44 border-b border-r border-[#E8D4CB] p-0 last:border-r-0"
                              key={accessChannel}
                            >
                              {cell ? (
                                <CellButton
                                  cell={cell}
                                  evidenceLevel={evidenceLevel}
                                  onSelect={onSelectCell}
                                />
                              ) : (
                                <span className="flex h-28 items-center justify-center bg-[#FBF8F5] text-xs text-[#B7A49C]">
                                  已被筛选
                                </span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="grid gap-3 md:hidden">
            <label className="grid gap-2 text-xs font-semibold uppercase text-[#B47767]">
              移动端平台
              <select
                className="h-11 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm normal-case text-[#2E201C] outline-none focus-visible:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
                data-testid="capability-platform-select"
                onChange={(event) =>
                  onMobilePlatformChange(
                    event.target.value as CapabilityPlatform,
                  )
                }
                value={mobilePlatform}
              >
                {capabilityPlatforms.map((platform) => (
                  <option key={platform} value={platform}>
                    {capabilityPlatformLabel(platform)}
                  </option>
                ))}
              </select>
            </label>

            {mobileCells.length > 0 ? (
              <div className="grid gap-2">
                {mobileCells.map((cell) => (
                  <div
                    className="overflow-hidden rounded-xl border border-[#E8D4CB] bg-white"
                    key={cell.accessChannel}
                  >
                    <p className="border-b border-[#F0E1D9] bg-[#FBF8F5] px-3 py-2 text-xs font-semibold text-[#7A625A]">
                      {accessChannelLabels[cell.accessChannel]}
                    </p>
                    <CellButton
                      cell={cell}
                      evidenceLevel={evidenceLevel}
                      onSelect={onSelectCell}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="rounded-xl border border-dashed border-[#D9C4BA] bg-[#FFFDFC] p-5 text-center text-sm font-semibold text-[#7A625A]">
                当前平台没有符合筛选条件的单元格。
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function CellButton({
  cell,
  evidenceLevel,
  onSelect,
}: {
  cell: CapabilityMatrixCell;
  evidenceLevel: string;
  onSelect: (cell: CapabilityMatrixCell, trigger: HTMLElement) => void;
}) {
  const populated = cell.implementationIds.length > 0;
  return (
    <button
      aria-label={`${capabilityPlatformLabel(cell.platform)} ${accessChannelLabels[cell.accessChannel]} ${capabilityStatusLabel(cell.summaryStatus)}`}
      className={`grid h-28 w-full content-between gap-1 p-3 text-left outline-none transition focus-visible:relative focus-visible:z-10 focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-[#F3D7CE] ${
        populated
          ? "bg-[#FFFDFC] hover:bg-[#FFF1EC]"
          : "bg-[#FBF8F5] hover:bg-[#F7F0EB]"
      }`}
      data-access-channel={cell.accessChannel}
      data-platform={cell.platform}
      data-testid="capability-matrix-cell"
      onClick={(event) => onSelect(cell, event.currentTarget)}
      type="button"
    >
      <span className="flex items-start justify-between gap-2">
        <WorkbenchTag tone={cell.summaryStatus === "candidate" ? "amber" : cell.summaryStatus === "verified" ? "green" : "muted"}>
          {capabilityStatusLabel(cell.summaryStatus)}
        </WorkbenchTag>
        <ShieldCheck className="shrink-0 text-[#B47767]" size={14} aria-hidden="true" />
      </span>
      <span className="text-xs font-semibold text-[#3B2924]">
        {cell.assertionIds.length} assertions · {cell.evidenceCount} evidence
      </span>
      <span className="flex items-end justify-between gap-2 text-[11px] text-[#7A625A]">
        <span>{evidenceLevel}</span>
        {cell.summaryStatus === "candidate" ? (
          <span className="font-semibold text-[#B85F4F]">不可执行</span>
        ) : null}
      </span>
    </button>
  );
}

function cellKey(
  platform: CapabilityPlatform,
  accessChannel: CapabilityAccessChannel,
): string {
  return `${platform}:${accessChannel}`;
}
