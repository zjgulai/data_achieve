"use client";

import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Grid3x3, Loader2 } from "lucide-react";
import { login } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login({ email, password });
      const target = nextPath.startsWith("/") ? nextPath : "/dashboard";
      router.replace(target);
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("邮箱或密码不正确。");
      } else {
        setError(`登录失败：${err instanceof Error ? err.message : "未知错误"}`);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--surface-canvas)] px-4 py-10 text-[var(--text-primary)]">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-3)] bg-[var(--action-primary)] text-[var(--text-inverse)]">
            <Grid3x3 size={20} aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-bold">采集控制台</p>
            <p className="text-xs text-[var(--text-tertiary)]">Data Intelligence Hub</p>
          </div>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6"
        >
          <h1 className="text-lg font-semibold">登录</h1>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">
            使用工作区账号邮箱与密码登录。
          </p>

          <label className="mt-5 block text-xs font-medium text-[var(--text-secondary)]" htmlFor="email">
            邮箱
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-1.5 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm outline-none focus:border-[var(--action-primary)]"
          />

          <label className="mt-4 block text-xs font-medium text-[var(--text-secondary)]" htmlFor="password">
            密码
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1.5 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2 text-sm outline-none focus:border-[var(--action-primary)]"
          />

          {error && (
            <p role="alert" className="mt-4 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-xs text-[var(--state-danger)]">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--action-primary)] px-3 py-2.5 text-sm font-semibold text-[var(--text-inverse)] disabled:opacity-60"
          >
            {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
            {submitting ? "登录中..." : "登录"}
          </button>
        </form>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
