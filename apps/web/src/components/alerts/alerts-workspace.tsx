"use client";

import {
  BellOff,
  BellRing,
  Braces,
  CheckCircle2,
  Filter,
  Mail,
  Megaphone,
  PlusCircle,
  Radio,
  Search,
  Send,
  ShieldAlert,
  SlidersHorizontal,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  createAlertRule,
  listAlertEvents,
  listAlertRules,
  updateAlertEventStatus,
  type AlertEventStatus,
} from "@/lib/api/alerts";
import { buildAuditFacts, getAuditFactCount, type AuditFact } from "@/lib/audit-display";
import { cn } from "@/lib/utils";
import type { AlertChannel, AlertEvent, AlertRule } from "@/types/alert";

const fieldOptions = ["severity", "final_score", "domain", "intelligence_type", "status"];
const opOptions = ["eq", "in", "gte", "lte", "gt", "lt"];

const channelTone: Record<
  string,
  {
    label: string;
    icon: typeof BellRing;
    accent: string;
    surface: string;
    text: string;
  }
> = {
  in_app: {
    label: "站内",
    icon: BellRing,
    accent: "bg-[#C96F5C]",
    surface: "border-[#E8D4CB] bg-[#FFF7F2]",
    text: "text-[#9E4F41]",
  },
  email: {
    label: "邮件",
    icon: Mail,
    accent: "bg-[#D5A642]",
    surface: "border-[#E7D8B8] bg-[#FFF9E9]",
    text: "text-[#8C6824]",
  },
  both: {
    label: "双通道",
    icon: Send,
    accent: "bg-[#7D9A68]",
    surface: "border-[#D9E2CC] bg-[#F7FBF1]",
    text: "text-[#536B40]",
  },
};

const statusTone: Record<string, string> = {
  triggered: "bg-[#FFF3D5] text-[#8C6824]",
  sent: "bg-[#ECF7EA] text-[#4E7C45]",
  acknowledged: "bg-[#F1EEF8] text-[#6B5685]",
  muted: "bg-[#F6ECE8] text-[#9E5C4D]",
  resolved: "bg-[#EFF7EC] text-[#5D7B4E]",
};

export function AlertsWorkspace() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [name, setName] = useState("High severity signal");
  const [signalType, setSignalType] = useState("*");
  const [field, setField] = useState("severity");
  const [operator, setOperator] = useState("in");
  const [value, setValue] = useState("high,critical");
  const [channel, setChannel] = useState<AlertChannel>("in_app");
  const [enabled, setEnabled] = useState(true);
  const [eventStatusFilter, setEventStatusFilter] = useState("all");
  const [eventSearchTerm, setEventSearchTerm] = useState("");
  const [message, setMessage] = useState<string | null>(null);
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
        setSelectedEventId(eventItems[0]?.id ?? null);
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

  const selectedEvent = useMemo(() => {
    return events.find((event) => event.id === selectedEventId) ?? null;
  }, [events, selectedEventId]);

  const eventStatuses = useMemo(() => {
    return Array.from(new Set(events.map((event) => event.status)));
  }, [events]);

  const filteredEvents = useMemo(() => {
    const term = eventSearchTerm.trim().toLowerCase();
    return events.filter((event) => {
      const matchesStatus = eventStatusFilter === "all" || event.status === eventStatusFilter;
      if (!matchesStatus) {
        return false;
      }
      if (!term) {
        return true;
      }
      return [event.id, event.signalId, event.ruleId, event.status, JSON.stringify(event.payload)]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [eventSearchTerm, eventStatusFilter, events]);

  const stats = useMemo(() => {
    const enabledRules = rules.filter((rule) => rule.enabled).length;
    const sentEvents = events.filter((event) => Boolean(event.sentAt)).length;
    const activeChannels = new Set(rules.map((rule) => rule.channel)).size;
    return {
      rules: rules.length,
      enabledRules,
      events: events.length,
      sentEvents,
      activeChannels,
    };
  }, [events, rules]);

  async function handleCreateRule() {
    setError(null);
    setMessage(null);
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
      setMessage(`${rule.name}: rule created`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Alert rule create failed");
    }
  }

  async function handleUpdateEventStatus(eventId: string, nextStatus: AlertEventStatus) {
    setError(null);
    setMessage(null);
    try {
      const updated = await updateAlertEventStatus(eventId, nextStatus);
      setEvents((current) => current.map((event) => (event.id === updated.id ? updated : event)));
      setSelectedEventId(updated.id);
      setMessage(`AlertEvent ${updated.id.slice(0, 8)}: ${updated.status}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Alert event update failed");
    }
  }

  return (
    <div className="grid min-w-0 gap-5">
      <section className="overflow-hidden rounded-2xl border border-[#EDDCD3] bg-[#FFF8F4] shadow-[0_18px_60px_rgba(115,70,58,0.08)]">
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <ShieldAlert size={14} aria-hidden="true" />
              Alert Delivery Layer
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C] sm:text-3xl">
              预警交付控制台
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#7A625A]">
              当 Signal 命中规则后生成 AlertEvent，并按站内、邮件或双通道推送给团队。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-4">
              <MetricPill icon={SlidersHorizontal} label="规则数" value={String(stats.rules)} />
              <MetricPill icon={CheckCircle2} label="启用规则" value={`${stats.enabledRules}/${stats.rules}`} />
              <MetricPill icon={BellRing} label="事件数" value={String(stats.events)} />
              <MetricPill icon={Send} label="已发送" value={String(stats.sentEvents)} />
            </div>
          </div>

          <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">Channels</p>
                <h3 className="mt-1 text-base font-semibold text-[#2E201C]">交付通道</h3>
              </div>
              <span className="rounded-full bg-[#C96F5C] px-3 py-1 text-xs font-semibold text-white">
                {stats.activeChannels} active
              </span>
            </div>
            <div className="mt-4 grid gap-2">
              {Object.entries(channelTone).map(([channelKey, tone]) => (
                <ChannelRow
                  count={rules.filter((rule) => rule.channel === channelKey).length}
                  key={channelKey}
                  tone={tone}
                />
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_460px]">
        <section className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">Alert Rules</p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">规则配置</h2>
              <p className="mt-1 text-sm text-[#7A625A]">定义信号类型、匹配条件和交付通道。</p>
            </div>
            <span className="inline-flex w-fit items-center gap-2 rounded-full border border-[#E8D4CB] bg-[#FFF7F2] px-3 py-1.5 text-xs font-semibold text-[#9E5C4D]">
              <Radio size={14} aria-hidden="true" />
              Signal match
            </span>
          </div>

          {loading ? (
            <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
              加载预警中
            </div>
          ) : null}
          <StatusNotice error={error} message={message} />

          <div className="mb-5 rounded-2xl border border-[#E8D4CB] bg-[#FFF8F4] p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">New Rule</p>
                <h3 className="mt-1 text-base font-semibold text-[#2E201C]">创建预警规则</h3>
              </div>
              <button
                className="inline-flex h-10 items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.24)] transition hover:bg-[#B85F4F]"
                onClick={() => void handleCreateRule()}
                type="button"
              >
                <PlusCircle size={16} aria-hidden="true" />
                Create
              </button>
            </div>
            <div className="grid gap-3">
              <TextField label="规则名称" onChange={setName} value={name} />
              <div className="grid gap-3 md:grid-cols-2">
                <TextField label="Signal Type" onChange={setSignalType} value={signalType} />
                <SelectField
                  label="Channel"
                  onChange={(nextValue) => setChannel(nextValue as AlertChannel)}
                  options={[
                    { label: "站内通知", value: "in_app" },
                    { label: "邮件", value: "email" },
                    { label: "双通道", value: "both" },
                  ]}
                  value={channel}
                />
              </div>
              <div className="grid gap-3 md:grid-cols-[1fr_120px_1fr]">
                <SelectField
                  label="Field"
                  onChange={setField}
                  options={fieldOptions.map((option) => ({ label: option, value: option }))}
                  value={field}
                />
                <SelectField
                  label="Op"
                  onChange={setOperator}
                  options={opOptions.map((option) => ({ label: option, value: option }))}
                  value={operator}
                />
                <TextField label="Value" onChange={setValue} value={value} />
              </div>
              <div className="flex flex-col gap-3 rounded-xl border border-[#E8D4CB] bg-white/70 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                <button
                  className="inline-flex w-fit items-center gap-2 text-sm font-semibold text-[#7D4F43]"
                  onClick={() => setEnabled((current) => !current)}
                  type="button"
                >
                  {enabled ? <ToggleRight size={20} aria-hidden="true" /> : <ToggleLeft size={20} aria-hidden="true" />}
                  {enabled ? "enabled" : "disabled"}
                </button>
                <RuleConditionSummary condition={buildCondition(field, operator, value)} />
              </div>
            </div>
          </div>

          <div className="grid gap-3">
            {rules.map((rule) => (
              <RuleCard key={rule.id} rule={rule} />
            ))}
            {!loading && rules.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
                暂无预警规则。
              </div>
            ) : null}
          </div>
        </section>

        <aside className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">Alert Events</p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">预警事件流</h2>
              <p className="mt-1 text-sm text-[#7A625A]">事件状态、触发信号和交付事实。</p>
            </div>
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#C96F5C] text-white">
              <Megaphone size={18} aria-hidden="true" />
            </span>
          </div>

          <div className="mb-4 grid gap-2 sm:grid-cols-2">
            <label className="relative block">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                size={16}
                aria-hidden="true"
              />
              <input
                className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                onChange={(event) => setEventSearchTerm(event.target.value)}
                placeholder="搜索事件、信号"
                value={eventSearchTerm}
              />
            </label>
            <label className="relative block">
              <Filter
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                size={16}
                aria-hidden="true"
              />
              <select
                className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-8 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                onChange={(event) => setEventStatusFilter(event.target.value)}
                value={eventStatusFilter}
              >
                <option value="all">全部状态</option>
                {eventStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid gap-3">
            {filteredEvents.map((event) => (
              <EventCard
                event={event}
                key={event.id}
                onSelect={() => setSelectedEventId(event.id)}
                selected={event.id === selectedEventId}
              />
            ))}
            {!loading && filteredEvents.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
                没有匹配的预警事件。
              </div>
            ) : null}
          </div>

          {selectedEvent ? (
            <EventPayload
              event={selectedEvent}
              onUpdateStatus={(nextStatus) => {
                void handleUpdateEventStatus(selectedEvent.id, nextStatus);
              }}
            />
          ) : null}
        </aside>
      </div>
    </div>
  );
}

function RuleCard({ rule }: { rule: AlertRule }) {
  const tone = getChannelTone(rule.channel);
  const Icon = tone.icon;
  const conditionFacts = buildAuditFacts(rule.condition, 6);
  const conditionCount = getAuditFactCount(rule.condition);
  return (
    <article className={cn("rounded-2xl border p-4", tone.surface)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-3">
            <span
              className={cn(
                "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white",
                tone.accent,
              )}
            >
              <Icon size={17} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h3 className="break-words text-base font-semibold text-[#2E201C]">{rule.name}</h3>
              <p className="mt-1 text-sm text-[#7A625A]">
                {rule.signalType} · {tone.label}
              </p>
            </div>
          </div>
        </div>
        <span
          className={cn(
            "w-fit rounded-full px-2.5 py-1 text-xs font-semibold",
            rule.enabled ? "bg-[#ECF7EA] text-[#4E7C45]" : "bg-[#F6ECE8] text-[#9E5C4D]",
          )}
        >
          {rule.enabled ? "enabled" : "disabled"}
        </span>
      </div>
      <div className="mt-4 rounded-xl border border-white/80 bg-white/75 p-3">
        <div className="mb-2 flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase text-[#B47767]">触发条件</p>
          <span className="rounded-full bg-[#FFF8F4] px-2 py-0.5 text-xs font-semibold text-[#7D4F43]">
            {conditionCount} facts
          </span>
        </div>
        <FactGrid facts={conditionFacts} emptyText="没有额外触发条件。" />
      </div>
    </article>
  );
}

function EventCard({
  event,
  selected,
  onSelect,
}: {
  event: AlertEvent;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      className={cn(
        "rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4 text-left transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(72,45,38,0.1)]",
        selected ? "ring-2 ring-[#C96F5C] ring-offset-2 ring-offset-white" : "",
      )}
      onClick={onSelect}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="break-words text-base font-semibold text-[#2E201C]">
            {String(event.payload.signal_type ?? "signal")}
          </h3>
          <p className="mt-1 break-all text-xs text-[#7A625A]">
            {formatDate(event.triggeredAt)} · {event.signalId}
          </p>
        </div>
        <span
          className={cn(
            "rounded-full px-2.5 py-1 text-xs font-semibold",
            statusTone[event.status] ?? "bg-[#F6ECE8] text-[#7D4F43]",
          )}
        >
          {event.status}
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <Metric label="severity" value={event.payload.severity} />
        <Metric label="domain" value={event.payload.domain} />
        <Metric label="score" value={event.payload.final_score} />
        <Metric label="channel" value={event.payload.channel} />
      </dl>
    </button>
  );
}

function EventPayload({
  event,
  onUpdateStatus,
}: {
  event: AlertEvent;
  onUpdateStatus: (status: AlertEventStatus) => void;
}) {
  return (
    <div className="mt-4 rounded-2xl border border-[#E8D4CB] bg-[#FFF8F4] p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase text-[#B47767]">事件事实</p>
        <span className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#7D4F43]">
          <Braces size={13} aria-hidden="true" />
          {formatShortTraceId(event.id)}
        </span>
      </div>
      <div className="mb-3 grid grid-cols-3 gap-2">
        <EventActionButton
          disabled={event.status === "acknowledged"}
          icon={CheckCircle2}
          label="确认"
          onClick={() => onUpdateStatus("acknowledged")}
        />
        <EventActionButton
          disabled={event.status === "muted"}
          icon={BellOff}
          label="静默"
          onClick={() => onUpdateStatus("muted")}
        />
        <EventActionButton
          disabled={event.status === "resolved"}
          icon={CheckCircle2}
          label="解决"
          onClick={() => onUpdateStatus("resolved")}
        />
      </div>
      <FactGrid
        facts={buildAuditFacts(event.payload, 8)}
        emptyText="没有可展示的事件事实字段。"
      />
    </div>
  );
}

function EventActionButton({
  disabled,
  icon: Icon,
  label,
  onClick,
}: {
  disabled: boolean;
  icon: typeof CheckCircle2;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={cn(
        "h-9 rounded-xl border px-2 text-xs font-semibold transition",
        disabled
          ? "border-[#E8D4CB] bg-white/50 text-[#B49A91]"
          : "border-[#C96F5C] bg-white text-[#B85F4F] hover:bg-[#FFFDFC]",
      )}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <Icon className="inline-block" size={13} aria-hidden="true" />{" "}
      {label}
    </button>
  );
}

function MetricPill({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof BellRing;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 px-4 py-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
        <Icon size={14} aria-hidden="true" />
        {label}
      </div>
      <p className="mt-2 break-words text-xl font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

function ChannelRow({
  tone,
  count,
}: {
  tone: (typeof channelTone)[string];
  count: number;
}) {
  const Icon = tone.icon;
  return (
    <div className="flex items-center justify-between rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2">
      <span className="inline-flex items-center gap-2 text-sm font-medium text-[#3B2924]">
        <span className={cn("inline-flex h-7 w-7 items-center justify-center rounded-full text-white", tone.accent)}>
          <Icon size={14} aria-hidden="true" />
        </span>
        {tone.label}
      </span>
      <span className="text-sm font-semibold text-[#3B2924]">{count}</span>
    </div>
  );
}

function StatusNotice({ message, error }: { message: string | null; error: string | null }) {
  if (!message && !error) {
    return null;
  }
  return (
    <div className="mb-4 grid gap-2">
      {message ? (
        <p className="rounded-xl border border-[#CDE6C4] bg-[#F3FAEF] px-3 py-2 text-sm font-medium text-[#4E7C45]">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
      <span>{label}</span>
      <input
        className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ label: string; value: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
      <span>{label}</span>
      <select
        className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function RuleConditionSummary({ condition }: { condition: Record<string, unknown> }) {
  const facts = buildAuditFacts(condition, 3);
  if (facts.length === 0) {
    return (
      <span className="break-words rounded-lg bg-[#FFF8F4] px-3 py-2 text-xs font-semibold text-[#7D4F43]">
        无额外条件
      </span>
    );
  }
  return (
    <span className="break-words rounded-lg bg-[#FFF8F4] px-3 py-2 text-xs font-semibold text-[#7D4F43]">
      {facts.map((fact) => `${fact.label}: ${fact.value}`).join(" / ")}
    </span>
  );
}

function FactGrid({
  facts,
  emptyText,
}: {
  facts: AuditFact[];
  emptyText: string;
}) {
  if (facts.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-[#E8D4CB] bg-white/70 px-3 py-3 text-sm text-[#7A625A]">
        {emptyText}
      </p>
    );
  }
  return (
    <div className="grid gap-2">
      {facts.map((fact) => (
        <div
          className="rounded-xl border border-[#F0E1D9] bg-white/80 px-3 py-2 text-sm"
          key={`${fact.label}-${fact.value}`}
        >
          <p className="text-xs font-semibold uppercase text-[#B47767]">{fact.label}</p>
          <p className="mt-1 break-words font-semibold text-[#3B2924]">{fact.value}</p>
        </div>
      ))}
    </div>
  );
}

function buildCondition(field: string, operator: string, rawValue: string): Record<string, unknown> {
  if (operator === "in") {
    return {
      field,
      op: operator,
      value: rawValue
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
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
    <div className="rounded-xl border border-[#F0E1D9] bg-[#FFF8F4] px-3 py-2">
      <dt className="text-[#B47767]">{label}</dt>
      <dd className="mt-1 break-words font-semibold text-[#3B2924]">
        {value == null ? "n/a" : String(value)}
      </dd>
    </div>
  );
}

function getChannelTone(channel: string) {
  return channelTone[channel] ?? channelTone.in_app;
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatShortTraceId(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return value.length > 12 ? `${value.slice(0, 8)}...` : value;
}
