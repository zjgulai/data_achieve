"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Cable, Code2, Download, ServerCog } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import {
  fetchPlatformPackage,
  fetchPlatformPlaybook,
} from "@/lib/api/platform-packages";
import type { PackageEndpoint } from "@/lib/api/platform-packages";
import { API_BASE_URL } from "@/lib/api/client";

export function SkillDetail({ platformId }: { readonly platformId: string }) {
  const packageQuery = useQuery({
    queryKey: ["platform-package", platformId],
    queryFn: () => fetchPlatformPackage(platformId),
  });
  const playbookQuery = useQuery({
    queryKey: ["platform-playbook", platformId],
    queryFn: () => fetchPlatformPlaybook(platformId),
  });
  const item = packageQuery.data;

  if (packageQuery.isLoading) {
    return <ShellState title="加载中" text="正在读取平台 Skill 契约…" />;
  }
  if (packageQuery.error || !item) {
    return <ShellState title="平台不存在" text="未找到对应的平台工具包。" danger />;
  }

  const firstEndpoint = item.endpoints[0];
  const restExample = firstEndpoint
    ? JSON.stringify(
        {
          project_id: "<project-uuid>",
          endpoint_type: firstEndpoint.endpoint_type,
          params: Object.fromEntries(
            firstEndpoint.required_params.map((name) => [name, `<${name}>`]),
          ),
        },
        null,
        2,
      )
    : "{}";

  return (
    <AppShell
      title={`${item.display_name} Skill`}
      description={`${item.endpoint_count} 个能力视图 · ${item.provider_groups.length} 个 Provider`}
      breadcrumbs={[
        { label: "Skill 与 MCP", href: "/skills" },
        { label: item.display_name },
      ]}
    >
      <section className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
          <p className="text-sm leading-6 text-[var(--text-secondary)]">{item.description}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            {item.methods.map((method) => <Tag key={method}>{method}</Tag>)}
            {item.content_types.map((type) => <Tag key={type}>{type}</Tag>)}
          </div>
        </div>
        <aside className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <InfoRow icon={<Code2 size={14} />} label="Skill" value={item.skill_path} />
          <InfoRow icon={<Cable size={14} />} label="MCP" value="https://scrapy.luteos.com/mcp" />
          <InfoRow icon={<BookOpen size={14} />} label="Playbook" value={item.playbook_path} />
          <InfoRow icon={<ServerCog size={14} />} label="Catalog digest" value="由 API 响应提供" />
          <a
            href={`${API_BASE_URL}/api/platform-packages/${encodeURIComponent(item.platform_id)}/download`}
            className="mt-4 flex min-h-10 items-center justify-center gap-2 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-3 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]"
          >
            <Download size={15} />
            下载 Skill ZIP
          </a>
        </aside>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <CodePanel title="REST 调用" code={`curl -X POST https://scrapy.luteos.com/api/quick-collect \\\n+  -H 'Content-Type: application/json' \\\n+  -d '${restExample.replaceAll("'", "'\\''")}'`} />
        <CodePanel title="MCP 配置" code={`{
  "mcpServers": {
    "data-intelligence-hub": {
      "url": "https://scrapy.luteos.com/mcp",
      "headers": { "Authorization": "Bearer <SCRAPY_MCP_TOKEN>" }
    }
  }
}`} />
      </section>

      <section className="overflow-hidden rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
        <div className="border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 className="font-bold">能力清单</h2>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">参数来自生产 catalog，disabled 能力不可执行。</p>
        </div>
        <div className="divide-y divide-[var(--border-subtle)]">
          {item.endpoints.map((endpoint) => <CapabilityRow key={endpoint.capability_id} endpoint={endpoint} />)}
        </div>
      </section>

      <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
        <h2 className="font-bold">Playbook</h2>
        {playbookQuery.isLoading ? (
          <p className="mt-4 text-sm text-[var(--text-tertiary)]">正在加载 Playbook…</p>
        ) : playbookQuery.data ? (
          <pre className="mt-4 max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-[var(--radius-2)] bg-[var(--surface-canvas)] p-4 text-xs leading-6 text-[var(--text-secondary)]">
            {playbookQuery.data.markdown}
          </pre>
        ) : (
          <p className="mt-4 text-sm text-[var(--state-danger)]">Playbook 加载失败。</p>
        )}
      </section>
      <Link href="/skills" className="text-sm font-semibold text-[var(--action-primary)] hover:underline">返回 Skill 目录</Link>
    </AppShell>
  );
}

function CapabilityRow({ endpoint }: { readonly endpoint: PackageEndpoint }) {
  return (
    <article className="grid gap-3 px-5 py-4 lg:grid-cols-[1fr_auto]">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <code className="text-sm font-semibold text-[var(--text-primary)]">{endpoint.endpoint_type}</code>
          <Status value={endpoint.status} />
          <Tag>{endpoint.method}</Tag>
        </div>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">{endpoint.label}</p>
        <p className="mt-1 text-xs leading-5 text-[var(--text-tertiary)]">{endpoint.description}</p>
      </div>
      <div className="flex max-w-md flex-wrap content-start gap-1.5 lg:justify-end">
        {endpoint.required_params.map((param) => <Param key={param} name={param} required />)}
        {endpoint.optional_params.slice(0, 6).map((param) => <Param key={param} name={param} />)}
      </div>
    </article>
  );
}

function Param({ name, required = false }: { readonly name: string; readonly required?: boolean }) {
  return <span className={`rounded-[var(--radius-1)] border px-2 py-1 font-mono text-[10px] ${required ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] text-[var(--action-primary)]" : "border-[var(--border-subtle)] bg-[var(--surface-muted)] text-[var(--text-tertiary)]"}`}>{name}{required ? " *" : ""}</span>;
}

function Status({ value }: { readonly value: string }) {
  const style = value === "verified" ? "border-[var(--state-success)] bg-[var(--success-soft)] text-[var(--state-success)]" : value === "disabled" ? "border-[var(--border-subtle)] bg-[var(--surface-muted)] text-[var(--text-tertiary)]" : "border-[var(--state-warning)] bg-[var(--warning-soft)] text-[var(--state-warning)]";
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${style}`}>{value}</span>;
}

function Tag({ children }: { readonly children: React.ReactNode }) {
  return <span className="rounded-[var(--radius-1)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-2 py-1 font-mono text-[10px] text-[var(--text-tertiary)]">{children}</span>;
}

function InfoRow({ icon, label, value }: { readonly icon: React.ReactNode; readonly label: string; readonly value: string }) {
  return <div className="border-b border-[var(--border-subtle)] py-3 last:border-0"><div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-secondary)]">{icon}{label}</div><p className="mt-1 break-all font-mono text-[10px] leading-5 text-[var(--text-tertiary)]">{value}</p></div>;
}

function CodePanel({ title, code }: { readonly title: string; readonly code: string }) {
  return <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5"><h2 className="font-bold">{title}</h2><pre className="mt-4 overflow-auto whitespace-pre-wrap rounded-[var(--radius-2)] bg-[var(--surface-canvas)] p-4 text-xs leading-6 text-[var(--text-secondary)]">{code}</pre></section>;
}

function ShellState({ title, text, danger = false }: { readonly title: string; readonly text: string; readonly danger?: boolean }) {
  return <AppShell title={title}><div className={`rounded-[var(--radius-3)] border p-10 text-center text-sm ${danger ? "border-[var(--state-danger)] bg-[var(--danger-soft)] text-[var(--state-danger)]" : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-tertiary)]"}`}>{text}</div></AppShell>;
}
