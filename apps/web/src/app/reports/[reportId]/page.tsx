import { AppShell } from "@/components/layout/app-shell";
import { ReportDetailPageWorkspace } from "@/components/reports/report-detail-page-workspace";

export default async function ReportDetailPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = await params;

  return (
    <AppShell title="报告详情" description="报告正文、证据引用和派发状态">
      <ReportDetailPageWorkspace reportId={reportId} />
    </AppShell>
  );
}
