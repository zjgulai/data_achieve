"use client";

import { useState } from "react";
import { BookOpen, Cable, Code2, Copy, Check, ServerCog } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { API_BASE_URL } from "@/lib/api/client";

/** 接入方式。见整合方案 §4.1 的 /connect。 */
const TABS = [
  { key: "rest", label: "REST", icon: Code2 },
  { key: "mcp", label: "MCP", icon: Cable },
  { key: "skill", label: "Skill", icon: BookOpen },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/** 一段可复制的代码。 */
function CodeBlock({ title, code }: { readonly title: string; readonly code: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 剪贴板不可用。用户可手动选取。
    }
  }

  return (
    <div className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] px-4 py-3">
        <h3 className="min-w-0 text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
        <button
          type="button"
          onClick={copy}
          className="flex shrink-0 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)]"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? "已复制" : "复制"}
        </button>
      </div>
      <pre className="overflow-x-auto px-4 py-3 text-xs leading-6 text-[var(--text-secondary)]">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export default function ConnectPage() {
  const [tab, setTab] = useState<TabKey>("rest");

  return (
    <AppShell
      title="接入"
      description="用 REST、MCP 或 Skill 接入采集能力"
      brief="选一种接入方式，复制示例后填入自己的项目与密钥。"
    >
      <div className="flex flex-wrap gap-2">
        {TABS.map(t => {
          const on = tab === t.key;
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              aria-current={on ? "page" : undefined}
              className={[
                "inline-flex items-center gap-1.5 rounded-[var(--radius-2)] border px-3 py-1.5 text-sm font-medium transition-colors",
                on
                  ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]"
                  : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--border-strong)]",
              ].join(" ")}
            >
              <Icon size={13} />
              {t.label}
            </button>
          );
        })}
      </div>

      <div className="grid min-w-0 gap-4">
        {tab === "rest" && (
          <>
            <CodeBlock
              title="发起一次采集"
              code={`curl -X POST ${API_BASE_URL}/api/quick-collect \\
  -H 'Content-Type: application/json' \\
  -d '{
    "project_id": "<project-uuid>",
    "endpoint_type": "anysearch_brand_media",
    "params": { "query": "关键词" }
  }'`}
            />
            <CodeBlock
              title="查目录里的必填参数"
              code={`curl ${API_BASE_URL}/api/tools/anysearch_brand_media`}
            />
          </>
        )}

        {tab === "mcp" && (
          <CodeBlock
            title="MCP 配置"
            code={`{
  "mcpServers": {
    "data-intelligence-hub": {
      "url": "${API_BASE_URL}/mcp/",
      "headers": { "Authorization": "Bearer <SCRAPY_MCP_TOKEN>" }
    }
  }
}`}
          />
        )}

        {tab === "skill" && (
          <>
            <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">安装 Skill</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                到「工具」页选一个平台，下载 Skill ZIP。
                解压到 Agent 的 Skill 目录即可。
              </p>
              <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
                {[
                  ["Claude Code", "~/.claude/skills/<platform>-collector/"],
                  ["Codex", "~/.agents/skills/<platform>-collector/"],
                  ["OpenCode", "~/.config/opencode/skills/<platform>-collector/"],
                  ["Cursor", "项目 .cursor/skills/<platform>-collector/"],
                ].map(([name, path]) => (
                  <div key={name}>
                    <dt className="font-semibold text-[var(--text-secondary)]">{name}</dt>
                    <dd className="mt-0.5 break-all font-mono text-[var(--text-tertiary)]">{path}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] p-4 text-xs leading-6 text-[var(--text-tertiary)]">
              <p className="flex items-center gap-1.5 font-semibold text-[var(--text-secondary)]">
                <ServerCog size={13} />
                密钥只在服务端保存
              </p>
              <p className="mt-1">
                Skill 与 MCP 都不携带平台密钥。缺密钥时请到「凭证设置」补配置。
              </p>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
