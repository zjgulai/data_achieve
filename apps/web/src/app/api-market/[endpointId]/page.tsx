import { notFound } from "next/navigation";

import { ApiMarketDetailWorkspace } from "@/components/api-market/api-market-detail-workspace";
import { AppShell } from "@/components/layout/app-shell";
import { findApiMarketPresentationById } from "@/lib/api-market-catalog";

export default async function ApiMarketEndpointPage({
  params,
}: {
  params: Promise<{ endpointId: string }>;
}) {
  const { endpointId } = await params;
  const presentation = findApiMarketPresentationById(endpointId);

  if (!presentation) {
    notFound();
  }

  return (
    <AppShell
      title={presentation.title}
      description={presentation.endpointId}
      brief="展示增强只提供 Fixture Review；能力事实由后端 Capability API 加载。"
      signals={["Fixture Review", "provider_call=false", "production unchanged"]}
    >
      <ApiMarketDetailWorkspace presentation={presentation} />
    </AppShell>
  );
}
