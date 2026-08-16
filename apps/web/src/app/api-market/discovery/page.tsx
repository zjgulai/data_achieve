import { CapabilityDiscoveryWorkspace } from "@/components/api-market/capability-discovery-workspace";
import { CapabilityGovernanceWorkspace } from "@/components/api-market/capability-governance-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function CapabilityDiscoveryPage() {
  return (
    <AppShell
      title="能力发现 Preview"
      description="离线来源快照、Candidate Assertion 与 Evidence 审查"
      brief="只回放 2 份公开市场与 2 份官方文档 Fixture；结果待核验、不可执行、不可发布。"
      signals={["4 份离线来源", "provider_call=false", "browser_run=false"]}
    >
      <div className="grid gap-10">
        <CapabilityDiscoveryWorkspace />
        <CapabilityGovernanceWorkspace />
      </div>
    </AppShell>
  );
}
