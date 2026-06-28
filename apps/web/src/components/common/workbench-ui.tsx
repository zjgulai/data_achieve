"use client";

import { type LucideIcon, Loader2 } from "lucide-react";
import { type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export type WorkflowLaneId = string;

export type WorkflowLaneItem = {
  caption: string;
  id: WorkflowLaneId;
  title: string;
};

export function WorkflowLaneRail({
  activeLane,
  lanes,
}: {
  activeLane: WorkflowLaneId;
  lanes: WorkflowLaneItem[];
}) {
  return (
    <section className="rounded-2xl border border-[#E8D4CB] bg-white/80 p-3">
      <div className="grid gap-2 sm:grid-cols-5">
        {lanes.map((lane, index) => {
          const active = lane.id === activeLane;
          return (
            <div
              aria-current={active ? "step" : undefined}
              className={cn(
                "min-h-16 rounded-xl border px-3 py-2 transition",
                active
                  ? "border-[#C96F5C] bg-[#FFF1EC] text-[#7D4F43]"
                  : "border-[#F0E1D9] bg-[#FFFDFC] text-[#7A625A]",
              )}
              key={lane.id}
            >
              <p className="text-[11px] font-semibold uppercase tracking-normal">
                {String(index + 1).padStart(2, "0")}
              </p>
              <p className="mt-1 text-sm font-semibold text-[#2E201C]">{lane.title}</p>
              <p className="mt-0.5 text-xs leading-4">{lane.caption}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function WorkflowLane({
  children,
  description,
  icon: Icon,
  label,
  title,
}: {
  children: ReactNode;
  description: string;
  icon: LucideIcon;
  label: string;
  title: string;
}) {
  return (
    <section aria-label={title} className="grid min-w-0 gap-3">
      <div className="flex min-w-0 flex-col gap-2 border-l-4 border-[#C96F5C] pl-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
            <Icon size={14} aria-hidden="true" />
            {label}
          </p>
          <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">{title}</h2>
        </div>
        <p className="max-w-3xl text-sm leading-6 text-[#7A625A]">{description}</p>
      </div>
      {children}
    </section>
  );
}

export function WorkbenchPanel({
  action,
  children,
  icon: Icon,
  label,
  subtitle,
  title,
}: {
  action?: ReactNode;
  children: ReactNode;
  icon: LucideIcon;
  label?: string;
  subtitle?: string;
  title: string;
}) {
  if (!label) {
    return (
      <section className="min-w-0 rounded-2xl border border-[#F0E1D9] bg-white p-4">
        <div className="mb-4 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#FFF1EC] text-[#C96F5C]">
            <Icon size={17} aria-hidden="true" />
          </span>
          <h2 className="text-base font-semibold text-[#2E201C]">{title}</h2>
        </div>
        {children}
      </section>
    );
  }

  return (
    <section className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
            <Icon size={14} aria-hidden="true" />
            {label}
          </p>
          <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-[#86868B]">{subtitle}</p> : null}
        </div>
        {action ? <span className="whitespace-nowrap">{action}</span> : null}
      </div>
      {children}
    </section>
  );
}

export function WorkbenchFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
      <p className="text-xs font-semibold uppercase text-[#B47767]">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

export function WorkbenchDetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/80 bg-white/75 px-3 py-2 text-sm">
      <span className="text-xs font-semibold uppercase text-[#B47767]">{label}</span>
      <p className="mt-1 break-all font-semibold text-[#3B2924]">{value}</p>
    </div>
  );
}

export function WorkbenchTraceDetailRow({
  label,
  surface = "white",
  value,
}: {
  label: string;
  surface?: "warm" | "white";
  value: string;
}) {
  return (
    <div className={cn("rounded-xl px-3 py-2 text-sm", surface === "warm" ? "bg-[#FBF8F5]" : "bg-white")}>
      <span className="text-[#86868B]">{label}</span>
      <p className="mt-1 break-all font-medium text-[#1D1D1F]">{value}</p>
    </div>
  );
}

export function WorkbenchKeyValueRow({
  label,
  labelSlot,
  value,
}: {
  label?: string;
  labelSlot?: ReactNode;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2">
      {labelSlot ?? <span className="text-sm font-medium text-[#7A625A]">{label}</span>}
      <span className="text-sm font-semibold text-[#3B2924]">{value}</span>
    </div>
  );
}

export function WorkbenchTag({
  children,
  className,
  shape = "tag",
  tone,
}: {
  children: ReactNode;
  className?: string;
  shape?: "pill" | "tag";
  tone?: "amber" | "green" | "muted" | "neutral" | "red" | "rose" | "roseStrong";
}) {
  const toneClasses = {
    amber: "bg-[#FFF4DE] text-[#FF9800]",
    neutral: "bg-white text-[#5F5757]",
    muted: "bg-[#FBF8F5] text-[#86868B]",
    green: "bg-[#EAF8EE] text-[#2EBA62]",
    red: "bg-[#FFE5E2] text-[#FF3B30]",
    rose: "bg-[#FFF1EC] text-[#B85F4F]",
    roseStrong: "bg-[#FCEBF0] text-[#C25B6E]",
  };
  const shapeClass = shape === "pill" ? "rounded-full px-3 py-1" : "rounded-lg px-2 py-1";

  return <span className={cn(shapeClass, "text-xs font-semibold", toneClasses[tone ?? "neutral"], className)}>{children}</span>;
}

export function WorkbenchStatusRow({
  label,
  tone = "neutral",
  value,
}: {
  label: string;
  tone?: "green" | "neutral" | "red";
  value: string | number;
}) {
  const valueClass = {
    green: "text-[#2EBA62]",
    neutral: "text-[#1D1D1F]",
    red: "text-[#FF3B30]",
  }[tone];

  return (
    <div className="flex items-center justify-between rounded-xl bg-[#FBF8F5] px-3 py-2">
      <span className="text-[#86868B]">{label}</span>
      <span className={cn("font-semibold", valueClass)}>{value}</span>
    </div>
  );
}

type WorkbenchMetricTone = "amber" | "green" | "red" | "rose" | "violet" | "neutral";

export function WorkbenchMetric({
  icon: Icon,
  label,
  size = "compact",
  tone,
  value,
  caption,
}: {
  icon?: LucideIcon;
  label: string;
  size?: "large" | "compact";
  tone?: WorkbenchMetricTone;
  value: string;
  caption?: string;
}) {
  const toneClasses: Record<WorkbenchMetricTone, string> = {
    amber: "text-[#FF9800]",
    green: "text-[#2EBA62]",
    red: "text-[#FF3B30]",
    rose: "text-[#C25B6E]",
    violet: "text-[#6E5CF6]",
    neutral: "text-[#B47767]",
  };

  if (size === "large") {
    return (
      <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
          {Icon ? (
            <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-full", toneClasses[tone ?? "neutral"])}>
              <Icon size={15} aria-hidden="true" />
            </span>
          ) : null}
          <span className={cn("leading-5", tone ? toneClasses[tone] : undefined)}>{label}</span>
        </div>
        {caption ? (
          <p className={cn("mt-1 text-[11px] font-semibold", tone ? toneClasses[tone] : "text-[#7A625A]")}>
            {caption}
          </p>
        ) : null}
        <p className={cn("mt-2 text-2xl font-semibold text-[#2E201C]", tone ? toneClasses[tone] : undefined)}>{value}</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-2 py-2">
      <p className={cn("text-xs font-semibold", tone ? toneClasses[tone] : "text-[#B47767]")}>{label}</p>
      {caption ? (
        <p className={cn("mt-1 text-[11px] font-semibold", tone ? toneClasses[tone] : "text-[#7A625A]")}>
          {caption}
        </p>
      ) : null}
      <p className="mt-1 text-sm font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

export function WorkbenchMetricPill({
  icon: Icon,
  label,
  value,
  valueSize = "xl",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  valueSize?: "large" | "xl";
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 px-4 py-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
        <Icon size={14} aria-hidden="true" />
        {label}
      </div>
      <p
        className={cn(
          "mt-2 break-words font-semibold text-[#2E201C]",
          valueSize === "large" ? "text-2xl" : "text-xl",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export type WorkbenchStatusTone = "amber" | "green" | "neutral" | "red" | "rose" | "violet";

export function WorkbenchStatusPill({
  children,
  status,
  tone,
}: {
  children?: ReactNode;
  status: string;
  tone?: WorkbenchStatusTone;
}) {
  const normalized = status.toLowerCase();
  const toneClasses: Record<WorkbenchStatusTone, string> = {
    amber: "bg-[#FFF4DE] text-[#FF9800]",
    green: "bg-[#EAF8EE] text-[#2EBA62]",
    neutral: "bg-[#FBF8F5] text-[#86868B]",
    red: "bg-[#FFE5E2] text-[#FF3B30]",
    rose: "bg-[#FFF7F8] text-[#C25B6E]",
    violet: "bg-[#F5F0FF] text-[#6E5CF6]",
  };
  const className = tone
    ? toneClasses[tone]
    : normalized.includes("critical")
      ? "bg-[#FFF2EF] text-[#B85F4F]"
      : normalized.includes("warning")
        ? "bg-[#FFF8E8] text-[#9C6A1E]"
        : normalized.includes("success") || normalized.includes("ok") || normalized.includes("saved")
          ? "bg-[#EAF7EE] text-[#287A45]"
          : "bg-[#FFF8F4] text-[#7D4F43]";
  return (
    <span className={cn("rounded-full px-2.5 py-1 text-xs font-semibold", className)}>
      {children ?? status}
    </span>
  );
}

export function WorkbenchDomainCard({
  intelligenceCount,
  label,
  projectCount,
  signalCount,
}: {
  intelligenceCount: number;
  label: string;
  projectCount: number;
  signalCount: number;
}) {
  return (
    <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-[#1D1D1F]">{label}</p>
        <span className="rounded-lg bg-white px-2 py-1 text-xs font-semibold text-[#C25B6E]">
          {intelligenceCount} intelligence
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-xl bg-white px-3 py-2">
          <p className="text-[#86868B]">Signals</p>
          <p className="mt-1 text-lg font-semibold text-[#1D1D1F]">{signalCount}</p>
        </div>
        <div className="rounded-xl bg-white px-3 py-2">
          <p className="text-[#86868B]">Projects</p>
          <p className="mt-1 text-lg font-semibold text-[#1D1D1F]">{projectCount}</p>
        </div>
      </div>
    </div>
  );
}

export function WorkbenchDistributionRow({
  label,
  size = "default",
  tone = "rose",
  value,
  width,
}: {
  label: string;
  size?: "default" | "compact";
  tone?: "rose" | "amber" | "green" | "red";
  value: string;
  width: number;
}) {
  const barColor = {
    rose: "bg-[#C25B6E]",
    amber: "bg-[#F0B95F]",
    green: "bg-[#2EBA62]",
    red: "bg-[#FF3B30]",
  }[tone];

  return (
    <div className={cn("grid min-w-0 grid-cols-1", size === "compact" ? "gap-1" : "gap-2")}>
      <div className={cn("flex items-center justify-between", size === "compact" ? "text-xs" : "text-sm")}>
        <span className="font-semibold text-[#5F5757]">{label}</span>
        <span className={size === "compact" ? "text-[#86868B]" : "font-semibold text-[#1D1D1F]"}>{value}</span>
      </div>
      <div className="h-2 rounded-full bg-[#F5EDE8]">
        <div className={cn("h-2 rounded-full", barColor)} style={{ width: `${clampPercent(width)}%` }} />
      </div>
    </div>
  );
}

function clampPercent(value: number) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
}

export type ActionGateTone = "preview" | "write" | "send" | "export" | "schedule";

export type ActionButtonTone =
  | "primary"
  | "secondary"
  | "outline"
  | "danger"
  | "success"
  | "muted";

export function WorkbenchActionButton({
  children,
  icon: Icon,
  loading,
  tone = "primary",
  ...props
}: {
  children: ReactNode;
  icon?: LucideIcon;
  loading?: boolean;
  tone?: ActionButtonTone;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60";
  const toneClass = {
    primary: "h-11 bg-[#C96F5C] text-white hover:bg-[#B85F4F]",
    secondary: "h-11 bg-[#2E201C] text-white hover:bg-[#46332C]",
    danger: "h-11 bg-[#7A5A3E] text-white hover:bg-[#674A35]",
    success: "h-11 bg-[#287A45] text-white hover:bg-[#22683B]",
    outline: "h-11 border border-[#E8D4CB] bg-white text-[#7D4F4F] hover:border-[#C96F5C]",
    muted: "h-11 border border-[#D9E2CC] bg-[#FAFCF7] text-[#4E7C45] hover:border-[#4E7C45]",
  }[tone];

  return (
    <button
      {...props}
      className={cn(base, toneClass, props.className)}
      disabled={props.disabled || loading}
      type={props.type ?? "button"}
    >
      {loading ? <Loader2 className="animate-spin" size={15} aria-hidden="true" /> : null}
      {loading ? null : Icon ? <Icon size={15} aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function ActionGate({
  boundary,
  children,
  description,
  icon: Icon,
  title,
  tone,
}: {
  boundary: string[];
  children: ReactNode;
  description: string;
  icon: LucideIcon;
  title: string;
  tone: ActionGateTone;
}) {
  const toneClass = {
    preview: "border-[#D9E2CC] bg-[#FAFCF7] text-[#4E7C45]",
    write: "border-[#F0D8C4] bg-[#FFF8F4] text-[#A65E45]",
    send: "border-[#D5E4D9] bg-[#F4FBF6] text-[#287A45]",
    export: "border-[#E8D4CB] bg-[#FFFDFC] text-[#7D4F43]",
    schedule: "border-[#D9E2CC] bg-[#FAFCF7] text-[#4E7C45]",
  }[tone];

  return (
    <div className={cn("grid gap-3 rounded-xl border p-3", toneClass)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/80">
              <Icon size={16} aria-hidden="true" />
            </span>
            <h3 className="text-sm font-semibold text-[#2E201C]">{title}</h3>
          </div>
          <p className="mt-2 text-sm leading-6 text-[#7A625A]">{description}</p>
        </div>
        <div className="grid gap-1 text-xs font-semibold leading-5 text-[#6B5D58] sm:max-w-xs">
          {boundary.map((item) => (
            <span className="rounded-lg bg-white/80 px-2.5 py-1" key={item}>
              {item}
            </span>
          ))}
        </div>
      </div>
      {children}
    </div>
  );
}

export function WorkbenchEmptyState({
  compact = false,
  icon: Icon,
  text,
  title,
}: {
  compact?: boolean;
  icon?: LucideIcon;
  text: string;
  title?: string;
}) {
  if (compact) {
    return (
      <p className="rounded-xl border border-dashed border-[#E8D4CB] bg-[#FFFDFC] px-3 py-3 text-sm leading-6 text-[#7A625A]">
        {text}
      </p>
    );
  }

  return (
    <section className="rounded-2xl border border-dashed border-[#DDBEAF] bg-white/70 p-8">
      <div className="mx-auto max-w-2xl text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#FFF0EA] text-[#C96F5C]">
          {Icon ? <Icon size={22} aria-hidden="true" /> : null}
        </span>
        {title ? <h2 className="mt-4 text-lg font-semibold text-[#2E201C]">{title}</h2> : null}
        <p className="mt-2 text-sm leading-6 text-[#7A625A]">{text}</p>
      </div>
    </section>
  );
}
