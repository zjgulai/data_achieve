import { AppShell } from "@/components/layout/app-shell";
import { ToolkitCoursePackPage } from "@/components/toolkit/toolkit-course-pack-page";

export default function ToolkitCoursePackRoute() {
  return (
    <AppShell
      title="培训课程包"
      description="可打印的数据采集工具与平台方法课程包"
      brief="课程包把工具雷达、平台方法、风险边界和课堂讲义组织成一套可交付培训材料，支持复制链接和浏览器打印。"
      signals={["课程目录", "全量讲义", "打印导出"]}
    >
      <ToolkitCoursePackPage />
    </AppShell>
  );
}
