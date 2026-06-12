import { Activity } from "lucide-react";

import { LoginPanel } from "@/components/auth/login-panel";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f7f8fa] px-6 py-10">
      <section className="grid w-full max-w-5xl grid-cols-1 overflow-hidden rounded-lg border border-[#dfe3ea] bg-white md:grid-cols-[1fr_420px]">
        <div className="flex min-h-[520px] flex-col justify-between bg-[#111827] p-8 text-white">
          <div className="flex items-center gap-3 text-sm font-semibold">
            <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[#0f766e]">
              <Activity size={19} aria-hidden="true" />
            </span>
            Data Intelligence Hub
          </div>
          <div className="max-w-xl">
            <p className="mb-4 text-sm uppercase tracking-[0.12em] text-[#99f6e4]">
              Evidence-first intelligence
            </p>
            <h1 className="text-3xl font-semibold leading-tight md:text-4xl">
              把采集数据变成可审计的业务情报
            </h1>
            <p className="mt-5 max-w-lg text-sm leading-6 text-[#d1d5db]">
              RawRecord、Snapshot、Signal、Evidence 全链路保留，AI 只生成解释文本，不改写事实。
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 text-sm text-[#d1d5db]">
            <div className="rounded-md border border-white/10 p-3">采集</div>
            <div className="rounded-md border border-white/10 p-3">信号</div>
            <div className="rounded-md border border-white/10 p-3">证据</div>
          </div>
        </div>

        <LoginPanel />
      </section>
    </main>
  );
}
