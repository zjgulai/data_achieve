"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import {
  fetchCredentials,
  updateCredential,
  deleteCredential,
} from "@/lib/api/credentials";
import type { PlatformCredential } from "@/lib/api/credentials";
import { Key, CheckCircle, AlertCircle, Trash2, Loader2, Eye, EyeOff } from "lucide-react";
import { ApiError } from "@/lib/api/client";

/* ── Platform badge (matches platforms/page.tsx PlatformLogo) ── */
const PLATFORM_BADGE: Record<string, { bg: string; fg: string; letter: string }> = {
  tikhub:    { bg: "#010101", fg: "#fff", letter: "TH"  },
  apify:     { bg: "#FF7300", fg: "#fff", letter: "Ap"  },
  anysearch: { bg: "#2563EB", fg: "#fff", letter: "AS"  },
  jina:      { bg: "#9333EA", fg: "#fff", letter: "Ji"  },
  github:    { bg: "#24292F", fg: "#fff", letter: "GH"  },
  youtube:   { bg: "#FF0000", fg: "#fff", letter: "YT"  },
  reddit:    { bg: "#FF4500", fg: "#fff", letter: "Re"  },
  x:         { bg: "#000000", fg: "#fff", letter: "𝕏"   },
  instagram: { bg: "#E1306C", fg: "#fff", letter: "In"  },
  threads:   { bg: "#101010", fg: "#fff", letter: "Th"  },
  tiktok:    { bg: "#010101", fg: "#fff", letter: "TK"  },
  linkedin:  { bg: "#0A66C2", fg: "#fff", letter: "in"  },
};

function PlatformBadge({ platform }: { platform: string }) {
  const meta = PLATFORM_BADGE[platform.toLowerCase()]
    ?? { bg: "#6B7280", fg: "#fff", letter: platform.slice(0, 2).toUpperCase() };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 36,
        height: 36,
        borderRadius: 8,
        background: meta.bg,
        color: meta.fg,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: "-0.03em",
        flexShrink: 0,
      }}
    >
      {meta.letter}
    </span>
  );
}

/* ── Field input ── */
function SecretInput({
  label,
  configured,
  value,
  onChange,
}: {
  label: string;
  configured: boolean;
  value: string;
  onChange: (v: string) => void;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="grid gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-[var(--text-primary)]">{label}</label>
        {configured && (
          <span className="flex items-center gap-1 text-xs text-[var(--state-success)]">
            <CheckCircle size={12} />
            已配置
          </span>
        )}
      </div>
      <div className="relative">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={configured ? "输入新值以更新" : `输入 ${label}`}
          autoComplete="off"
          className="h-10 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 pr-9 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
        >
          {show ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
    </div>
  );
}

/* ── Platform card ── */
function PlatformCard({
  platform,
  vaultEnabled,
}: {
  platform: PlatformCredential;
  vaultEnabled: boolean;
}) {
  const qc = useQueryClient();
  const [values, setValues] = useState<Record<string, string>>(
    () => Object.fromEntries(platform.fields.map((f) => [f.key, ""]))
  );
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, string> = {};
      for (const [k, v] of Object.entries(values)) {
        if (v.trim()) payload[k] = v.trim();
      }
      if (Object.keys(payload).length === 0) throw new Error("请至少填写一个字段");
      return updateCredential(platform.platform, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["credentials"] });
      setExpanded(false);
      setValues(Object.fromEntries(platform.fields.map((f) => [f.key, ""])));
      setError(null);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : String(e)),
  });

  const remove = useMutation({
    mutationFn: () => deleteCredential(platform.platform),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["credentials"] }),
  });

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-3">
          <PlatformBadge platform={platform.platform} />
          <div>
            <p className="text-sm font-semibold text-[var(--text-primary)]">{platform.label}</p>
            <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
              {platform.auth_mode}
              {platform.configured && (
                <span className="ml-2 text-[var(--state-success)]">
                  {platform.configured_field_count} 个字段已配置
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {platform.configured && (
            <button
              type="button"
              disabled={remove.isPending || !vaultEnabled}
              onClick={() => remove.mutate()}
              className="rounded-lg p-2 text-[var(--text-tertiary)] hover:bg-[var(--danger-soft)] hover:text-[var(--state-danger)] disabled:opacity-40 transition-colors"
            >
              {remove.isPending
                ? <Loader2 size={14} className="animate-spin" />
                : <Trash2 size={14} />}
            </button>
          )}
          <button
            type="button"
            disabled={!vaultEnabled}
            onClick={() => setExpanded(!expanded)}
            className="rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-40 transition-colors"
          >
            {platform.configured ? "更新" : "配置"}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-[var(--border-subtle)] px-5 pb-5 pt-4">
          <div className="grid gap-4">
            {platform.fields.map((f) => (
              <SecretInput
                key={f.key}
                label={f.label}
                configured={f.configured}
                value={values[f.key] ?? ""}
                onChange={(v) => setValues((prev) => ({ ...prev, [f.key]: v }))}
              />
            ))}
          </div>

          {error && (
            <div className="mt-3 flex items-center gap-2 text-sm text-[var(--state-danger)]">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => { setExpanded(false); setError(null); }}
              className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            >
              取消
            </button>
            <button
              type="button"
              disabled={save.isPending}
              onClick={() => save.mutate()}
              className="flex items-center gap-1.5 rounded-lg bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] disabled:opacity-60"
            >
              {save.isPending ? <Loader2 size={14} className="animate-spin" /> : <Key size={14} />}
              保存
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Page ── */
export default function CredentialsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["credentials"],
    queryFn: fetchCredentials,
  });

  const configuredCount = data?.platforms.filter((p) => p.configured).length ?? 0;

  return (
    <AppShell
      title="凭证管理"
      description="配置各平台 API Key 用于采集"
    >
      {data && !data.vault_write_enabled && (
        <div className="rounded-lg border border-[var(--state-warning)] bg-[var(--warning-soft)] px-4 py-3 text-sm text-[var(--state-warning)]">
          <p className="font-medium">凭证保险库未启用</p>
          <p className="mt-1 text-xs">
            需要在服务器设置{" "}
            <code className="font-mono">PLATFORM_CREDENTIAL_MASTER_KEY</code>{" "}
            环境变量并重启 API 服务
          </p>
        </div>
      )}

      <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-4 py-3 text-xs text-[var(--text-tertiary)]">
        TikHub / Apify / AnySearch / Jina Reader 的密钥在生产服务器
        <code className="mx-1 font-mono">.env.production</code>
        中通过环境变量配置，不在此界面管理。此处管理平台级 OAuth 凭证（YouTube Data API、Reddit OAuth 等）。
      </div>

      {data && (
        <p className="text-sm text-[var(--text-tertiary)]">
          {configuredCount}/{data.platforms.length} 个平台已配置凭证
        </p>
      )}

      {isLoading ? (
        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
          <Loader2 size={24} className="mx-auto animate-spin text-[var(--text-tertiary)]" />
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">加载中...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-8 text-center">
          <p className="text-sm text-[var(--state-danger)]">
            加载失败：{(error as Error).message}
          </p>
        </div>
      ) : (
        <div className="grid gap-3">
          {data?.platforms.map((p) => (
            <PlatformCard
              key={p.platform}
              platform={p}
              vaultEnabled={data.vault_write_enabled}
            />
          ))}
        </div>
      )}
    </AppShell>
  );
}
