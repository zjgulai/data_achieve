import { notFound } from "next/navigation";

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
    description: "电商、社媒、视频和内容平台的数据采集方法",
    brief:
      "平台采集沉淀不同平台的数据入口、授权边界、频控策略和采集方法，避免只停留在演示数据。",
    signals: ["平台入口", "频控策略", "采集方法"],
  },
  governance: {
    title: "合规边界",
    description: "授权范围、频控策略、禁止项和风险提示",
    brief:
      "合规边界记录授权范围、禁止项、频控和留痕要求，为每类采集动作提供可解释的风险边界。",
    signals: ["授权范围", "风险提示", "审计留痕"],
  },
} as const;

type DomainKey = keyof typeof domainCopy;

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
      <DashboardOverview domain={domain} />
    </AppShell>
  );
}

function isDomainKey(value: string): value is DomainKey {
  return value in domainCopy;
}
