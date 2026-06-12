import { notFound } from "next/navigation";

import { DashboardOverview } from "@/components/dashboard/dashboard-overview";
import { AppShell } from "@/components/layout/app-shell";

const domainCopy = {
  osint: {
    title: "开源雷达",
    description: "GitHub 趋势、Star 增速、Release 流",
  },
  ecommerce: {
    title: "电商风向",
    description: "价格变动、排名走势、商品信号",
  },
  social: {
    title: "社媒脉搏",
    description: "手动导入数据、热点实体、内容信号",
  },
  competitor: {
    title: "竞品守望",
    description: "官网变化、页面快照、策略动态",
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
    <AppShell title={copy.title} description={copy.description}>
      <DashboardOverview domain={domain} />
    </AppShell>
  );
}

function isDomainKey(value: string): value is DomainKey {
  return value in domainCopy;
}
