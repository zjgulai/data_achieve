import { AppShell } from "@/components/layout/app-shell";
import { RawRecordsWorkspace } from "@/components/raw-records/raw-records-workspace";

export default function RawRecordsPage() {
  return (
    <AppShell
      title="原始数据"
      description="原始事实、校验指纹、采集证据审计"
      brief="原始数据保留采集返回的事实、来源 URL、内容哈希和时间戳，作为后续实体、信号和报告的证据底座。"
      signals={["原始事实", "内容哈希", "来源追溯"]}
    >
      <RawRecordsWorkspace />
    </AppShell>
  );
}
