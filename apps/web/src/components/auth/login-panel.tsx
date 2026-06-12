"use client";

import type { Route } from "next";
import {
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useState } from "react";

import { login, register } from "@/lib/api/auth";
import { cn } from "@/lib/utils";

type Mode = "login" | "register";

export function LoginPanel() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("owner@example.com");
  const [name, setName] = useState("Owner");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "register") {
        await register({ email, name, password });
      } else {
        await login({ email, password });
      }
      router.push(getSafeNextPath(searchParams.get("next")) as Route);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      className="w-full"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <div className="mb-7">
        <p className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-[#FFF8F4] px-3 py-1 text-xs font-semibold uppercase text-[#B47767]">
          <ShieldCheck size={14} aria-hidden="true" />
          Secure Access
        </p>
        <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C]">
          {mode === "login" ? "登录 Workspace" : "创建 Workspace"}
        </h2>
        <p className="mt-2 text-sm leading-6 text-[#7A625A]">
          {mode === "login"
            ? "使用邮箱和密码进入情报工作台。"
            : "新账号会自动创建默认 Workspace。"}
        </p>
      </div>

      <div className="mb-5 grid grid-cols-2 rounded-2xl border border-[#E8D4CB] bg-[#FFF8F4] p-1 text-sm">
        <button
          aria-pressed={mode === "login"}
          className={cn(
            "h-10 rounded-xl px-3 font-semibold transition",
            mode === "login"
              ? "bg-[#C96F5C] text-white shadow-[0_10px_22px_rgba(201,111,92,0.2)]"
              : "text-[#7D4F43] hover:text-[#C96F5C]",
          )}
          onClick={() => {
            setMode("login");
            setError(null);
          }}
          type="button"
        >
          登录
        </button>
        <button
          aria-pressed={mode === "register"}
          className={cn(
            "h-10 rounded-xl px-3 font-semibold transition",
            mode === "register"
              ? "bg-[#C96F5C] text-white shadow-[0_10px_22px_rgba(201,111,92,0.2)]"
              : "text-[#7D4F43] hover:text-[#C96F5C]",
          )}
          onClick={() => {
            setMode("register");
            setError(null);
          }}
          type="button"
        >
          注册
        </button>
      </div>

      <div className="grid gap-4">
        {mode === "register" ? (
          <Field label="名称" htmlFor="auth-name" icon={UserRound}>
            <input
              className="w-full border-0 bg-transparent text-sm text-[#3B2924] outline-none placeholder:text-[#B9A19A]"
              id="auth-name"
              name="name"
              onChange={(event) => setName(event.target.value)}
              placeholder="Owner"
              value={name}
            />
          </Field>
        ) : null}

        <Field label="邮箱" htmlFor="auth-email" icon={Mail}>
          <input
            autoComplete="email"
            className="w-full border-0 bg-transparent text-sm text-[#3B2924] outline-none placeholder:text-[#B9A19A]"
            id="auth-email"
            name="email"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="owner@example.com"
            type="email"
            value={email}
          />
        </Field>

        <Field label="密码" htmlFor="auth-password" icon={LockKeyhole}>
          <input
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            className="w-full border-0 bg-transparent text-sm text-[#3B2924] outline-none placeholder:text-[#B9A19A]"
            id="auth-password"
            name="password"
            onChange={(event) => setPassword(event.target.value)}
            placeholder="输入密码"
            type={passwordVisible ? "text" : "password"}
            value={password}
          />
          <button
            aria-label={passwordVisible ? "Hide password" : "Show password"}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[#9E5C4D] transition hover:bg-[#FFF1EB]"
            onClick={() => setPasswordVisible((current) => !current)}
            type="button"
          >
            {passwordVisible ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
          </button>
        </Field>
      </div>

      {error ? (
        <p className="mt-4 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
          {error}
        </p>
      ) : null}

      <div className="mt-5 rounded-2xl border border-[#F0E1D9] bg-[#FFFDFC] p-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#ECF7EA] text-[#4E7C45]">
            <CheckCircle2 size={16} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[#2E201C]">
              {mode === "login" ? "Demo session ready" : "Default workspace will be created"}
            </p>
            <p className="mt-1 text-xs leading-5 text-[#7A625A]">
              {mode === "login"
                ? "使用部署时配置的演示账号，或切换到注册创建新 Workspace。"
                : "注册后进入同一个情报工作流入口。"}
            </p>
          </div>
        </div>
      </div>

      <button
        className="mt-5 inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white shadow-[0_14px_28px_rgba(201,111,92,0.22)] transition hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:opacity-60"
        disabled={submitting}
        type="submit"
      >
        {submitting ? "处理中" : mode === "login" ? "登录" : "创建账号"}
        <ArrowRight size={16} aria-hidden="true" />
      </button>

      <p className="mt-4 text-center text-xs leading-5 text-[#8B6D63]">
        访问即进入当前 Workspace 范围，后续数据按 Workspace 隔离。
      </p>
    </form>
  );
}

function getSafeNextPath(next: string | null) {
  if (next && next.startsWith("/") && !next.startsWith("//") && next !== "/login") {
    return next;
  }
  return "/dashboard";
}

function Field({
  label,
  htmlFor,
  icon: Icon,
  children,
}: {
  label: string;
  htmlFor: string;
  icon: typeof Mail;
  children: ReactNode;
}) {
  return (
    <label className="grid gap-2 text-sm font-semibold text-[#3B2924]" htmlFor={htmlFor}>
      {label}
      <span className="flex h-12 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 transition focus-within:border-[#C96F5C] focus-within:ring-4 focus-within:ring-[#F3D7CE]">
        <Icon size={18} className="shrink-0 text-[#B47767]" aria-hidden="true" />
        {children}
      </span>
    </label>
  );
}
