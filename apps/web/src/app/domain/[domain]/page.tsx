import { notFound } from "next/navigation";
import Link from "next/link";

import { DashboardOverview } from "@/components/dashboard/dashboard-overview";
import { AppShell } from "@/components/layout/app-shell";

const domainCopy = {
  osint: {
    title: "开源雷达",
    description: "GitHub 趋势、Star 增速、Release 流",
    brief:
      "开源雷达聚焦 GitHub、Release 和工具生态变化，用于识别可复用的爬虫、Agent、MCP 与数据采集方案。",
    signals: ["GitHub 趋势", "Release 变化", "采集工具"],
  },
  ecommerce: {
    title: "电商风向",
    description: "价格变动、排名走势、商品信号",
    brief:
      "电商风向沉淀价格、排名、商品页面和评论等采集入口，服务平台采集培训与竞品监控。",
    signals: ["价格变化", "排名趋势", "商品信号"],
  },
  social: {
    title: "社媒脉搏",
    description: "手动导入数据、热点实体、内容信号",
    brief:
      "社媒脉搏把热点实体、内容线索和导入记录集中在同一视角，便于追踪平台内容采集方法。",
    signals: ["热点实体", "内容信号", "导入记录"],
  },
  competitor: {
    title: "竞品守望",
    description: "官网变化、页面快照、策略动态",
    brief:
      "竞品守望跟踪官网、文档、价格页和发布动态，形成可追溯的竞品采集与变化观察样本。",
    signals: ["页面快照", "策略动态", "官网变化"],
  },
  agent: {
    title: "Agent 生态",
    description: "AI Agent、Skills、MCP 和采集编排工具",
    brief:
      "Agent 生态聚合 AI Agent、Skills、MCP、浏览器自动化和爬虫编排相关情报，支撑培训内容持续更新。",
    signals: ["Skills", "MCP", "采集编排"],
  },
  platform: {
    title: "平台采集",
    description: "GitHub、跨境电商、社媒、视频与内容平台的数据采集方法",
    brief:
      "平台采集沉淀 GitHub、跨境电商、社媒、视频与内容平台的数据入口、授权边界、频控策略和采集方法，避免只停留在演示数据。",
    signals: ["平台入口", "跨境电商", "频控策略"],
  },
  governance: {
    title: "合规边界",
    description: "授权范围、频率限制、robots、账号安全和风险提示",
    brief:
      "合规边界记录授权范围、频率限制、robots、账号安全、禁止项和留痕要求，为每类采集动作提供可解释的风险边界。",
    signals: ["授权范围", "频率限制", "审计留痕"],
  },
} as const;

type DomainKey = keyof typeof domainCopy;

const trainingDomainCopy: Partial<
  Record<DomainKey, { title: string; body: string; tags: string[] }>
> = {
  agent: {
    title: "Agent 生态培训路径",
    body: "围绕 AI Agent、Skills、MCP、browser-use、Playwright 和采集编排工具，讲清工具能力、安装 SOP、适用场景和风险边界。",
    tags: ["Skills", "MCP", "Agent 浏览器", "爬虫编排"],
  },
  platform: {
    title: "平台采集培训路径",
    body: "围绕 GitHub、跨境电商、社媒、视频与内容平台，讲清官方 API、公开页面、频控策略、禁止项和证据留痕。",
    tags: ["GitHub API", "跨境电商", "社媒采集", "平台限制"],
  },
  governance: {
    title: "合规边界培训路径",
    body: "围绕授权范围、频率限制、robots 与账号安全、公开数据和审计留痕，讲清采集动作的红线和可执行边界。",
    tags: ["授权边界", "频控", "禁止项", "审计留痕"],
  },
};

export default async function DomainPage({
  params,
}: {
  params: Promise<{ domain: string }>;
}) {
  const { domain } = await params;

  if (!isDomainKey(domain)) {
    notFound();
  }

  const copy = domainCopy[domain];

  return (
    <AppShell
      title={copy.title}
      description={copy.description}
      brief={copy.brief}
      signals={copy.signals}
    >
      <DomainTrainingPanel domain={domain} />
      <DashboardOverview domain={domain} />
    </AppShell>
  );
}

function isDomainKey(value: string): value is DomainKey {
  return value in domainCopy;
}

function DomainTrainingPanel({ domain }: { domain: DomainKey }) {
  const training =
    trainingDomainCopy[domain] ??
    {
      title: `${domainCopy[domain].title}教学视角`,
      body: "该业务域可作为采集方法案例入口：先看数据源，再看原始证据、信号、情报和报告，形成完整教学闭环。",
      tags: domainCopy[domain].signals,
    };

  return (
    <section className="rounded-2xl border border-[#F1D9A8] bg-[#FFF9E9] p-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-[#8C6824]">培训域路径</p>
          <h2 className="mt-1 text-base font-semibold text-[#2E201C]">{training.title}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#87611B]">{training.body}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {training.tags.map((tag) => (
              <span
                className="rounded-full border border-[#F1D9A8] bg-white px-3 py-1 text-xs font-semibold text-[#8C6824]"
                key={tag}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-3 lg:w-[360px]">
          <TrainingLink href="/toolkit" label="工具库" />
          <TrainingLink href="/signals" label="信号链路" />
          <TrainingLink href="/reports" label="培训报告" />
        </div>
      </div>
    </section>
  );
}

function TrainingLink({ href, label }: { href: "/toolkit" | "/signals" | "/reports"; label: string }) {
  return (
    <Link
      className="inline-flex h-10 items-center justify-center rounded-xl border border-[#F1D9A8] bg-white px-3 text-sm font-semibold text-[#8C6824] transition hover:border-[#C96F5C]"
      href={href}
    >
      {label}
    </Link>
  );
}
