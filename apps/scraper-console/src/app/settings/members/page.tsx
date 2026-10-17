"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchAuthSession } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { Loader2, Users, RefreshCw } from "lucide-react";

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

export default function MembersPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["auth-session"],
    queryFn: fetchAuthSession,
    // 401 是常态，不是故障。只对 401 关闭重试。
    // 其余错误（502、网络中断）仍按默认策略重试。
    retry: (failureCount, err) => {
      if (err instanceof ApiError && err.status === 401) return false;
      return failureCount < 3;
    },
  });

  const unauthorized = error instanceof ApiError && error.status === 401;

  return (
    <AppShell
      title="成员与工作区"
      description="查看当前会话所属的用户与工作区"
      breadcrumbs={[{ label: "设置" }, { label: "成员与工作区" }]}
    >
      <div className="mb-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-4 py-3 text-xs text-[var(--text-tertiary)]">
        后端目前没有成员列表、邀请或角色管理接口。
        本页只显示当前会话所属的一个用户与一个工作区。
        多人协作能力尚未提供。
      </div>

      {isLoading ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
          <Loader2 size={24} className="mx-auto animate-spin text-[var(--text-tertiary)]" />
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">加载中...</p>
        </div>
      ) : unauthorized ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
          <Users size={32} className="mx-auto text-[var(--text-tertiary)]" />
          <p className="mt-3 text-sm text-[var(--text-secondary)]">尚未登录</p>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">
            控制台暂无登录界面。请先通过 API 登录以写入会话 Cookie。
          </p>
        </div>
      ) : error ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-8 text-center">
          <p className="text-sm text-[var(--state-danger)]">
            加载失败：{(error as Error).message}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
          >
            <RefreshCw size={14} />
            重试
          </button>
        </div>
      ) : !data ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
          <p className="text-sm text-[var(--text-tertiary)]">没有会话数据</p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">当前用户</h2>
            <dl className="mt-4 grid gap-3 text-sm">
              <Field label="名称" value={data.user.name} />
              <Field label="邮箱" value={data.user.email} />
              <Field label="状态" value={data.user.status} />
              <Field label="创建时间" value={formatTime(data.user.created_at)} />
            </dl>
          </section>

          <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">当前工作区</h2>
            <dl className="mt-4 grid gap-3 text-sm">
              <Field label="名称" value={data.workspace.name} />
              <Field label="标识" value={data.workspace.slug} />
              <Field
                label="所有者"
                value={
                  data.workspace.owner_id === data.user.id
                    ? "当前用户"
                    : data.workspace.owner_id
                }
              />
              <Field label="创建时间" value={formatTime(data.workspace.created_at)} />
            </dl>
          </section>
        </div>
      )}
    </AppShell>
  );
}

function Field({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="grid gap-1">
      <dt className="text-xs text-[var(--text-tertiary)]">{label}</dt>
      <dd className="break-all text-[var(--text-primary)]">{value}</dd>
    </div>
  );
}
