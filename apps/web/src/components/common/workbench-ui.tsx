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
    <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3">
      <div className="grid gap-2 sm:grid-cols-5">
        {lanes.map((lane, index) => {
          const active = lane.id === activeLane;
          return (
            <div
              aria-current={active ? "step" : undefined}
              className={cn(
                "min-h-16 rounded-[var(--radius-2)] border px-3 py-2 transition-colors duration-[var(--duration-base)]",
                active
                  ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                  : "border-[var(--border-subtle)] bg-[var(--surface-secondary)] text-[var(--text-secondary)]",
              )}
              key={lane.id}
            >
              <p className="text-[11px] font-semibold uppercase tracking-normal">
                {String(index + 1).padStart(2, "0")}
              </p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{lane.title}</p>
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
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase text-[var(--action-primary)]">
            <Icon size={14} aria-hidden="true" />
            {label}
          </p>
          <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{title}</h2>
        </div>
        <p className="max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">{description}</p>
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
      <section className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4">
        <div className="mb-4 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-2)] bg-[var(--accent-1-soft)] text-[var(--action-primary)]">
            <Icon size={17} aria-hidden="true" />
          </span>
          <h2 className="text-base font-semibold text-[var(--text-primary)]">{title}</h2>
        </div>
        {children}
      </section>
    );
  }

  return (
    <section className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4 sm:p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase text-[var(--action-primary)]">
            <Icon size={14} aria-hidden="true" />
            {label}
          </p>
          <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-[var(--text-tertiary)]">{subtitle}</p> : null}
        </div>
        {action ? <span className="whitespace-nowrap">{action}</span> : null}
      </div>
      {children}
    </section>
  );
}

export function WorkbenchFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-3">
      <p className="text-xs font-semibold uppercase text-[var(--action-primary)]">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

export function WorkbenchDetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm">
      <span className="text-xs font-semibold uppercase text-[var(--action-primary)]">{label}</span>
      <p className="mt-1 break-all font-semibold text-[var(--text-primary)]">{value}</p>
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
    <div className={cn("rounded-[var(--radius-2)] px-3 py-2 text-sm", surface === "warm" ? "bg-[var(--surface-muted)]" : "bg-[var(--surface-primary)]")}>
      <span className="text-[var(--text-tertiary)]">{label}</span>
      <p className="mt-1 break-all font-medium text-[var(--text-primary)]">{value}</p>
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
    <div className="flex items-center justify-between rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2">
      {labelSlot ?? <span className="text-sm font-medium text-[var(--text-secondary)]">{label}</span>}
      <span className="text-sm font-semibold text-[var(--text-primary)]">{value}</span>
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
    amber: "bg-[var(--warning-soft)] text-[var(--state-warning)]",
    neutral: "bg-[var(--surface-primary)] text-[var(--text-secondary)]",
    muted: "bg-[var(--surface-muted)] text-[var(--text-tertiary)]",
    green: "bg-[var(--success-soft)] text-[var(--state-success)]",
    red: "bg-[var(--danger-soft)] text-[var(--state-danger)]",
    rose: "bg-[var(--accent-1-soft)] text-[var(--action-primary)]",
    roseStrong: "bg-[var(--accent-1-soft)] text-[var(--action-primary-pressed)]",
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
    green: "text-[var(--state-success)]",
    neutral: "text-[var(--text-primary)]",
    red: "text-[var(--state-danger)]",
  }[tone];

  return (
    <div className="flex items-center justify-between rounded-[var(--radius-2)] bg-[var(--surface-muted)] px-3 py-2">
      <span className="text-[var(--text-tertiary)]">{label}</span>
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
    amber: "text-[var(--state-warning)]",
    green: "text-[var(--state-success)]",
    red: "text-[var(--state-danger)]",
    rose: "text-[var(--action-primary)]",
    violet: "text-[var(--state-info)]",
    neutral: "text-[var(--text-tertiary)]",
  };

  if (size === "large") {
    return (
      <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[var(--text-tertiary)]">
          {Icon ? (
            <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-full", toneClasses[tone ?? "neutral"])}>
              <Icon size={15} aria-hidden="true" />
            </span>
          ) : null}
          <span className={cn("leading-5", tone ? toneClasses[tone] : undefined)}>{label}</span>
        </div>
        {caption ? (
          <p className={cn("mt-1 text-[11px] font-semibold", tone ? toneClasses[tone] : "text-[var(--text-secondary)]")}>
            {caption}
          </p>
        ) : null}
        <p className={cn("mt-2 text-2xl font-semibold text-[var(--text-primary)]", tone ? toneClasses[tone] : undefined)}>{value}</p>
      </div>
    );
  }

  return (
    <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-2 py-2">
      <p className={cn("text-xs font-semibold", tone ? toneClasses[tone] : "text-[var(--text-tertiary)]")}>{label}</p>
      {caption ? (
        <p className={cn("mt-1 text-[11px] font-semibold", tone ? toneClasses[tone] : "text-[var(--text-secondary)]")}>
          {caption}
        </p>
      ) : null}
      <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{value}</p>
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
    <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[var(--text-tertiary)]">
        <Icon size={14} aria-hidden="true" />
        {label}
      </div>
      <p
        className={cn(
          "mt-2 break-words font-semibold text-[var(--text-primary)]",
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
    amber: "bg-[var(--warning-soft)] text-[var(--state-warning)]",
    green: "bg-[var(--success-soft)] text-[var(--state-success)]",
    neutral: "bg-[var(--surface-muted)] text-[var(--text-tertiary)]",
    red: "bg-[var(--danger-soft)] text-[var(--state-danger)]",
    rose: "bg-[var(--accent-1-soft)] text-[var(--action-primary)]",
    violet: "bg-[var(--accent-2-soft)] text-[var(--state-info)]",
  };
  const className = tone
    ? toneClasses[tone]
    : normalized.includes("critical")
      ? "bg-[var(--danger-soft)] text-[var(--state-danger)]"
      : normalized.includes("warning")
        ? "bg-[var(--warning-soft)] text-[var(--state-warning)]"
        : normalized.includes("success") || normalized.includes("ok") || normalized.includes("saved")
          ? "bg-[var(--success-soft)] text-[var(--state-success)]"
          : "bg-[var(--surface-muted)] text-[var(--text-secondary)]";
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold", className)}>
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />
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
    <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-[var(--text-primary)]">{label}</p>
        <span className="rounded-[var(--radius-2)] bg-[var(--surface-primary)] px-2 py-1 text-xs font-semibold text-[var(--action-primary)]">
          {intelligenceCount} intelligence
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-[var(--radius-2)] bg-[var(--surface-primary)] px-3 py-2">
          <p className="text-[var(--text-tertiary)]">Signals</p>
          <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{signalCount}</p>
        </div>
        <div className="rounded-[var(--radius-2)] bg-[var(--surface-primary)] px-3 py-2">
          <p className="text-[var(--text-tertiary)]">Projects</p>
          <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{projectCount}</p>
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
    rose: "bg-[var(--action-primary)]",
    amber: "bg-[var(--state-warning)]",
    green: "bg-[var(--state-success)]",
    red: "bg-[var(--state-danger)]",
  }[tone];

  return (
    <div className={cn("grid min-w-0 grid-cols-1", size === "compact" ? "gap-1" : "gap-2")}>
      <div className={cn("flex items-center justify-between", size === "compact" ? "text-xs" : "text-sm")}>
        <span className="font-semibold text-[var(--text-secondary)]">{label}</span>
        <span className={size === "compact" ? "text-[var(--text-tertiary)]" : "font-semibold text-[var(--text-primary)]"}>{value}</span>
      </div>
      <div className="h-2 rounded-full bg-[var(--surface-muted)]">
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
    "inline-flex h-11 items-center justify-center gap-2 rounded-[var(--radius-2)] px-4 text-sm font-semibold transition duration-[var(--duration-base)] active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60 motion-reduce:transform-none";
  const toneClass = {
    primary: "bg-[var(--action-primary)] text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] active:bg-[var(--action-primary-pressed)]",
    secondary: "bg-[var(--action-secondary)] text-[var(--text-inverse)] hover:opacity-90",
    danger: "bg-[var(--state-danger)] text-[var(--text-inverse)] hover:opacity-90",
    success: "bg-[var(--state-success)] text-[var(--text-inverse)] hover:opacity-90",
    outline: "border border-[var(--border-strong)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--action-primary)] hover:text-[var(--action-primary)]",
    muted: "border border-[var(--border-subtle)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:border-[var(--border-strong)]",
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
    preview: "border-[var(--border-subtle)] bg-[var(--accent-2-soft)] text-[var(--state-info)]",
    write: "border-[var(--border-subtle)] bg-[var(--warning-soft)] text-[var(--state-warning)]",
    send: "border-[var(--border-subtle)] bg-[var(--success-soft)] text-[var(--state-success)]",
    export: "border-[var(--border-subtle)] bg-[var(--surface-secondary)] text-[var(--text-secondary)]",
    schedule: "border-[var(--border-subtle)] bg-[var(--surface-muted)] text-[var(--text-secondary)]",
  }[tone];

  return (
    <div aria-label={title} className={cn("grid gap-3 rounded-[var(--radius-2)] border p-3", toneClass)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-2)] bg-[var(--surface-primary)]">
              <Icon size={16} aria-hidden="true" />
            </span>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
          </div>
          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{description}</p>
        </div>
        <div className="grid gap-1 text-xs font-semibold leading-5 text-[var(--text-secondary)] sm:max-w-xs">
          {boundary.map((item) => (
            <span className="rounded-[var(--radius-2)] bg-[var(--surface-primary)] px-2.5 py-1" key={item}>
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
      <p className="rounded-[var(--radius-2)] border border-dashed border-[var(--border-strong)] bg-[var(--surface-secondary)] px-3 py-3 text-sm leading-6 text-[var(--text-secondary)]">
        {text}
      </p>
    );
  }

  return (
    <section className="rounded-[var(--radius-3)] border border-dashed border-[var(--border-strong)] bg-[var(--surface-primary)] p-8">
      <div className="mx-auto max-w-2xl text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[var(--accent-1-soft)] text-[var(--action-primary)]">
          {Icon ? <Icon size={22} aria-hidden="true" /> : null}
        </span>
        {title ? <h2 className="mt-4 text-lg font-semibold text-[var(--text-primary)]">{title}</h2> : null}
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{text}</p>
      </div>
    </section>
  );
}
