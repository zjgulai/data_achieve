import { notFound } from "next/navigation";

import { ApiMarketDetailWorkspace } from "@/components/api-market/api-market-detail-workspace";
import { AppShell } from "@/components/layout/app-shell";
import { findApiMarketEndpointById } from "@/lib/api-market-catalog";

export default async function ApiMarketEndpointPage({
  params,
}: {
  params: Promise<{ endpointId: string }>;
}) {
  const { endpointId } = await params;
  const endpoint = findApiMarketEndpointById(endpointId);

  if (!endpoint) {
    notFound();
  }

  return (
    <AppShell
      title="API市场详情"
      description={`${endpoint.platformLabel} / ${endpoint.endpoint}`}
      brief="详情页用于复核官方 API 合同、私有化运行边界、fixture 响应和 live gate 前置条件；默认不读取凭据、不创建 live client、不调用 provider。"
      signals={["请求合同", "Policy Gate", "Fixture Replay", "provider_call=false"]}
    >
      <ApiMarketDetailWorkspace endpoint={endpoint} />
    </AppShell>
  );
}
