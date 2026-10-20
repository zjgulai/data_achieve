"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import {
  activateWorkspace,
  addWorkspaceMember,
  fetchAuthSession,
  fetchWorkspaceMembers,
  fetchWorkspaces,
  logout,
  removeWorkspaceMember,
} from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { Loader2, LogOut, RefreshCw, UserMinus, Users } from "lucide-react";

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

function noRetryOn401(failureCount: number, err: unknown): boolean {
  if (err instanceof ApiError && err.status === 401) return false;
  return failureCount < 3;
}

export default function MembersPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  const session = useQuery({
    queryKey: ["auth-session"],
    queryFn: fetchAuthSession,
    retry: noRetryOn401,
  });

  const workspaces = useQuery({
    queryKey: ["workspaces"],
    queryFn: fetchWorkspaces,
    enabled: session.isSuccess,
    retry: noRetryOn401,
  });

  const members = useQuery({
    queryKey: ["workspace-members"],
    queryFn: fetchWorkspaceMembers,
    enabled: session.isSuccess,
    retry: noRetryOn401,
  });

  const activate = useMutation({
    mutationFn: activateWorkspace,
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      router.refresh();
    },
    onError: (err) => setActionError(`切换失败：${(err as Error).message}`),
  });

  const addMember = useMutation({
    mutationFn: addWorkspaceMember,
    onSuccess: async () => {
      setEmail("");
      await queryClient.invalidateQueries({ queryKey: ["workspace-members"] });
    },
    onError: (err) => setActionError(`添加失败：${(err as Error).message}`),
  });

  const removeMember = useMutation({
    mutationFn: removeWorkspaceMember,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["workspace-members"] });
    },
    onError: (err) => setActionError(`移除失败：${(err as Error).message}`),
  });

  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.clear();
      router.replace("/login");
    },
  });

  const unauthorized = session.error instanceof ApiError && session.error.status === 401;
  const data = session.data;
  const isOwner = Boolean(data && data.workspace.owner_id === data.user.id);
  const busy = activate.isPending || addMember.isPending || removeMember.isPending;

  function onAddMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionError(null);
    if (!email.trim()) return;
    addMember.mutate(email.trim());
  }

  return (
    <AppShell
      title="成员与工作区"
      description="切换工作区，管理成员"
      breadcrumbs={[{ label: "设置" }, { label: "成员与工作区" }]}
    >
      <div className="mb-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-4 py-3 text-xs text-[var(--text-tertiary)]">
        每个用户有自己的工作区。项目、任务、资产都按工作区隔离。
        切换后，控制台显示所选工作区的数据。
      </div>

      {session.isLoading ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
          <Loader2 size={24} className="mx-auto animate-spin text-[var(--text-tertiary)]" />
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">加载中...</p>
        </div>
      ) : unauthorized ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
          <Users size={32} className="mx-auto text-[var(--text-tertiary)]" />
          <p className="mt-3 text-sm text-[var(--text-secondary)]">尚未登录</p>
          <button
            type="button"
            onClick={() => router.replace("/login")}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[var(--action-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--text-inverse)]"
          >
            去登录
          </button>
        </div>
      ) : session.error ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-8 text-center">
          <p className="text-sm text-[var(--state-danger)]">
            加载失败：{(session.error as Error).message}
          </p>
          <button
            type="button"
            onClick={() => session.refetch()}
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
        <div className="grid gap-4">
          {actionError && (
            <p role="alert" className="rounded-lg bg-[var(--danger-soft)] px-4 py-3 text-xs text-[var(--state-danger)]">
              {actionError}
            </p>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-sm font-semibold text-[var(--text-primary)]">当前用户</h2>
                <button
                  type="button"
                  onClick={() => signOut.mutate()}
                  disabled={signOut.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-60"
                >
                  <LogOut size={13} />
                  退出登录
                </button>
              </div>
              <dl className="mt-4 grid gap-3 text-sm">
                <Field label="名称" value={data.user.name} />
                <Field label="邮箱" value={data.user.email} />
                <Field label="状态" value={data.user.status} />
                <Field label="创建时间" value={formatTime(data.user.created_at)} />
              </dl>
            </section>

            <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">我的工作区</h2>
              {workspaces.isLoading ? (
                <p className="mt-4 text-xs text-[var(--text-tertiary)]">加载中...</p>
              ) : workspaces.error ? (
                <p className="mt-4 text-xs text-[var(--state-danger)]">
                  加载失败：{(workspaces.error as Error).message}
                </p>
              ) : (
                <ul className="mt-3 grid gap-2">
                  {(workspaces.data ?? []).map((workspace) => {
                    const active = workspace.id === data.workspace.id;
                    return (
                      <li
                        key={workspace.id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border-subtle)] px-3 py-2"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                            {workspace.name}
                          </p>
                          <p className="truncate text-xs text-[var(--text-tertiary)]">
                            {workspace.slug} · {workspace.role === "owner" ? "所有者" : "成员"}
                          </p>
                        </div>
                        {active ? (
                          <span className="shrink-0 rounded-full bg-[var(--accent-1-soft)] px-2 py-0.5 text-xs font-medium text-[var(--action-primary)]">
                            当前
                          </span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              setActionError(null);
                              activate.mutate(workspace.id);
                            }}
                            disabled={busy}
                            className="shrink-0 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-60"
                          >
                            切换
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </div>

          <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              当前工作区成员
              <span className="ml-2 text-xs font-normal text-[var(--text-tertiary)]">
                {data.workspace.name}
              </span>
            </h2>

            {members.isLoading ? (
              <p className="mt-4 text-xs text-[var(--text-tertiary)]">加载中...</p>
            ) : members.error ? (
              <p className="mt-4 text-xs text-[var(--state-danger)]">
                加载失败：{(members.error as Error).message}
              </p>
            ) : (
              <ul className="mt-3 grid gap-2">
                {(members.data ?? []).map((member) => (
                  <li
                    key={member.user.id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border-subtle)] px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                        {member.user.name}
                        {member.user.id === data.user.id && (
                          <span className="ml-2 text-xs font-normal text-[var(--text-tertiary)]">你</span>
                        )}
                      </p>
                      <p className="truncate text-xs text-[var(--text-tertiary)]">{member.user.email}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="rounded-full border border-[var(--border-subtle)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
                        {member.role === "owner" ? "所有者" : "成员"}
                      </span>
                      {isOwner && member.role !== "owner" && (
                        <button
                          type="button"
                          onClick={() => {
                            setActionError(null);
                            removeMember.mutate(member.user.id);
                          }}
                          disabled={busy}
                          className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2 py-1 text-xs font-medium text-[var(--state-danger)] hover:bg-[var(--danger-soft)] disabled:opacity-60"
                        >
                          <UserMinus size={13} />
                          移除
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {isOwner && (
              <form onSubmit={onAddMember} className="mt-4 flex flex-wrap items-end gap-2">
                <div className="min-w-0 flex-1">
                  <label className="block text-xs font-medium text-[var(--text-secondary)]" htmlFor="member-email">
                    添加成员
                  </label>
                  <input
                    id="member-email"
                    type="email"
                    required
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="成员邮箱"
                    className="mt-1.5 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm outline-none focus:border-[var(--action-primary)]"
                  />
                </div>
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-lg bg-[var(--action-primary)] px-3 py-2 text-xs font-semibold text-[var(--text-inverse)] disabled:opacity-60"
                >
                  {addMember.isPending ? "添加中..." : "添加"}
                </button>
              </form>
            )}
            {!isOwner && (
              <p className="mt-4 text-xs text-[var(--text-tertiary)]">
                只有工作区所有者可以添加或移除成员。
              </p>
            )}
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
