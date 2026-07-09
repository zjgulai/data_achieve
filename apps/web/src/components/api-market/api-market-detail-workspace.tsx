"use client";

import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  Clipboard,
  DatabaseZap,
  FileJson2,
  KeyRound,
  LockKeyhole,
  Route as RouteIcon,
  ShieldCheck,
  SlidersHorizontal,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import type { Route } from "next";
import { WorkbenchFact, WorkbenchPanel, WorkbenchTag } from "@/components/common/workbench-ui";
import type { ApiMarketEndpoint } from "@/types/api-market";

export function ApiMarketDetailWorkspace({ endpoint }: { endpoint: ApiMarketEndpoint }) {
  const [copied, setCopied] = useState(false);
  const responsePreview = useMemo(
    () => JSON.stringify(endpoint.responsePreview.sample, null, 2),
    [endpoint.responsePreview.sample],
  );
  const requestBodyPreview = endpoint.request.requestBodyExample
    ? JSON.stringify(endpoint.request.requestBodyExample, null, 2)
    : null;

  async function copyFixture() {
    if (!navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(responsePreview);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <div className="grid min-w-0 gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7A625A]"
          href="/api-market"
        >
          <ArrowLeft size={15} aria-hidden="true" />
          返回 API市场
        </Link>
        <Link
          className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white"
          href={typedRoute(
            `/automation?platform=${endpoint.platform}&endpoint=${encodeURIComponent(endpoint.endpoint)}`,
          )}
        >
          生成预案
          <ArrowUpRight size={15} aria-hidden="true" />
        </Link>
      </div>

      <WorkbenchPanel
        action={<WorkbenchTag tone="neutral">provider_call=false</WorkbenchTag>}
        icon={RouteIcon}
        label={endpoint.platformLabel}
        subtitle={endpoint.summary}
        title={endpoint.title}
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <WorkbenchFact label="provider_id" value={endpoint.providerId} />
          <WorkbenchFact label="method" value={endpoint.method} />
          <WorkbenchFact label="endpoint" value={endpoint.endpoint} />
          <WorkbenchFact label="api_version" value={endpoint.apiVersion} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <WorkbenchTag tone={endpoint.priority === "p0" ? "green" : "amber"}>
            {endpoint.priority}
          </WorkbenchTag>
          <WorkbenchTag tone={stabilityTone(endpoint.stability)}>
            {endpoint.stability}
          </WorkbenchTag>
          <WorkbenchTag tone="muted">{endpoint.category}</WorkbenchTag>
          <WorkbenchTag tone="neutral">{endpoint.executionMode}</WorkbenchTag>
          <WorkbenchTag tone="rose">{endpoint.sdkStatus}</WorkbenchTag>
        </div>
      </WorkbenchPanel>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="grid min-w-0 gap-5">
          <WorkbenchPanel
            icon={SlidersHorizontal}
            label="Contract"
            subtitle="只展示官方/授权 API 合同字段，后续 adapter 只能按这些字段做最小 glue code"
            title="请求合同与参数"
          >
            <div className="overflow-x-auto rounded-2xl border border-[#F0E1D9]">
              <table className="w-full min-w-[720px] border-collapse text-left text-sm">
                <thead className="bg-[#FBF8F5] text-xs uppercase text-[#B47767]">
                  <tr>
                    <th className="px-3 py-3">name</th>
                    <th className="px-3 py-3">in</th>
                    <th className="px-3 py-3">type</th>
                    <th className="px-3 py-3">required</th>
                    <th className="px-3 py-3">example</th>
                    <th className="px-3 py-3">description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F0E1D9] bg-white">
                  {endpoint.request.parameters.map((param) => (
                    <tr key={`${param.in}:${param.name}`}>
                      <td className="break-all px-3 py-3 font-semibold text-[#2E201C]">
                        {param.name}
                      </td>
                      <td className="px-3 py-3 text-[#7A625A]">{param.in}</td>
                      <td className="px-3 py-3 text-[#7A625A]">{param.type}</td>
                      <td className="px-3 py-3">
                        <WorkbenchTag tone={param.required ? "rose" : "muted"}>
                          {param.required ? "required" : "optional"}
                        </WorkbenchTag>
                      </td>
                      <td className="break-all px-3 py-3 text-[#7A625A]">
                        {param.example ?? "-"}
                      </td>
                      <td className="min-w-56 px-3 py-3 leading-6 text-[#7A625A]">
                        {param.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {requestBodyPreview ? (
              <JsonPanel label="request_body_example" value={requestBodyPreview} />
            ) : null}
          </WorkbenchPanel>

          <WorkbenchPanel
            icon={FileJson2}
            label="Fixture Replay"
            subtitle="本页只使用本地静态 fixture 样例，不读取环境变量、不创建真实 provider client"
            title="Fixture 响应预览"
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                <WorkbenchTag tone="neutral">{endpoint.responsePreview.schemaVersion}</WorkbenchTag>
                <WorkbenchTag tone="green">social schema linked</WorkbenchTag>
              </div>
              <button
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7A625A]"
                onClick={copyFixture}
                type="button"
              >
                {copied ? <Check size={15} aria-hidden="true" /> : <Clipboard size={15} aria-hidden="true" />}
                {copied ? "已复制" : "复制 fixture"}
              </button>
            </div>
            <JsonPanel label="response_preview" value={responsePreview} />
          </WorkbenchPanel>
        </section>

        <aside className="grid min-w-0 content-start gap-5">
          <WorkbenchPanel
            icon={ShieldCheck}
            label="Policy Gate"
            subtitle="live gate 未授权前只能 dry-run 或 fixture replay"
            title="私有化部署边界"
          >
            <div className="grid gap-2">
              <BoundaryRow label="provider_call" value={String(endpoint.providerCall)} tone="green" />
              <BoundaryRow
                label="provider_call_attempted"
                value={String(endpoint.providerCallAttempted)}
                tone="green"
              />
              <BoundaryRow
                label="credential_read_attempted"
                value={String(endpoint.credentialReadAttempted)}
                tone="green"
              />
              <BoundaryRow
                label="live_client_created"
                value={String(endpoint.liveClientCreated)}
                tone="green"
              />
              <BoundaryRow
                label="production_write_allowed"
                value={String(endpoint.productionWriteAllowed)}
                tone="green"
              />
            </div>
          </WorkbenchPanel>

          <WorkbenchPanel
            icon={KeyRound}
            label="Authorization"
            subtitle={endpoint.authMode}
            title="凭据与权限"
          >
            <TagList icon={KeyRound} items={endpoint.requiredCredentials} tone="muted" />
            <div className="mt-3 grid gap-2 rounded-2xl border border-[#F0E1D9] bg-[#FFFDFC] p-3 text-sm">
              <span className="text-xs font-semibold uppercase text-[#B47767]">quota</span>
              <p className="leading-6 text-[#3B2924]">{endpoint.quotaHint}</p>
            </div>
            <div className="mt-3 grid gap-2 rounded-2xl border border-[#F0E1D9] bg-[#FFFDFC] p-3 text-sm">
              <span className="text-xs font-semibold uppercase text-[#B47767]">cost</span>
              <p className="leading-6 text-[#3B2924]">{endpoint.costHint}</p>
            </div>
          </WorkbenchPanel>

          <WorkbenchPanel icon={LockKeyhole} label="Blocked" title="禁止实现项">
            <TagList icon={LockKeyhole} items={endpoint.blockedActions} tone="rose" />
            <div className="mt-4 grid gap-2">
              {endpoint.policyFlags.map((flag) => (
                <span
                  className="inline-flex min-w-0 items-center gap-2 break-all rounded-xl bg-[#FBF8F5] px-3 py-2 text-xs font-semibold text-[#7A625A]"
                  key={flag}
                >
                  <ShieldCheck size={13} className="shrink-0" aria-hidden="true" />
                  {flag}
                </span>
              ))}
            </div>
          </WorkbenchPanel>

          <WorkbenchPanel
            icon={DatabaseZap}
            label="SDK"
            subtitle="优先复用成熟官方/流行 SDK，页面仅记录选型，不安装运行时采集依赖"
            title="开源复用候选"
          >
            <div className="grid gap-2">
              <BoundaryRow label="package" value={endpoint.sdkPackage} tone="neutral" />
              <BoundaryRow label="status" value={endpoint.sdkStatus} tone="neutral" />
              <BoundaryRow label="data_domain" value={endpoint.dataDomain.join(", ")} tone="neutral" />
            </div>
            <div className="mt-4 grid gap-2">
              {endpoint.officialDocs.map((doc) => (
                <a
                  className="inline-flex min-w-0 items-center gap-2 break-all rounded-xl border border-[#E8D4CB] bg-white px-3 py-2 text-sm font-semibold text-[#7A625A]"
                  href={doc}
                  key={doc}
                  rel="noreferrer"
                  target="_blank"
                >
                  <Zap size={14} className="shrink-0" aria-hidden="true" />
                  {doc}
                </a>
              ))}
            </div>
          </WorkbenchPanel>
        </aside>
      </div>
    </div>
  );
}

function BoundaryRow({
  label,
  tone,
  value,
}: {
  label: string;
  tone: "green" | "neutral";
  value: string;
}) {
  const valueClass = tone === "green" ? "text-[#2EBA62]" : "text-[#3B2924]";
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2">
      <span className="break-all text-sm font-semibold text-[#7A625A]">{label}</span>
      <span className={`shrink-0 text-sm font-semibold ${valueClass}`}>{value}</span>
    </div>
  );
}

function JsonPanel({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-w-0 gap-2">
      <p className="text-xs font-semibold uppercase text-[#B47767]">{label}</p>
      <pre className="max-h-[420px] overflow-auto rounded-2xl border border-[#F0E1D9] bg-[#2E201C] p-4 text-xs leading-5 text-[#FFF8F5]">
        <code>{value}</code>
      </pre>
    </div>
  );
}

function TagList({
  icon: Icon,
  items,
  tone,
}: {
  icon: typeof KeyRound;
  items: string[];
  tone: "muted" | "rose";
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          className="inline-flex min-w-0 items-center gap-2 break-all rounded-xl bg-[#FBF8F5] px-3 py-2 text-xs font-semibold text-[#7A625A]"
          key={item}
        >
          <Icon size={13} className="shrink-0" aria-hidden="true" />
          <WorkbenchTag tone={tone}>{item}</WorkbenchTag>
        </span>
      ))}
    </div>
  );
}

function stabilityTone(stability: ApiMarketEndpoint["stability"]): "amber" | "green" | "rose" {
  if (stability === "high") {
    return "green";
  }
  if (stability === "medium") {
    return "amber";
  }
  return "rose";
}

function typedRoute(href: string): Route {
  return href as Route;
}
