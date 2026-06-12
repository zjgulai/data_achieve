"use client";

import { BellRing, PlusCircle, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { createAlertRule, listAlertEvents, listAlertRules } from "@/lib/api/alerts";
import type { AlertChannel, AlertEvent, AlertRule } from "@/types/alert";

const fieldOptions = ["severity", "final_score", "domain", "intelligence_type", "status"];
const opOptions = ["eq", "in", "gte", "lte", "gt", "lt"];

export function AlertsWorkspace() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [name, setName] = useState("High severity signal");
  const [signalType, setSignalType] = useState("*");
  const [field, setField] = useState("severity");
  const [operator, setOperator] = useState("in");
  const [value, setValue] = useState("high,critical");
  const [channel, setChannel] = useState<AlertChannel>("in_app");
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([listAlertRules(), listAlertEvents()])
      .then(([ruleItems, eventItems]) => {
        if (!mounted) {
          return;
        }
        setRules(ruleItems);
        setEvents(eventItems);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load alerts");
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

  async function handleCreateRule() {
    setError(null);
    try {
      const rule = await createAlertRule({
        name,
        projectId: null,
        signalType,
        condition: buildCondition(field, operator, value),
        channel,
        enabled,
      });
      setRules((current) => [rule, ...current]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Alert rule create failed");
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
      <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">预警规则</h2>
            <p className="mt-1 text-sm text-[#6b7280]">规则命中 Signal 后生成 AlertEvent</p>
          </div>
          <ShieldAlert size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {loading ? <p className="text-sm text-[#6b7280]">加载预警中</p> : null}
        {error ? (
          <p className="mb-4 rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
            {error}
          </p>
        ) : null}

        <div className="mb-5 grid gap-3 rounded-md border border-[#dfe3ea] bg-[#f8fafc] p-4">
          <input
            className="rounded-md border border-[#dfe3ea] bg-white px-3 py-2 text-sm"
            onChange={(event) => setName(event.target.value)}
            value={name}
          />
          <div className="grid gap-2 md:grid-cols-2">
            <input
              className="rounded-md border border-[#dfe3ea] bg-white px-3 py-2 text-sm"
              onChange={(event) => setSignalType(event.target.value)}
              value={signalType}
            />
            <select
              className="rounded-md border border-[#dfe3ea] bg-white px-3 py-2 text-sm"
              onChange={(event) => setChannel(event.target.value as AlertChannel)}
              value={channel}
            >
              <option value="in_app">in_app</option>
              <option value="email">email</option>
              <option value="both">both</option>
            </select>
          </div>
          <div className="grid gap-2 md:grid-cols-[1fr_110px_1fr]">
            <select
              className="rounded-md border border-[#dfe3ea] bg-white px-3 py-2 text-sm"
              onChange={(event) => setField(event.target.value)}
              value={field}
            >
              {fieldOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <select
              className="rounded-md border border-[#dfe3ea] bg-white px-3 py-2 text-sm"
              onChange={(event) => setOperator(event.target.value)}
              value={operator}
            >
              {opOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <input
              className="rounded-md border border-[#dfe3ea] bg-white px-3 py-2 text-sm"
              onChange={(event) => setValue(event.target.value)}
              value={value}
            />
          </div>
          <div className="flex items-center justify-between gap-3">
            <label className="inline-flex items-center gap-2 text-sm text-[#374151]">
              <input
                checked={enabled}
                onChange={(event) => setEnabled(event.target.checked)}
                type="checkbox"
              />
              enabled
            </label>
            <button
              className="inline-flex items-center gap-2 rounded-md bg-[#0f766e] px-3 py-2 text-sm font-semibold text-white"
              onClick={() => void handleCreateRule()}
              type="button"
            >
              <PlusCircle size={16} aria-hidden="true" />
              Create
            </button>
          </div>
        </div>

        <div className="grid gap-3">
          {rules.map((rule) => (
            <article className="rounded-md border border-[#dfe3ea] p-4" key={rule.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold">{rule.name}</h3>
                  <p className="mt-2 text-xs text-[#6b7280]">
                    {rule.signalType} · {rule.channel}
                  </p>
                </div>
                <span className="rounded-md bg-[#f1f5f9] px-2.5 py-1 text-xs font-semibold">
                  {rule.enabled ? "enabled" : "disabled"}
                </span>
              </div>
              <code className="mt-3 block rounded-md bg-[#f8fafc] px-3 py-2 text-xs text-[#374151]">
                {JSON.stringify(rule.condition)}
              </code>
            </article>
          ))}
          {!loading && rules.length === 0 ? (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
              暂无预警规则
            </div>
          ) : null}
        </div>
      </section>

      <aside className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">预警事件</h2>
            <p className="mt-1 text-sm text-[#6b7280]">AlertEvent · Notification</p>
          </div>
          <BellRing size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>
        <div className="grid gap-3">
          {events.map((event) => (
            <article className="rounded-md border border-[#dfe3ea] p-4" key={event.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold">
                    {String(event.payload.signal_type ?? "signal")}
                  </h3>
                  <p className="mt-2 text-xs text-[#6b7280]">
                    {formatDate(event.triggeredAt)} · {event.signalId}
                  </p>
                </div>
                <span className="rounded-md bg-[#ecfdf5] px-2.5 py-1 text-xs font-semibold text-[#047857]">
                  {event.status}
                </span>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
                <Metric label="severity" value={event.payload.severity} />
                <Metric label="domain" value={event.payload.domain} />
                <Metric label="score" value={event.payload.final_score} />
                <Metric label="type" value={event.payload.intelligence_type} />
              </dl>
            </article>
          ))}
          {!loading && events.length === 0 ? (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
              暂无预警事件
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

function buildCondition(field: string, operator: string, rawValue: string): Record<string, unknown> {
  if (operator === "in") {
    return {
      field,
      op: operator,
      value: rawValue.split(",").map((item) => item.trim()).filter(Boolean),
    };
  }
  const numeric = Number(rawValue);
  return {
    field,
    op: operator,
    value: Number.isNaN(numeric) ? rawValue : numeric,
  };
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-md bg-[#f8fafc] px-3 py-2">
      <dt className="text-[#6b7280]">{label}</dt>
      <dd className="mt-1 font-semibold text-[#111827]">{value == null ? "n/a" : String(value)}</dd>
    </div>
  );
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
