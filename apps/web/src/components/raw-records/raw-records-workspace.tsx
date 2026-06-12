"use client";

import { Database, FileJson2, Hash, Link2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listRawRecords } from "@/lib/api/raw-records";
import type { RawRecord } from "@/types/raw-record";

export function RawRecordsWorkspace() {
  const [rawRecords, setRawRecords] = useState<RawRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    listRawRecords()
      .then((items) => {
        if (!mounted) {
          return;
        }
        setRawRecords(items);
        setSelectedId(items[0]?.id ?? null);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load raw records");
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

  const selectedRecord = useMemo(() => {
    return rawRecords.find((item) => item.id === selectedId) ?? null;
  }, [rawRecords, selectedId]);

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_440px]">
      <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">RawRecord 列表</h2>
            <p className="mt-1 text-sm text-[#6b7280]">采集任务写入的原始事实层记录</p>
          </div>
          <Database size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {loading ? <p className="text-sm text-[#6b7280]">加载原始记录中</p> : null}
        {error ? (
          <p className="mb-4 rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3">
          {rawRecords.map((rawRecord) => (
            <button
              className={`rounded-md border p-4 text-left transition ${
                rawRecord.id === selectedId
                  ? "border-[#0f766e] bg-[#ecfdf5]"
                  : "border-[#dfe3ea] bg-white hover:border-[#94a3b8]"
              }`}
              key={rawRecord.id}
              onClick={() => setSelectedId(rawRecord.id)}
              type="button"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <h3 className="text-sm font-semibold">{rawRecord.recordType}</h3>
                  <p className="mt-2 break-all text-xs text-[#6b7280]">
                    {rawRecord.sourceUrl ?? "manual-json"}
                  </p>
                </div>
                <span className="rounded-md bg-[#f1f5f9] px-2.5 py-1 text-xs font-semibold">
                  {new Date(rawRecord.collectedAt).toLocaleString()}
                </span>
              </div>
              <div className="mt-4 flex items-center gap-2 text-xs text-[#6b7280]">
                <Hash size={14} aria-hidden="true" />
                <span className="break-all">{rawRecord.contentHash.slice(0, 20)}</span>
              </div>
            </button>
          ))}
          {!loading && rawRecords.length === 0 ? (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
              暂无原始记录
            </div>
          ) : null}
        </div>
      </section>

      <aside className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">记录详情</h2>
            <p className="mt-1 text-sm text-[#6b7280]">RawRecord content JSON</p>
          </div>
          <FileJson2 size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {selectedRecord ? (
          <div className="grid gap-4">
            <DetailRow label="ID" value={selectedRecord.id} />
            <DetailRow label="TaskRun" value={selectedRecord.taskRunId} />
            <DetailRow label="Source" value={selectedRecord.sourceId} />
            <DetailRow label="Hash" value={selectedRecord.contentHash} />
            {selectedRecord.sourceUrl ? (
              <a
                className="inline-flex items-center gap-2 break-all rounded-md border border-[#dfe3ea] px-3 py-2 text-sm text-[#0f766e]"
                href={selectedRecord.sourceUrl}
                rel="noreferrer"
                target="_blank"
              >
                <Link2 size={16} aria-hidden="true" />
                {selectedRecord.sourceUrl}
              </a>
            ) : null}
            <pre className="max-h-[560px] overflow-auto rounded-md bg-[#111827] p-4 text-xs leading-5 text-[#e5e7eb]">
              {JSON.stringify(selectedRecord.content, null, 2)}
            </pre>
          </div>
        ) : (
          <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
            选择一条记录查看详情
          </div>
        )}
      </aside>
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
