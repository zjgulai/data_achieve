import { ApiMarketWorkspace } from "@/components/api-market/api-market-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function ApiMarketPage() {
  return (
    <AppShell
      title="API市场"
      description="官方/授权 API 能力、私有化部署入口和 fixture-only 预案"
      brief="API市场把海外社媒官方 API、授权边界、SDK 选型、成本/限流和数据合同放在同一页复核；默认只做 fixture 预案，不读取凭据、不调用平台、不写生产。"
      signals={["官方 API 优先", "私有化部署", "fixture-only", "合规边界"]}
    >
      <ApiMarketWorkspace />
    </AppShell>
  );
}
