import {
  Activity,
  ArrowRight,
  BellRing,
  Database,
  FileText,
  Fingerprint,
  GitBranch,
  LineChart,
  Radar,
  ShieldCheck,
} from "lucide-react";
import { Suspense } from "react";

import { LoginPanel } from "@/components/auth/login-panel";

export default function LoginPage() {
  return (
    <main className="min-h-screen bg-[#F6EEE9] px-4 py-5 text-[#2E201C] sm:px-6 lg:px-8">
      <section className="mx-auto grid min-h-[calc(100vh-40px)] w-full max-w-7xl overflow-hidden rounded-2xl border border-[#EDDCD3] bg-[#FFFDFC] shadow-[0_24px_90px_rgba(115,70,58,0.12)] lg:grid-cols-[minmax(0,1fr)_470px]">
        <div className="relative flex min-w-0 flex-col justify-between overflow-hidden bg-[#FFF8F4] p-5 sm:p-8 lg:p-10">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3 text-sm font-semibold">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#C96F5C] text-white shadow-[0_14px_28px_rgba(201,111,92,0.22)]">
                <Activity size={20} aria-hidden="true" />
              </span>
              <div>
                <p className="text-base font-semibold">Data Intelligence Hub</p>
                <p className="text-xs font-medium text-[#8B6D63]">Evidence-first workspace</p>
              </div>
            </div>
            <span className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/80 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <Fingerprint size={14} aria-hidden="true" />
              Workspace Login
            </span>
          </div>

          <div className="my-8 grid gap-8 xl:grid-cols-[minmax(0,0.86fr)_minmax(360px,1fr)] xl:items-center">
            <div className="min-w-0">
              <p className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold uppercase text-[#B47767]">
                <Radar size={14} aria-hidden="true" />
                Traceable Intelligence
              </p>
              <h1 className="mt-5 max-w-2xl text-3xl font-semibold leading-tight tracking-normal text-[#2E201C] sm:text-4xl lg:text-5xl">
                登录到可追溯的情报工作台
              </h1>
              <p className="mt-5 max-w-xl text-sm leading-6 text-[#7A625A] sm:text-base">
                采集、快照、信号、证据和报告都围绕 Workspace 组织，团队从同一条链路判断事实，不让 AI 改写原始证据。
              </p>
              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                <SignalBadge icon={Database} label="原始事实" value="保留原文" />
                <SignalBadge icon={GitBranch} label="变化信号" value="规则触发" />
                <SignalBadge icon={FileText} label="证据链路" value="可回溯" />
              </div>
            </div>

            <div className="min-w-0 rounded-2xl border border-[#E8D4CB] bg-white/85 p-4 shadow-[0_18px_60px_rgba(115,70,58,0.09)]">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase text-[#B47767]">Live Workspace</p>
                  <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">今日情报链路</h2>
                </div>
                <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#C96F5C] text-white">
                  <LineChart size={18} aria-hidden="true" />
                </span>
              </div>
              <div className="grid gap-3">
                <PreviewRow
                  icon={Database}
                  label="采集完成"
                  title="竞品首页监控"
                  value="页面快照已留存"
                />
                <PreviewRow
                  icon={BellRing}
                  label="信号触发"
                  title="页面变化 · 高"
                  value="新增产品线区块"
                />
                <PreviewRow
                  icon={ShieldCheck}
                  label="证据绑定"
                  title="证据包已就绪"
                  value="快照 + 原文 + URL"
                />
              </div>
              <div className="mt-4 rounded-2xl border border-[#F0E1D9] bg-[#FFF8F4] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase text-[#B47767]">Workspace Health</p>
                    <p className="mt-1 text-2xl font-semibold text-[#2E201C]">96</p>
                  </div>
                  <ArrowRight className="text-[#C96F5C]" size={20} aria-hidden="true" />
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#F3E3DC]">
                  <div className="h-full w-[92%] rounded-full bg-[#C96F5C]" />
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-3 text-sm text-[#5F4A43] sm:grid-cols-3">
            <Footnote title="MVP Auth" value="邮箱 + 密码" />
            <Footnote title="Workspace" value="默认进入培训库" />
            <Footnote title="Session" value="Cookie 保持登录态" />
          </div>
        </div>

        <div className="flex min-w-0 items-center bg-white p-5 sm:p-8 lg:p-10">
          <Suspense fallback={<div className="h-[420px] w-full rounded-2xl bg-[#FFF8F4]" />}>
            <LoginPanel />
          </Suspense>
        </div>
      </section>
    </main>
  );
}

function SignalBadge({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Database;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-white/80 p-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
        <Icon size={14} aria-hidden="true" />
        {label}
      </div>
      <p className="mt-2 break-words text-sm font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

function PreviewRow({
  icon: Icon,
  label,
  title,
  value,
}: {
  icon: typeof Database;
  label: string;
  title: string;
  value: string;
}) {
  return (
    <div className="grid grid-cols-[40px_minmax(0,1fr)] gap-3 rounded-2xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FFF1EB] text-[#C96F5C]">
        <Icon size={17} aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase text-[#B47767]">{label}</p>
        <p className="mt-1 break-words text-sm font-semibold text-[#2E201C]">{title}</p>
        <p className="mt-1 break-words text-xs text-[#7A625A]">{value}</p>
      </div>
    </div>
  );
}

function Footnote({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-white/70 px-4 py-3">
      <p className="text-xs font-semibold uppercase text-[#B47767]">{title}</p>
      <p className="mt-1 break-words font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}
