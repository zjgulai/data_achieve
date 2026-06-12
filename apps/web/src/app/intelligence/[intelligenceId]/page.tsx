import { IntelligenceDetailWorkspace } from "@/components/intelligence/intelligence-detail-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default async function IntelligenceDetailPage({
  params,
}: {
  params: Promise<{ intelligenceId: string }>;
}) {
  const { intelligenceId } = await params;

  return (
    <AppShell title="情报详情" description="结论、证据、快照对比和人工反馈">
      <IntelligenceDetailWorkspace intelligenceId={intelligenceId} />
    </AppShell>
  );
}
