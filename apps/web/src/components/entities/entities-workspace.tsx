"use client";

import { Boxes, Clock3, ExternalLink, Layers3 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listEntities, listEntitySnapshots } from "@/lib/api/entities";
import { listEntitySignals } from "@/lib/api/signals";
import type { Entity, EntitySnapshot } from "@/types/entity";
import type { Signal } from "@/types/signal";

export function EntitiesWorkspace() {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [snapshots, setSnapshots] = useState<EntitySnapshot[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [snapshotsLoading, setSnapshotsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    listEntities()
      .then((items) => {
        if (!mounted) {
          return;
        }
        setEntities(items);
        setSelectedId(items[0]?.id ?? null);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load entities");
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

  useEffect(() => {
    if (!selectedId) {
      setSnapshots([]);
      return;
    }
    let mounted = true;
    setSnapshotsLoading(true);
    Promise.all([listEntitySnapshots(selectedId), listEntitySignals(selectedId)])
      .then(([snapshotItems, signalItems]) => {
        if (mounted) {
          setSnapshots(snapshotItems);
          setSignals(signalItems);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load snapshots");
        }
      })
      .finally(() => {
        if (mounted) {
          setSnapshotsLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [selectedId]);

  const selectedEntity = useMemo(() => {
    return entities.find((item) => item.id === selectedId) ?? null;
  }, [entities, selectedId]);

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_460px]">
      <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">Entity 列表</h2>
            <p className="mt-1 text-sm text-[#6b7280]">由 RawRecord 标准化生成的实体</p>
          </div>
          <Boxes size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {loading ? <p className="text-sm text-[#6b7280]">加载实体中</p> : null}
        {error ? (
          <p className="mb-4 rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3">
          {entities.map((entity) => (
            <button
              className={`rounded-md border p-4 text-left transition ${
                entity.id === selectedId
                  ? "border-[#0f766e] bg-[#ecfdf5]"
                  : "border-[#dfe3ea] bg-white hover:border-[#94a3b8]"
              }`}
              key={entity.id}
              onClick={() => setSelectedId(entity.id)}
              type="button"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <h3 className="text-sm font-semibold">{entity.name}</h3>
                  <p className="mt-2 break-all text-xs text-[#6b7280]">{entity.externalId}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-md bg-[#f1f5f9] px-2.5 py-1 text-xs font-semibold">
                    {entity.entityType}
                  </span>
                  <span className="rounded-md bg-[#f1f5f9] px-2.5 py-1 text-xs font-semibold">
                    {entity.domain}
                  </span>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-2 text-xs text-[#6b7280]">
                <Clock3 size={14} aria-hidden="true" />
                <span>{new Date(entity.lastSeenAt).toLocaleString()}</span>
              </div>
            </button>
          ))}
          {!loading && entities.length === 0 ? (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
              暂无实体
            </div>
          ) : null}
        </div>
      </section>

      <aside className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">快照时间线</h2>
            <p className="mt-1 text-sm text-[#6b7280]">最新快照、metrics 和 RawRecord 来源</p>
          </div>
          <Layers3 size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {selectedEntity ? (
          <div className="grid gap-4">
            <DetailRow label="Entity ID" value={selectedEntity.id} />
            <DetailRow label="External ID" value={selectedEntity.externalId} />
            {selectedEntity.canonicalUrl ? (
              <a
                className="inline-flex items-center gap-2 break-all rounded-md border border-[#dfe3ea] px-3 py-2 text-sm text-[#0f766e]"
                href={selectedEntity.canonicalUrl}
                rel="noreferrer"
                target="_blank"
              >
                <ExternalLink size={16} aria-hidden="true" />
                {selectedEntity.canonicalUrl}
              </a>
            ) : null}

            <div className="rounded-md border border-[#dfe3ea] p-4">
              <h3 className="text-sm font-semibold">关联信号</h3>
              <div className="mt-3 grid gap-2">
                {signals.map((signal) => (
                  <div className="rounded-md bg-[#f7f8fa] px-3 py-2 text-xs" key={signal.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-semibold">{signal.signalType}</span>
                      <span>{signal.severity}</span>
                    </div>
                    <p className="mt-1 text-[#6b7280]">
                      {new Date(signal.detectedAt).toLocaleString()}
                    </p>
                  </div>
                ))}
                {signals.length === 0 ? (
                  <p className="text-sm text-[#6b7280]">暂无关联信号</p>
                ) : null}
              </div>
            </div>

            {snapshotsLoading ? (
              <p className="text-sm text-[#6b7280]">加载快照中</p>
            ) : (
              <div className="grid gap-3">
                {snapshots.map((snapshot) => (
                  <article className="rounded-md border border-[#dfe3ea] p-4" key={snapshot.id}>
                    <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                      <div>
                        <h3 className="text-sm font-semibold">
                          {new Date(snapshot.capturedAt).toLocaleString()}
                        </h3>
                        <p className="mt-1 break-all text-xs text-[#6b7280]">
                          RawRecord {snapshot.rawRecordId}
                        </p>
                      </div>
                    </div>
                    <MetricGrid metrics={snapshot.metrics} />
                    <pre className="mt-3 max-h-56 overflow-auto rounded-md bg-[#111827] p-3 text-xs leading-5 text-[#e5e7eb]">
                      {JSON.stringify(snapshot.snapshotData, null, 2)}
                    </pre>
                  </article>
                ))}
                {snapshots.length === 0 ? (
                  <div className="rounded-md border border-dashed border-[#dfe3ea] p-6 text-sm text-[#6b7280]">
                    暂无快照
                  </div>
                ) : null}
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
            选择一个实体查看快照
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

function MetricGrid({ metrics }: { metrics: Record<string, unknown> }) {
  const entries = Object.entries(metrics).filter(([, value]) => value !== null);
  if (entries.length === 0) {
    return null;
  }
  return (
    <div className="mt-3 grid grid-cols-2 gap-2">
      {entries.map(([key, value]) => (
        <div className="rounded-md bg-[#f7f8fa] px-3 py-2 text-xs" key={key}>
          <span className="text-[#6b7280]">{key}</span>
          <p className="mt-1 font-semibold">{String(value)}</p>
        </div>
      ))}
    </div>
  );
}
