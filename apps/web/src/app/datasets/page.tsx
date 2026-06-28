import { DatasetsWorkspace } from "@/components/datasets/datasets-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function DatasetsPage() {
  return (
    <AppShell
      title="数据集资产台"
      description="回看已保存的数据集版本、字段质量、清洗脚本和漂移历史"
      brief="数据集资产台承接自动采集工作台的保存结果：每个数据集版本都记录来源运行、字段选择、清洗规则和质量指标，方便后续调度、复核和下游交付。"
      signals={["版本历史", "字段质量", "清洗规则", "漂移历史"]}
    >
      <DatasetsWorkspace />
    </AppShell>
  );
}
