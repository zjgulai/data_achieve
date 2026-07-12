import { ApiMarketWorkspace } from "@/components/api-market/api-market-workspace";
import { AppShell } from "@/components/layout/app-shell";
import {
  parseCapabilityMarketFilters,
  parseCapabilityMarketView,
} from "@/lib/capability-market";

type ApiMarketPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function ApiMarketPage({ searchParams }: ApiMarketPageProps) {
  const resolvedSearchParams = await searchParams;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(resolvedSearchParams)) {
    const firstValue = Array.isArray(value) ? value[0] : value;
    if (firstValue !== undefined) {
      query.set(key, firstValue);
    }
  }

  return (
    <AppShell
      title="能力市场"
      description="7×6 能力矩阵、Implementation、Constraint 与 Evidence"
      brief="按场景、平台和访问通道审查规范能力事实；Candidate 不代表可执行。"
      signals={["42 个显式矩阵格", "Candidate 不可执行", "provider_call=false"]}
    >
      <ApiMarketWorkspace
        initialFilters={parseCapabilityMarketFilters(query.toString())}
        initialView={parseCapabilityMarketView(query.get("view"))}
      />
    </AppShell>
  );
}
