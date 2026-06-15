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
import { ApiRequestError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Mode = "login" | "register";

export function LoginPanel() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);

  async function submit() {
    const normalizedEmail = email.trim().toLowerCase();
    const trimmedName = name.trim();
    const validationError = validateAuthInput(mode, normalizedEmail, trimmedName, password);
    if (validationError) {
      setError(validationError);
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (mode === "register") {
        await register({ email: normalizedEmail, name: trimmedName, password });
      } else {
        await login({ email: normalizedEmail, password });
      }
      router.push(getSafeNextPath(searchParams.get("next")) as Route);
      router.refresh();
    } catch (caught) {
      setError(getAuthErrorMessage(caught, mode));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      className="w-full"
      noValidate
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
          {mode === "login" ? "登录情报工作台" : "创建账号"}
        </h2>
        <p className="mt-2 text-sm leading-6 text-[#7A625A]">
          {mode === "login"
            ? "输入已注册账号进入已填充的情报工作台。"
            : "新账号注册后直接进入培训情报工作台，不再看到空白骨架。"}
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
              placeholder="你的名称"
              required
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
            placeholder="you@example.com"
            required
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
            minLength={8}
            required
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
              {mode === "login" ? "账号验证" : "自动接入训练数据"}
            </p>
            <p className="mt-1 text-xs leading-5 text-[#7A625A]">
              {mode === "login"
                ? "使用已有邮箱和密码登录；没有账号时切换到注册。"
                : "注册成功后进入同一套项目、采集源、任务、信号、情报和报告。"}
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
        注册和登录默认进入 Data Achieve 培训情报工作台。
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

function validateAuthInput(mode: Mode, email: string, name: string, password: string) {
  if (!email) {
    return "请输入邮箱。";
  }
  if (!email.includes("@")) {
    return "请输入有效邮箱。";
  }
  if (mode === "register" && !name) {
    return "请输入名称。";
  }
  if (!password) {
    return "请输入密码。";
  }
  if (password.length < 8) {
    return "密码至少 8 位。";
  }
  return null;
}

function getAuthErrorMessage(caught: unknown, mode: Mode) {
  if (caught instanceof ApiRequestError) {
    if (caught.status === 401) {
      return "邮箱或密码不正确。";
    }
    if (caught.status === 409) {
      return "该邮箱已注册，请切换到登录。";
    }
    if (caught.status === 422) {
      return mode === "register" ? "请检查邮箱、名称和密码格式。" : "请检查邮箱和密码格式。";
    }
    if (caught.status >= 500) {
      return "认证服务暂时不可用，请稍后重试。";
    }
    return caught.message;
  }
  if (caught instanceof TypeError && caught.message === "Failed to fetch") {
    return "无法连接认证服务，请确认 API 服务和网络可用。";
  }
  return caught instanceof Error ? caught.message : "认证失败，请重试。";
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
