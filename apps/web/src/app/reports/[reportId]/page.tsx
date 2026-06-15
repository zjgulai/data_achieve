import { AppShell } from "@/components/layout/app-shell";
import { ReportDetailPageWorkspace } from "@/components/reports/report-detail-page-workspace";

export default async function ReportDetailPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = await params;

  return (
    <AppShell
      title="报告详情"
      description="报告正文、证据引用和派发状态"
      brief="报告详情用于逐段阅读报告结论，并核对每条结论对应的情报、原始证据和派发记录。"
      signals={["正文分段", "证据引用", "派发状态"]}
    >
      <ReportDetailPageWorkspace reportId={reportId} />
    </AppShell>
  );
}
