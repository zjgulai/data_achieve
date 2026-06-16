import { AppShell } from "@/components/layout/app-shell";
import { ToolkitLecturePlaybookPage } from "@/components/toolkit/toolkit-lecture-playbook-page";

export default async function ToolkitPlaybookPage({
  params,
}: {
  params: Promise<{ playbookId: string }>;
}) {
  const { playbookId } = await params;

  return (
    <AppShell
      title="培训讲义"
      description="可打印的数据采集课程讲义"
      brief="讲义页用于培训交付：保留讲解顺序、实操步骤、验收步骤、风险边界、课堂练习和证据链接，支持复制深链和浏览器打印。"
      signals={["讲义深链", "浏览器打印", "证据可追溯"]}
    >
      <ToolkitLecturePlaybookPage playbookId={playbookId} />
    </AppShell>
  );
}
