import { AppShell } from "@/components/layout/app-shell";
import { RawRecordsWorkspace } from "@/components/raw-records/raw-records-workspace";

export default function RawRecordsPage() {
  return (
    <AppShell title="原始数据" description="原始事实、内容哈希、采集证据审计">
      <RawRecordsWorkspace />
    </AppShell>
  );
}
