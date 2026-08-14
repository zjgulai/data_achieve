"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import {
  fetchCredentials,
  updateCredential,
  deleteCredential,
} from "@/lib/api/credentials";
import type { PlatformCredential, CredentialField } from "@/lib/api/credentials";
import { Key, CheckCircle, AlertCircle, Trash2, Loader2, Eye, EyeOff } from "lucide-react";
import { ApiError } from "@/lib/api/client";

/* ── Platform icons ── */
const PLATFORM_EMOJI: Record<string, string> = {
  youtube:   "▶",
  reddit:    "🔴",
  x:         "✕",
  instagram: "📸",
  threads:   "🧵",
  tiktok:    "🎵",
  linkedin:  "💼",
};

/* ── Field input with show/hide toggle ── */
function SecretInput({
  fieldKey,
  label,
  configured,
  value,
  onChange,
}: {
  fieldKey: string;
  label: string;
  configured: boolean;
  value: string;
  onChange: (v: string) => void;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="grid gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-[var(--text-primary)]">
          {label}
        </label>
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
          className="h-10 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 pr-9 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
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
      if (Object.keys(payload).length === 0)
        throw new Error("请至少填写一个字段");
      return updateCredential(platform.platform, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["credentials"] });
      setExpanded(false);
      setValues(Object.fromEntries(platform.fields.map((f) => [f.key, ""])));
      setError(null);
    },
    onError: (e) => {
      setError(e instanceof ApiError ? e.message : String(e));
    },
  });

  const remove = useMutation({
    mutationFn: () => deleteCredential(platform.platform),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["credentials"] }),
  });

  const icon = PLATFORM_EMOJI[platform.platform] ?? "🔑";

  return (
    <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="text-xl">{icon}</span>
          <div>
            <p className="text-sm font-semibold text-[var(--text-primary)]">
              {platform.label}
            </p>
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
              title="删除凭证"
              className="rounded-[var(--radius-2)] p-2 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--danger-soft)] hover:text-[var(--state-danger)] disabled:opacity-40"
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
            className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)] disabled:opacity-40"
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
                fieldKey={f.key}
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
              className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            >
              取消
            </button>
            <button
              type="button"
              disabled={save.isPending}
              onClick={() => save.mutate()}
              className="flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] disabled:opacity-60"
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
      {!data?.vault_write_enabled && !isLoading && (
        <div className="rounded-[var(--radius-2)] border border-[var(--state-warning)] bg-[var(--warning-soft)] px-4 py-3 text-sm text-[var(--state-warning)]">
          <p className="font-medium">凭证保险库未启用</p>
          <p className="mt-1 text-xs">
            需要在服务器设置 <code className="font-mono">PLATFORM_CREDENTIAL_MASTER_KEY</code> 环境变量并重启 API 服务
          </p>
        </div>
      )}

      {data && (
        <p className="text-sm text-[var(--text-tertiary)]">
          {configuredCount}/{data.platforms.length} 个平台已配置凭证
        </p>
      )}

      {isLoading ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
          <Loader2 size={24} className="mx-auto animate-spin text-[var(--text-tertiary)]" />
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">加载中...</p>
        </div>
      ) : error ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-8 text-center">
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

      <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3 text-xs text-[var(--text-tertiary)]">
        凭证经 Fernet 加密存储，API 不返回明文。TikHub 和 Apify 的密钥在 API 容器环境变量中配置（TIKHUB_API_KEY / APIFY_API_TOKEN），不在此处管理。
      </div>
    </AppShell>
  );
}
