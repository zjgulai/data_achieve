"use client";

import { ExternalLink, GitCompareArrows, X } from "lucide-react";
import { useEffect, useRef } from "react";

import { WorkbenchTag } from "@/components/common/workbench-ui";
import {
  capabilityPlatformLabel,
  capabilityScoreKeys,
  type CapabilityImplementationComparison,
} from "@/lib/capability-market";

type CapabilityComparisonPanelProps = {
  comparison: CapabilityImplementationComparison;
  onClose: () => void;
};

export function CapabilityComparisonPanel({
  comparison,
  onClose,
}: CapabilityComparisonPanelProps) {
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      } else if (event.key === "Tab") {
        keepFocusInsideDialog(event, dialogRef.current);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [comparison, onClose]);

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-[#2E201C]/40 p-3 backdrop-blur-[2px] sm:p-6">
      <button
        aria-label="关闭 Implementation 比较遮罩"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
        tabIndex={-1}
        type="button"
      />
      <section
        aria-label="Implementation 比较"
        aria-modal="true"
        className="relative z-10 grid max-h-[92vh] w-full max-w-6xl grid-rows-[auto_1fr] overflow-hidden rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] shadow-[0_30px_90px_rgba(46,32,28,0.28)]"
        ref={dialogRef}
        role="dialog"
      >
        <header className="flex items-start justify-between gap-4 border-b border-[#E8D4CB] bg-white px-4 py-4 sm:px-6">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#B47767]">
              <GitCompareArrows size={14} aria-hidden="true" />
              Same-platform review
            </p>
            <h2 className="mt-1 text-xl font-semibold text-[#2E201C]">
              Implementation 比较
            </h2>
            <p className="mt-1 text-sm text-[#7A625A]">
              {capabilityPlatformLabel(comparison.platform)} · 仅显示 Task6
              comparison model
            </p>
          </div>
          <button
            aria-label="关闭 Implementation 比较"
            autoFocus
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#E8D4CB] bg-white text-[#7A625A] outline-none transition hover:border-[#C96F5C] hover:text-[#B85F4F] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
            onClick={onClose}
            type="button"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        <div className="min-w-0 overflow-auto p-4 sm:p-6">
          <section className="mb-5 grid gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FBF8F5] p-4 sm:grid-cols-2">
            <ScopeTags label="共享资源" values={comparison.sharedResources} />
            <ScopeTags label="共享操作" values={comparison.sharedOperations} />
          </section>

          <div className="overflow-x-auto rounded-2xl border border-[#E8D4CB]">
            <table className="min-w-[48rem] w-full table-fixed border-collapse text-left">
              <thead className="bg-[#FBF8F5]">
                <tr>
                  <th className="w-48 border-b border-r border-[#E8D4CB] px-4 py-3 text-xs font-semibold uppercase text-[#B47767]">
                    Capability
                  </th>
                  {comparison.columns.map((column) => (
                    <th
                      className="border-b border-r border-[#E8D4CB] px-4 py-3 last:border-r-0"
                      key={column.implementationId}
                      scope="col"
                    >
                      <span className="block break-all text-sm font-semibold text-[#2E201C]">
                        {column.implementationId}
                      </span>
                      <span className="mt-1 block break-all text-xs text-[#7A625A]">
                        {column.providerId}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {capabilityScoreKeys.map((scoreKey) => (
                  <tr key={scoreKey}>
                    <th
                      className="border-b border-r border-[#E8D4CB] bg-[#FFFDFC] px-4 py-3 text-sm font-semibold text-[#7A625A]"
                      scope="row"
                    >
                      {scoreKey}
                    </th>
                    {comparison.columns.map((column) => (
                      <td
                        className="border-b border-r border-[#E8D4CB] bg-white px-4 py-3 text-sm font-semibold text-[#2E201C] last:border-r-0"
                        key={column.implementationId}
                      >
                        {column.scores[scoreKey] ?? "not provided"}
                      </td>
                    ))}
                  </tr>
                ))}
                <tr>
                  <th
                    className="border-b border-r border-[#E8D4CB] bg-[#FFFDFC] px-4 py-3 text-sm font-semibold text-[#7A625A]"
                    scope="row"
                  >
                    限制
                  </th>
                  {comparison.columns.map((column) => (
                    <td
                      className="border-b border-r border-[#E8D4CB] bg-white px-4 py-3 text-sm text-[#3B2924] last:border-r-0"
                      key={column.implementationId}
                    >
                      {column.constraintCodes.length > 0
                        ? column.constraintCodes.join(", ")
                        : "none"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th
                    className="border-r border-[#E8D4CB] bg-[#FFFDFC] px-4 py-3 text-sm font-semibold text-[#7A625A]"
                    scope="row"
                  >
                    Evidence
                  </th>
                  {comparison.columns.map((column) => (
                    <td
                      className="border-r border-[#E8D4CB] bg-white px-4 py-3 last:border-r-0"
                      key={column.implementationId}
                    >
                      <div className="grid gap-2">
                        {column.evidence.length > 0 ? (
                          column.evidence.map((evidence) => (
                            <a
                              className="inline-flex min-w-0 items-center gap-2 break-all text-xs font-semibold text-[#7D4F43] underline decoration-[#D9A99C] underline-offset-4 outline-none focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
                              href={evidence.source_url}
                              key={evidence.evidence_id}
                              rel="noreferrer"
                              target="_blank"
                            >
                              {evidence.evidence_id}
                              <ExternalLink className="shrink-0" size={12} aria-hidden="true" />
                            </a>
                          ))
                        ) : (
                          <span className="text-xs font-semibold text-[#7A625A]">
                            none
                          </span>
                        )}
                      </div>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}

function ScopeTags({
  label,
  values,
}: {
  label: string;
  values: readonly string[];
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-[#B47767]">{label}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {values.length > 0 ? (
          values.map((value) => (
            <WorkbenchTag key={value} tone="muted">
              {value}
            </WorkbenchTag>
          ))
        ) : (
          <WorkbenchTag tone="neutral">none</WorkbenchTag>
        )}
      </div>
    </div>
  );
}

function keepFocusInsideDialog(
  event: KeyboardEvent,
  dialog: HTMLElement | null,
) {
  if (!dialog) {
    return;
  }
  const focusableElements = Array.from(
    dialog.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), select:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => !element.hasAttribute("hidden"));
  const first = focusableElements[0];
  const last = focusableElements.at(-1);
  if (!first || !last) {
    event.preventDefault();
    dialog.focus();
    return;
  }
  const activeElement = document.activeElement;
  if (!dialog.contains(activeElement)) {
    event.preventDefault();
    first.focus();
  } else if (event.shiftKey && activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
