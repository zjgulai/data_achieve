"use client";

import React, { useEffect, useMemo, useState } from "react";
import { LockKeyhole, ShieldCheck } from "lucide-react";

import {
  getPlatformCredentialSettings,
  removePlatformCredentials,
  updatePlatformCredentials,
  type PlatformCredentialSettings,
  type PlatformCredentialSettingsResponse,
} from "@/lib/api/platform-credentials";

function readableError(error: unknown): string {
  if (!(error instanceof Error)) {
    return "凭证设置服务暂时不可用。";
  }
  if (error.message.includes("platform_credential_vault_unavailable")) {
    return "服务端尚未配置凭证 vault 主密钥，当前不能写入。";
  }
  if (error.message.includes("platform_credential_forbidden")) {
    return "只有当前 Workspace Owner 可以管理平台凭证。";
  }
  return "平台凭证操作失败；已保留当前页面状态，未触发 Provider 调用。";
}

export function PlatformCredentialsWorkspace() {
  const [settings, setSettings] =
    useState<PlatformCredentialSettingsResponse | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void getPlatformCredentialSettings()
      .then((result) => {
        if (!active) return;
        setSettings(result);
        setSelectedPlatform(
          (current) => current ?? result.platforms[0]?.platform ?? null,
        );
      })
      .catch((reason: unknown) => {
        if (active) setError(readableError(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const selected = useMemo(
    () =>
      settings?.platforms.find((item) => item.platform === selectedPlatform) ??
      null,
    [selectedPlatform, settings],
  );
  const configuredCount =
    settings?.platforms.filter((item) => item.configured).length ?? 0;
  const pendingValues = Object.fromEntries(
    Object.entries(draft).filter(([, value]) => value.length > 0),
  );
  const canSave =
    Boolean(settings?.vaultWriteEnabled) &&
    Object.keys(pendingValues).length > 0 &&
    !saving;

  function selectPlatform(platform: string): void {
    setSelectedPlatform(platform);
    setDraft({});
    setConfirmRemove(false);
    setMessage(null);
    setError(null);
  }

  function replacePlatform(updated: PlatformCredentialSettings): void {
    setSettings((current) =>
      current
        ? {
            ...current,
            platforms: current.platforms.map((item) =>
              item.platform === updated.platform ? updated : item,
            ),
          }
        : current,
    );
  }

  async function save(): Promise<void> {
    if (!selected || !canSave) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await updatePlatformCredentials(
        selected.platform,
        pendingValues,
      );
      replacePlatform(updated);
      setDraft({});
      setMessage(
        `${updated.label} 凭证已加密保存；未执行连接测试或 Provider 调用。`,
      );
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setSaving(false);
    }
  }

  async function remove(): Promise<void> {
    if (!selected || !confirmRemove || removing) return;
    setRemoving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await removePlatformCredentials(selected.platform);
      replacePlatform(updated);
      setDraft({});
      setConfirmRemove(false);
      setMessage(`${updated.label} 凭证已移除；未触发 Provider 调用。`);
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setRemoving(false);
    }
  }

  if (loading) {
    return (
      <section
        aria-busy="true"
        className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6"
      >
        <p className="text-sm text-[var(--text-secondary)]">
          正在读取平台凭证状态…
        </p>
      </section>
    );
  }

  if (!settings || !selected) {
    return (
      <section
        className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6"
        role="alert"
      >
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          平台凭证不可用
        </h2>
        <p className="mt-2 text-sm text-[var(--state-danger)]">
          {error ?? "未读取到平台凭证目录。"}
        </p>
      </section>
    );
  }

  return (
    <div
      className="min-w-0 space-y-5"
      data-testid="platform-credentials-workspace"
    >
      <section className="rounded-[var(--radius-4)] border border-[var(--border-strong)] bg-[var(--surface-secondary)] p-5 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2 text-[var(--state-info)]">
              <ShieldCheck aria-hidden="true" size={18} />
              <p className="text-sm font-semibold">配置不等于授权调用</p>
            </div>
            <h2 className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">
              平台凭证
            </h2>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              Secret 只在本次提交中进入服务端加密
              vault；页面不会回显、下载或写入浏览器存储。
              保存不会执行连接测试、创建客户端或调用平台 API。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2">
              <p className="text-xs text-[var(--text-tertiary)]">完整配置</p>
              <p className="mt-1 font-semibold text-[var(--text-primary)]">
                {configuredCount} / {settings.platforms.length}
              </p>
            </div>
            <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2">
              <p className="text-xs text-[var(--text-tertiary)]">Vault 写入</p>
              <p className="mt-1 font-semibold text-[var(--text-primary)]">
                {settings.vaultWriteEnabled ? "已启用" : "未启用"}
              </p>
            </div>
          </div>
        </div>
      </section>

      {!settings.vaultWriteEnabled ? (
        <p
          className="rounded-[var(--radius-3)] border border-[var(--warning-1)] bg-[var(--warning-soft)] px-4 py-3 text-sm text-[var(--state-warning)]"
          role="status"
        >
          服务端尚未配置 vault 主密钥。可审阅各平台所需字段，但保存保持禁用。
        </p>
      ) : null}

      <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(15rem,0.72fr)_minmax(0,1.28fr)]">
        <nav
          aria-label="平台凭证目录"
          className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-2"
        >
          {settings.platforms.map((platform) => {
            const active = platform.platform === selected.platform;
            return (
              <button
                aria-current={active ? "page" : undefined}
                className={`mb-1 flex min-h-[var(--touch-target)] w-full min-w-0 items-center justify-between gap-3 rounded-[var(--radius-2)] px-3 py-2 text-left transition-colors focus:outline-none focus:shadow-[var(--focus-ring)] ${
                  active
                    ? "bg-[var(--surface-muted)] text-[var(--text-primary)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-secondary)]"
                }`}
                data-testid={`platform-credential-row-${platform.platform}`}
                key={platform.platform}
                onClick={() => selectPlatform(platform.platform)}
                type="button"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold">
                    {platform.label}
                  </span>
                  <span className="mt-0.5 block text-xs text-[var(--text-tertiary)]">
                    {platform.configuredFieldCount}/{platform.fields.length} 项
                  </span>
                </span>
                <span
                  className={`shrink-0 rounded-[var(--radius-pill)] px-2 py-1 text-xs font-semibold ${
                    platform.configured
                      ? "bg-[var(--success-soft)] text-[var(--state-success)]"
                      : platform.configuredFieldCount > 0
                        ? "bg-[var(--warning-soft)] text-[var(--state-warning)]"
                        : "bg-[var(--surface-secondary)] text-[var(--text-tertiary)]"
                  }`}
                >
                  {platform.configured
                    ? "已配置"
                    : platform.configuredFieldCount > 0
                      ? "部分配置"
                      : "未配置"}
                </span>
              </button>
            );
          })}
        </nav>

        <section className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5 sm:p-6">
          <div className="flex flex-col gap-3 border-b border-[var(--border-subtle)] pb-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-semibold text-[var(--state-info)]">
                Workspace 级凭证
              </p>
              <h3 className="mt-1 text-xl font-semibold text-[var(--text-primary)]">
                {selected.label}
              </h3>
              <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                {selected.authMode}
              </p>
            </div>
            <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <LockKeyhole aria-hidden="true" size={17} />
              <span>已有值不可读取</span>
            </div>
          </div>

          <form
            className="mt-5 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            {selected.fields.map((field) => {
              const inputId = `platform-credential-${selected.platform}-${field.key}`;
              return (
                <div key={field.key}>
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <label
                      className="text-sm font-semibold text-[var(--text-primary)]"
                      htmlFor={inputId}
                    >
                      {field.label}
                    </label>
                    <span className="text-xs text-[var(--text-tertiary)]">
                      {field.configured ? "已保存加密值" : "尚未配置"}
                    </span>
                  </div>
                  <input
                    autoComplete="new-password"
                    className="min-h-[var(--touch-target)] w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--focus-1)] focus:shadow-[var(--focus-ring)]"
                    id={inputId}
                    maxLength={8192}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        [field.key]: event.target.value,
                      }))
                    }
                    placeholder={
                      field.configured
                        ? "输入新值以替换；留空保持不变"
                        : "输入后单向提交到 vault"
                    }
                    type="password"
                    value={draft[field.key] ?? ""}
                  />
                </div>
              );
            })}

            {message ? (
              <p
                aria-live="polite"
                className="text-sm font-semibold text-[var(--state-success)]"
              >
                {message}
              </p>
            ) : null}
            {error ? (
              <p
                className="text-sm font-semibold text-[var(--state-danger)]"
                role="alert"
              >
                {error}
              </p>
            ) : null}

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-subtle)] pt-4">
              <button
                className="min-h-[var(--touch-target)] rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] focus:outline-none focus:shadow-[var(--focus-ring)] disabled:cursor-not-allowed disabled:bg-[var(--border-strong)]"
                disabled={!canSave}
                type="submit"
              >
                {saving ? "正在加密保存…" : "保存凭证"}
              </button>

              {selected.configuredFieldCount > 0 ? (
                confirmRemove ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm text-[var(--state-danger)]">
                      确认移除该平台全部凭证？
                    </span>
                    <button
                      className="min-h-[var(--touch-target)] rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2 text-sm font-semibold text-[var(--text-secondary)]"
                      onClick={() => setConfirmRemove(false)}
                      type="button"
                    >
                      取消
                    </button>
                    <button
                      className="min-h-[var(--touch-target)] rounded-[var(--radius-2)] border border-[var(--state-danger)] px-3 py-2 text-sm font-semibold text-[var(--state-danger)] disabled:opacity-50"
                      disabled={removing}
                      onClick={() => void remove()}
                      type="button"
                    >
                      {removing ? "正在移除…" : "确认移除"}
                    </button>
                  </div>
                ) : (
                  <button
                    className="min-h-[var(--touch-target)] rounded-[var(--radius-2)] px-3 py-2 text-sm font-semibold text-[var(--state-danger)] focus:outline-none focus:shadow-[var(--focus-ring)]"
                    onClick={() => setConfirmRemove(true)}
                    type="button"
                  >
                    移除凭证
                  </button>
                )
              ) : null}
            </div>
          </form>

          <details className="mt-5 border-t border-[var(--border-subtle)] pt-4">
            <summary className="cursor-pointer text-sm font-semibold text-[var(--text-secondary)]">
              Advanced diagnostics
            </summary>
            <dl className="mt-3 grid gap-2 text-xs text-[var(--text-tertiary)] sm:grid-cols-2">
              <div>
                <dt>Provider ID</dt>
                <dd className="mt-1 break-all font-mono text-[var(--text-primary)]">
                  {selected.providerId}
                </dd>
              </div>
              <div>
                <dt>Live execution</dt>
                <dd className="mt-1 font-mono text-[var(--text-primary)]">
                  disabled
                </dd>
              </div>
            </dl>
          </details>
        </section>
      </div>
    </div>
  );
}
