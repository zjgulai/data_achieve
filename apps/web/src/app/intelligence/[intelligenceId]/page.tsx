import { IntelligenceDetailWorkspace } from "@/components/intelligence/intelligence-detail-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default async function IntelligenceDetailPage({
  params,
}: {
  params: Promise<{ intelligenceId: string }>;
}) {
  const { intelligenceId } = await params;

  return (
    <AppShell
      title="情报详情"
      description="结论、证据、快照对比和人工反馈"
      brief="情报详情用于核对单条结论背后的证据、快照差异和人工处理状态。"
      signals={["证据链", "快照对比", "人工反馈"]}
    >
      <IntelligenceDetailWorkspace intelligenceId={intelligenceId} />
    </AppShell>
  );
}
