"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Cable,
  Check,
  ChevronDown,
  Code2,
  Copy,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api/client";
import { Reveal } from "@/components/landing/Reveal";
import { HeroTexture } from "@/components/landing/HeroTexture";
import { AgentSprite } from "@/components/landing/AgentSprite";
import { ConnectDiagram } from "@/components/landing/ConnectDiagram";
import { StatBar } from "@/components/landing/StatBar";
import { ToolWall } from "@/components/landing/ToolWall";
import { TerminalDemo } from "@/components/landing/TerminalDemo";
import { GiantMark } from "@/components/landing/GiantMark";

/** 首屏命令。目录接口公开可读。 */
const CATALOG_COMMAND = `curl -s ${API_BASE_URL}/api/collectors/catalog`;

/** 行动区命令。读取实测计数。 */
const DOCS_COMMAND = `curl -s ${API_BASE_URL}/api/collectors/docs`;

const STEPS = [
  { title: "找能力", body: "按平台或分类筛选全部能力视图。" },
  { title: "发采集", body: "用 REST 或 MCP 提交参数。" },
  { title: "取产物", body: "运行完成后查看记录，导出数据集。" },
];

const ACCESS = [
  {
    icon: Code2,
    title: "REST",
    body: "提交 POST /api/quick-collect。目录与文档都是普通 JSON 接口。",
  },
  {
    icon: Cable,
    title: "MCP",
    body: "服务挂在 /mcp/。5 个工具：查平台、查能力、看能力详情、读文档、发起采集。",
  },
  {
    icon: BookOpen,
    title: "Skill",
    body: "按平台下载 ZIP，装进 Agent 的 Skill 目录。",
  },
];

const FAQ = [
  {
    q: "目录里有多少采集能力？",
    a: "全部能力视图汇总为唯一端点，分若干采集器分组。实时计数见本页统计条，数据来自 GET /api/tool-catalog。",
  },
  {
    q: "这些能力都验证过吗？",
    a: "多数端点有生产实测记录。状态来自最近一次真实运行，不是静态声明。实时计数见本页统计条，数据来自 GET /api/collectors/docs。",
  },
  {
    q: "怎么接入？",
    a: "三种方式：REST、MCP 或 Skill。REST 提交 POST /api/quick-collect。MCP 服务挂在 /mcp/，用 Bearer 令牌鉴权。Skill 按平台下载 ZIP，装进 Agent 的 Skill 目录。细节见「接入」页。",
  },
  {
    q: "采集结果放在哪里？",
    a: "结果写入运行记录与原始记录。到控制台的「运行记录」页查看，也可以导出数据集。",
  },
  {
    q: "端点缺密钥时怎么办？",
    a: "控制台会标出缺失的配置。缺平台密钥或自建服务地址的端点保持不可用；补齐后即可运行。",
  },
];

const FOOTER_COLUMNS = [
  {
    title: "产品",
    links: [
      { label: "工具目录", href: "/tools" },
      { label: "采集文档", href: "/docs" },
      { label: "接入方式", href: "/connect" },
    ],
  },
  {
    title: "控制台",
    links: [
      { label: "工作台", href: "/dashboard" },
      { label: "运行记录", href: "/runs" },
      { label: "数据集", href: "/assets" },
    ],
  },
  {
    title: "更多",
    links: [
      { label: "项目", href: "/projects" },
      { label: "任务", href: "/tasks" },
      { label: "常见问题", href: "#faq" },
    ],
  },
];

/** 可复制的命令条。变体决定底色。 */
function CopyCommand({
  command,
  variant = "surface",
}: {
  command: string;
  variant?: "surface" | "onPrimary";
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 剪贴板不可用。用户可手动选取。
    }
  }

  const shellClass =
    variant === "onPrimary"
      ? "border-transparent bg-[var(--surface-canvas)]"
      : "border-[var(--border-subtle)] bg-[var(--surface-primary)]";

  return (
    <div
      className={`flex items-center gap-2.5 rounded-[var(--radius-3)] border px-4 py-3 ${shellClass}`}
    >
      <span
        aria-hidden="true"
        className="select-none font-mono text-xs text-[var(--text-tertiary)] sm:text-[13px]"
      >
        $
      </span>
      <code className="min-w-0 flex-1 overflow-x-auto whitespace-pre font-mono text-xs text-[var(--text-secondary)] sm:text-[13px]">
        {command}
      </code>
      <button
        type="button"
        onClick={copy}
        aria-label={`复制命令：${command}`}
        className="flex shrink-0 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)]"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
        {copied ? "已复制" : "复制命令"}
      </button>
    </div>
  );
}

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[var(--surface-canvas)] text-[var(--text-primary)]">
      {/* 1. 顶栏 */}
      <header className="sticky top-0 z-40 border-b border-[var(--border-subtle)] bg-[var(--surface-canvas)]">
        <div className="mx-auto flex h-[var(--topbar-height)] w-full max-w-7xl items-center gap-6 px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-2.5">
            <span
              aria-hidden="true"
              className="grid size-8 place-items-center rounded-[var(--radius-2)] bg-[var(--action-primary)] text-[13px] font-bold text-[var(--text-inverse)]"
            >
              DI
            </span>
            <span className="text-sm font-bold">Data Intelligence Hub</span>
          </Link>
          <nav
            aria-label="主导航"
            className="ml-2 hidden items-center gap-6 text-sm text-[var(--text-secondary)] md:flex"
          >
            <Link href="/tools" className="hover:text-[var(--text-primary)]">
              工具
            </Link>
            <Link href="/docs" className="hover:text-[var(--text-primary)]">
              文档
            </Link>
            <Link href="/connect" className="hover:text-[var(--text-primary)]">
              接入
            </Link>
          </nav>
          <Link
            href="/dashboard"
            className="ml-auto rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3.5 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
          >
            打开控制台
          </Link>
        </div>
      </header>

      <main>
        {/* 2. 首屏 */}
        <section className="relative overflow-hidden">
          <HeroTexture />
          <div
            className="relative mx-auto flex w-full max-w-7xl flex-col justify-end px-4 pb-16 pt-24 sm:px-6 lg:px-8"
            style={{ minHeight: "calc(50vh + 130px)" }}
          >
            <Reveal>
              <p className="inline-flex items-center rounded-[var(--radius-pill)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
                数据采集与情报平台
              </p>
            </Reveal>
            <Reveal index={1}>
              <h1 className="mt-5 text-[36px] font-semibold leading-[42px] tracking-[-1px] sm:text-[56px] sm:leading-[62px]">
                把公开网络数据
                <br />
                变成可调用的
                <span className="text-[var(--action-primary)]">数据集</span>
              </h1>
            </Reveal>
            <Reveal index={2}>
              <p className="mt-5 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
                能力视图覆盖社媒、电商、评价、搜索与开放网络。
              </p>
            </Reveal>
            <Reveal index={3}>
              <p className="mt-4 flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <AgentSprite size={26} className="shrink-0" />
                支持 MCP 的 Agent 都能接入：Claude Code、Codex、Cursor。
              </p>
            </Reveal>
            <Reveal index={4} className="mt-7 max-w-xl">
              <CopyCommand command={CATALOG_COMMAND} />
            </Reveal>
            <Reveal index={5}>
              <p className="mt-4 text-xs text-[var(--text-tertiary)]">
                目录无需登录即可读取。接入方式见「接入」页。
              </p>
            </Reveal>
          </div>
        </section>

        {/* 3. 连接区 */}
        <section className="border-t border-[var(--border-subtle)] bg-[var(--surface-primary)] py-24">
          <div className="mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8">
            <Reveal>
              <h2 className="text-[30px] font-semibold leading-[36px] sm:text-[40px] sm:leading-[46px]">
                36 个采集器分组，汇入一张目录
              </h2>
              <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
                采集器负责拿数据。DIH 负责统一目录、运行与产物。
              </p>
            </Reveal>
            <Reveal index={1} className="mt-12">
              <ConnectDiagram className="h-auto w-full" />
            </Reveal>

            <div className="mt-16">
              <Reveal>
                <h3 className="text-lg font-semibold">目录里的前 24 条</h3>
                <p className="mt-2 text-sm text-[var(--text-tertiary)]">
                  数据来自 GET /api/collectors/catalog。
                </p>
              </Reveal>
              <Reveal index={1} className="mt-6">
                <ToolWall />
              </Reveal>
            </div>
          </div>
        </section>

        {/* 4. 三步流程 */}
        <section className="py-24">
          <div className="mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8">
            <Reveal>
              <h2 className="text-[30px] font-semibold leading-[36px] sm:text-[40px] sm:leading-[46px]">
                三步拿到数据
              </h2>
            </Reveal>
            <ol className="mt-12 grid gap-8 md:grid-cols-3">
              {STEPS.map((step, index) => (
                <li key={step.title}>
                  <Reveal index={index}>
                    <div className="border-t-2 border-[var(--border-strong)] pt-6">
                      <span className="text-xs font-semibold text-[var(--action-primary)]">
                        {`0${index + 1}`}
                      </span>
                      <h3 className="mt-2 text-lg font-semibold">{step.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        {step.body}
                      </p>
                    </div>
                  </Reveal>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* 5. 口号与统计 */}
        <section className="border-t border-[var(--border-subtle)] bg-[var(--surface-primary)] py-24">
          <div className="mx-auto w-full max-w-[1100px] px-4 sm:px-6 lg:px-8">
            <Reveal>
              <h2 className="text-[30px] font-semibold leading-[36px] sm:text-[40px] sm:leading-[46px]">
                为 Agent 准备的数据采集层
              </h2>
            </Reveal>
            <Reveal index={0} className="mt-12">
              <StatBar />
            </Reveal>
          </div>
        </section>

        {/* 6. 终端演示 */}
        <section className="py-24">
          <div className="mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8">
            <Reveal>
              <h2 className="text-[30px] font-semibold leading-[36px] sm:text-[40px] sm:leading-[46px]">
                看一次真实运行
              </h2>
              <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
                记录数与耗时直接取自运行记录。
              </p>
            </Reveal>
            <Reveal index={1} className="mt-10">
              <TerminalDemo />
            </Reveal>
          </div>
        </section>

        {/* 7. 接入方式 */}
        <section className="border-t border-[var(--border-subtle)] bg-[var(--surface-primary)] py-24">
          <div className="mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8">
            <Reveal>
              <h2 className="text-[30px] font-semibold leading-[36px] sm:text-[40px] sm:leading-[46px]">
                三种接入方式
              </h2>
            </Reveal>
            <div className="mt-12 grid gap-4 md:grid-cols-3">
              {ACCESS.map((item, index) => {
                const Icon = item.icon;
                return (
                  <Reveal key={item.title} index={index} className="h-full">
                    <Link
                      href="/connect"
                      className="flex h-full flex-col gap-4 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] p-6 transition-colors hover:border-[var(--border-strong)]"
                    >
                      <Icon size={18} className="text-[var(--action-primary)]" />
                      <h3 className="text-lg font-semibold">{item.title}</h3>
                      <p className="text-sm leading-6 text-[var(--text-secondary)]">
                        {item.body}
                      </p>
                      <span className="mt-auto flex items-center gap-1.5 text-sm font-medium text-[var(--action-primary)]">
                        查看接入说明
                        <ArrowRight size={14} />
                      </span>
                    </Link>
                  </Reveal>
                );
              })}
            </div>
          </div>
        </section>

        {/* 8. 行动区 */}
        <section className="bg-[var(--action-primary)] py-24 text-[var(--text-inverse)]">
          <div className="mx-auto w-full max-w-[1100px] px-4 text-center sm:px-6 lg:px-8">
            <Reveal>
              <h2 className="text-[30px] font-semibold leading-[36px] sm:text-[40px] sm:leading-[46px]">
                目录已就绪
              </h2>
              <p className="mt-4 text-base opacity-90">复制命令，先读一遍实测计数。</p>
            </Reveal>
            <Reveal index={1} className="mx-auto mt-10 max-w-xl text-left">
              <CopyCommand command={DOCS_COMMAND} variant="onPrimary" />
            </Reveal>
          </div>
        </section>

        {/* 9. 常见问题 */}
        <section id="faq" className="py-24">
          <div className="mx-auto w-full max-w-[1100px] px-4 sm:px-6 lg:px-8">
            <Reveal>
              <h2 className="text-[30px] font-semibold leading-[36px] sm:text-[40px] sm:leading-[46px]">
                常见问题
              </h2>
            </Reveal>
            <div className="mt-10 border-y border-[var(--border-subtle)]">
              {FAQ.map((item, index) => (
                <div key={item.q} className={index > 0 ? "border-t border-[var(--border-subtle)]" : ""}>
                  <Reveal index={index}>
                    <details className="group py-4">
                      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-medium [&::-webkit-details-marker]:hidden">
                        {item.q}
                        <ChevronDown
                          size={16}
                          aria-hidden="true"
                          className="shrink-0 text-[var(--text-tertiary)] transition-transform group-open:rotate-180 motion-reduce:transition-none"
                        />
                      </summary>
                      <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
                        {item.a}
                      </p>
                    </details>
                  </Reveal>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      {/* 11. 页脚 */}
      <footer className="bg-[var(--surface-terminal)] pt-20 text-[var(--terminal-text)]">
        <div className="mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid gap-10 md:grid-cols-[1.2fr_1fr_1fr_1fr]">
            <div>
              <p className="flex items-center gap-2.5">
                <span
                  aria-hidden="true"
                  className="grid size-8 place-items-center rounded-[var(--radius-2)] bg-[var(--action-primary)] text-[13px] font-bold text-[var(--text-inverse)]"
                >
                  DI
                </span>
                <span className="text-sm font-bold">Data Intelligence Hub</span>
              </p>
              <p className="mt-4 text-sm leading-6 text-[var(--terminal-text-muted)]">
                公开数据采集与目录平台。计数来自生产快照。
              </p>
            </div>
            {FOOTER_COLUMNS.map(column => (
              <nav key={column.title} aria-label={column.title}>
                <h2 className="text-xs font-semibold text-[var(--terminal-text-muted)]">
                  {column.title}
                </h2>
                <ul className="mt-4 grid gap-2.5 text-sm">
                  {column.links.map(link => (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        className="text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)]"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
          <p className="mt-16 text-xs text-[var(--terminal-text-muted)]">
            计数来源：GET /api/collectors/catalog 与 GET /api/collectors/docs。
          </p>
        </div>
        <GiantMark text="Data Intelligence Hub" className="mt-6" />
      </footer>
    </div>
  );
}
