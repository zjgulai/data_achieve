import { AppShell } from "@/components/layout/app-shell";
import { PlatformCredentialsWorkspace } from "@/components/settings/platform-credentials-workspace";

export default function PlatformCredentialsPage() {
  return (
    <AppShell
      brief="集中管理各平台所需凭证；Secret 只单向提交到服务端加密 vault，配置状态不代表已授权调用。"
      description="YouTube、Reddit、X、Instagram、Threads、TikTok 与 LinkedIn"
      signals={[
        "Workspace scoped",
        "Secrets never echoed",
        "Provider call disabled",
      ]}
      title="平台设置"
    >
      <PlatformCredentialsWorkspace />
    </AppShell>
  );
}
