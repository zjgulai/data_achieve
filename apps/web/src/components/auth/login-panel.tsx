"use client";

import { LockKeyhole, Mail, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { login, register } from "@/lib/api/auth";

type Mode = "login" | "register";

export function LoginPanel() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("owner@example.com");
  const [name, setName] = useState("Owner");
  const [password, setPassword] = useState("strong-password");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "register") {
        await register({ email, name, password });
      } else {
        await login({ email, password });
      }
      router.push("/dashboard");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      className="flex flex-col justify-center gap-5 p-8"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <div>
        <h2 className="text-2xl font-semibold">{mode === "login" ? "登录" : "注册"}</h2>
        <p className="mt-2 text-sm text-[#6b7280]">进入情报工作台</p>
      </div>

      <div className="grid grid-cols-2 rounded-md border border-[#dfe3ea] p-1 text-sm">
        <button
          className={`rounded px-3 py-2 ${mode === "login" ? "bg-[#0f766e] text-white" : ""}`}
          onClick={() => setMode("login")}
          type="button"
        >
          登录
        </button>
        <button
          className={`rounded px-3 py-2 ${mode === "register" ? "bg-[#0f766e] text-white" : ""}`}
          onClick={() => setMode("register")}
          type="button"
        >
          注册
        </button>
      </div>

      {mode === "register" ? (
        <label className="grid gap-2 text-sm font-medium">
          名称
          <span className="flex items-center gap-2 rounded-md border border-[#dfe3ea] bg-white px-3 py-2">
            <UserRound size={18} className="text-[#6b7280]" aria-hidden="true" />
            <input
              className="w-full border-0 bg-transparent outline-none"
              name="name"
              onChange={(event) => setName(event.target.value)}
              value={name}
            />
          </span>
        </label>
      ) : null}

      <label className="grid gap-2 text-sm font-medium">
        邮箱
        <span className="flex items-center gap-2 rounded-md border border-[#dfe3ea] bg-white px-3 py-2">
          <Mail size={18} className="text-[#6b7280]" aria-hidden="true" />
          <input
            className="w-full border-0 bg-transparent outline-none"
            name="email"
            onChange={(event) => setEmail(event.target.value)}
            type="email"
            value={email}
          />
        </span>
      </label>

      <label className="grid gap-2 text-sm font-medium">
        密码
        <span className="flex items-center gap-2 rounded-md border border-[#dfe3ea] bg-white px-3 py-2">
          <LockKeyhole size={18} className="text-[#6b7280]" aria-hidden="true" />
          <input
            className="w-full border-0 bg-transparent outline-none"
            name="password"
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            value={password}
          />
        </span>
      </label>

      {error ? (
        <p className="rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
          {error}
        </p>
      ) : null}

      <button
        className="rounded-md bg-[#0f766e] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
        disabled={submitting}
        type="submit"
      >
        {submitting ? "处理中" : mode === "login" ? "登录" : "创建账号"}
      </button>
    </form>
  );
}
