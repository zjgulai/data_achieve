"use client";

import { Activity, ArrowUpRight, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listSignals } from "@/lib/api/signals";
import type { Signal } from "@/types/signal";

const severityClass: Record<string, string> = {
  low: "bg-[#f1f5f9] text-[#475569]",
  medium: "bg-[#fef3c7] text-[#92400e]",
  high: "bg-[#fee2e2] text-[#b91c1c]",
  critical: "bg-[#7f1d1d] text-white",
};

export function SignalsWorkspace() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    listSignals()
      .then((items) => {
        if (!mounted) {
          return;
        }
        setSignals(items);
        setSelectedId(items[0]?.id ?? null);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load signals");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const selectedSignal = useMemo(() => {
    return signals.find((item) => item.id === selectedId) ?? null;
  }, [signals, selectedId]);

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_420px]">
      <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">Signal 列表</h2>
            <p className="mt-1 text-sm text-[#6b7280]">确定性规则生成的变化信号</p>
          </div>
          <Activity size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {loading ? <p className="text-sm text-[#6b7280]">加载信号中</p> : null}
        {error ? (
          <p className="mb-4 rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3">
          {signals.map((signal) => (
            <button
              className={`rounded-md border p-4 text-left transition ${
                signal.id === selectedId
                  ? "border-[#0f766e] bg-[#ecfdf5]"
                  : "border-[#dfe3ea] bg-white hover:border-[#94a3b8]"
              }`}
              key={signal.id}
              onClick={() => setSelectedId(signal.id)}
              type="button"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <h3 className="text-sm font-semibold">{signal.signalType}</h3>
                  <p className="mt-2 text-xs text-[#6b7280]">
                    {new Date(signal.detectedAt).toLocaleString()}
                  </p>
                </div>
                <span
                  className={`rounded-md px-2.5 py-1 text-xs font-semibold ${
                    severityClass[signal.severity] ?? severityClass.low
                  }`}
                >
                  {signal.severity}
                </span>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                <Metric label="current" value={signal.currentValue} />
                <Metric label="delta" value={signal.delta} />
                <Metric label="confidence" value={signal.confidence} />
              </div>
            </button>
          ))}
          {!loading && signals.length === 0 ? (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
              暂无信号
            </div>
          ) : null}
        </div>
      </section>

      <aside className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">信号详情</h2>
            <p className="mt-1 text-sm text-[#6b7280]">快照绑定与规则元数据</p>
          </div>
          <ShieldAlert size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {selectedSignal ? (
          <div className="grid gap-4">
            <DetailRow label="Signal ID" value={selectedSignal.id} />
            <DetailRow label="Entity ID" value={selectedSignal.entityId} />
            <DetailRow label="Previous Snapshot" value={selectedSignal.previousSnapshotId} />
            <DetailRow label="Current Snapshot" value={selectedSignal.currentSnapshotId} />
            <div className="grid grid-cols-2 gap-2">
              <Metric label="previous" value={selectedSignal.previousValue} />
              <Metric label="ratio" value={selectedSignal.deltaRatio} />
            </div>
            <pre className="max-h-72 overflow-auto rounded-md bg-[#111827] p-4 text-xs leading-5 text-[#e5e7eb]">
              {JSON.stringify(selectedSignal.metadata, null, 2)}
            </pre>
          </div>
        ) : (
          <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
            选择一条信号查看详情
          </div>
        )}
      </aside>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-md bg-[#f7f8fa] px-3 py-2">
      <span className="text-[#6b7280]">{label}</span>
      <p className="mt-1 flex items-center gap-1 font-semibold">
        {value === null ? "n/a" : value.toFixed(2)}
        {label === "delta" && value !== null && value > 0 ? (
          <ArrowUpRight size={13} aria-hidden="true" />
        ) : null}
      </p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-[#f7f8fa] px-3 py-2 text-sm">
      <span className="text-[#6b7280]">{label}</span>
      <p className="mt-1 break-all font-medium">{value}</p>
    </div>
  );
}
