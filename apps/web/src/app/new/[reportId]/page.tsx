import { InsightReportDetailWorkspace } from "@/components/insight/insight-report-detail-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default async function InsightReportDetailPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = await params;

  return (
    <AppShell
      brief="报告来自已生成快照。页面只读，不执行分析。"
      description="归档报告正文与数据范围"
      signals={["数据快照", "正文只读", "来源可追溯"]}
      title="报告详情"
    >
      <InsightReportDetailWorkspace reportId={reportId} />
    </AppShell>
  );
}
