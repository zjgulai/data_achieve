import { AppShell } from "@/components/layout/app-shell";
import { RawRecordsWorkspace } from "@/components/raw-records/raw-records-workspace";

export default function RawRecordsPage() {
  return (
    <AppShell title="原始数据" description="RawRecord 列表、内容哈希、采集来源">
      <RawRecordsWorkspace />
    </AppShell>
  );
}
