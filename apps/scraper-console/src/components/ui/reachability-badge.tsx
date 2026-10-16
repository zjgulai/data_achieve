"use client";

import { createContext, useContext } from "react";
import Link from "next/link";
import { Ban, CircleSlash, CloudOff, KeyRound, ShieldAlert } from "lucide-react";
import {
  resolveReachability,
  stateColor,
  type Blocker,
  type Reachability,
  type ReachabilityInput,
  type ReachabilityState,
} from "@/lib/reachability";

/** 状态徽标的图标。 */
function StateIcon({ state }: { state: ReachabilityState }) {
  const size = 11;
  switch (state) {
    case "available":
      return null;
    case "env_gated":
      return <CloudOff size={size} />;
    case "config_gated":
      return <KeyRound size={size} />;
    case "permanently_blocked":
      return <Ban size={size} />;
    case "disabled":
      return <CircleSlash size={size} />;
    default:
      return <ShieldAlert size={size} />;
  }
}

/** 状态徽标的配色。只用语义 token。 */
function stateStyle(state: ReachabilityState): string {
  switch (state) {
    case "available":
      return "border-[var(--state-success)] bg-[var(--success-soft)] text-[var(--state-success)]";
    case "env_gated":
      return "border-[var(--state-warning)] bg-[var(--warning-soft)] text-[var(--state-warning)]";
    case "config_gated":
      return "border-[var(--state-info)] bg-[var(--surface-muted)] text-[var(--state-info)]";
    case "permanently_blocked":
      return "border-[var(--border-strong)] bg-[var(--surface-muted)] text-[var(--text-tertiary)]";
    case "disabled":
      return "border-[var(--border-subtle)] bg-[var(--surface-muted)] text-[var(--text-tertiary)]";
    default:
      return "border-[var(--border-subtle)] bg-[var(--surface-muted)] text-[var(--text-tertiary)]";
  }
}

/** 一行原因。标题 + 原文 + 处置建议。 */
export function BlockerNote({ blocker }: { readonly blocker: Blocker }) {
  // 原因类型取 Blocker["kind"]。与状态枚举不同。
  const tone =
    blocker.kind === "permanent" || blocker.kind === "catalog"
      ? "text-[var(--text-tertiary)]"
      : blocker.kind === "configuration"
        ? "text-[var(--state-info)]"
        : "text-[var(--state-warning)]";
  return (
    <div className="mt-1 text-xs">
      <p className={`font-semibold ${tone}`}>{blocker.title}</p>
      <p className="mt-0.5 text-[var(--text-tertiary)]">{blocker.detail}</p>
      {blocker.action && blocker.action !== blocker.detail && (
        <p className="mt-0.5 text-[var(--text-tertiary)]">{blocker.action}</p>
      )}
    </div>
  );
}

/**
 * 一行原因，附凭证页入口。
 *
 * 仅缺配置状态显示入口。永久不可达不显示。
 */
export function BlockerList({ reachability }: { readonly reachability: Reachability }) {
  // 只在缺配置为主状态时给凭证入口。
  // 永久不可达不得提示补密钥。补了也不放行。
  const hasConfigBlocker = reachability.state === "config_gated";
  return (
    <div className="mt-1 grid gap-1">
      {reachability.blockers.map((b, i) => (
        <div key={`${b.kind}-${i}`}>
          <BlockerNote blocker={b} />
        </div>
      ))}
      {hasConfigBlocker && (
        <Link
          href="/settings/credentials"
          className="mt-0.5 inline-block text-xs text-[var(--action-primary)] underline"
        >
          前往凭证设置
        </Link>
      )}
    </div>
  );
}

/**
 * 状态徽标。
 *
 * `input` 由调用方从后端字段组装。
 * 见 `src/lib/reachability.ts` 的字段来源说明。
 */
export function ReachabilityBadge({
  input,
  className = "",
}: {
  readonly input: ReachabilityInput;
  readonly className?: string;
}) {
  const r = resolveReachability(input);
  // 可执行状态不显示徽标。避免噪声。
  if (r.state === "available") return null;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${stateStyle(r.state)} ${className}`}
      title={r.blockers.map(b => b.detail).join("；")}
    >
      <StateIcon state={r.state} />
      {r.label}
    </span>
  );
}

/** 状态圆点。用于紧凑列表。 */
export function ReachabilityDot({ input }: { readonly input: ReachabilityInput }) {
  const r = resolveReachability(input);
  return (
    <span
      className="inline-block shrink-0 rounded-full"
      style={{ width: 6, height: 6, background: stateColor(r.state) }}
      title={r.label}
      aria-label={r.label}
    />
  );
}

/** 由输入求可达性。供调用方复用同一份判定。 */
export { resolveReachability };
export type { ReachabilityInput, ReachabilityState };

/**
 * 端点级的可用性来源。
 *
 * 键是 endpoint_type。值来自 GET /api/platform-packages/providers/status。
 * 用 context 传，避免逐层加 props。
 */
export type AvailabilityLookup = (endpointType: string) => {
  availability?: string | null;
  missing_configuration?: readonly string[] | null;
  policy_block_reason?: string | null;
} | null;

const AvailabilityContext = createContext<AvailabilityLookup>(() => null);

export function ReachabilityProvider({
  lookup,
  children,
}: {
  readonly lookup: AvailabilityLookup;
  readonly children: React.ReactNode;
}) {
  return (
    <AvailabilityContext.Provider value={lookup}>{children}</AvailabilityContext.Provider>
  );
}

/** 取当前端点的可用性。无 provider 时返回 null。 */
export function useAvailability(endpointType: string) {
  const lookup = useContext(AvailabilityContext);
  return lookup(endpointType);
}
