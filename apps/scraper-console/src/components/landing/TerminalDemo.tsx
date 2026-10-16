"use client";

import { useEffect, useRef, useState } from "react";

/**
 * 回放内容。
 *
 * 全部来自生产运行记录（TaskRun）。
 * run id 截断；不含令牌、项目 id 与原始内容。
 */
const FEATURED = {
  run: "8898be69",
  endpoint: "aliens_eye_advanced",
  records: "5,032",
  seconds: "390.6",
};

const LINES = [
  "$ curl -X POST \"$DIH/api/quick-collect\" \\",
  "    -H \"Authorization: Bearer ••••\" \\",
  "    -d '{\"endpoint_type\":\"aliens_eye_advanced\",\"params\":{\"username\":\"<用户名>\"}}'",
  `· 已受理 · run ${FEATURED.run}…（queued）`,
  "· 状态 running",
  `· 状态 success · ${FEATURED.records} 条记录 · ${FEATURED.seconds} 秒`,
  "$ dih runs tail --limit 3",
  "54757eea…  aliens_eye_batch             success   556 条 · 34.3 秒",
  "ebabcdfb…  apify_amazon_reviews_axesso  success    10 条 · 13.1 秒",
  "35167b1a…  apify_shopify_store_leads    success    10 条 ·  7.4 秒",
];

/** 成功行的下标。右侧统计在它出现后显示。 */
const SUCCESS_LINE_INDEX = 5;

const LINE_INTERVAL_MS = 640;

function lineClass(index: number): string {
  if (index === SUCCESS_LINE_INDEX) return "text-[var(--terminal-success)]";
  if (LINES[index].startsWith("$")) return "text-[var(--terminal-text)]";
  return "text-[var(--terminal-text-muted)]";
}

function revealClass(shown: boolean): string {
  return shown ? "landing-term-line is-shown" : "landing-term-line";
}

/**
 * 终端演示。
 *
 * 深色卡加等宽字体，逐行显示真实运行日志的脱敏回放。
 * 右侧列显示记录数与耗时。DIH 没有计费概念，这里不出现余额。
 * 禁止动效时一次显示全部行。
 */
export function TerminalDemo() {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(0);

  useEffect(() => {
    const el = ref.current;
    // 禁止动效时一次显示全部行。用 timeout 异步置位，避开同步 setState。
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const timer = window.setTimeout(() => setVisible(LINES.length), 0);
      return () => window.clearTimeout(timer);
    }

    let timer: number | undefined;

    function start() {
      timer = window.setInterval(() => {
        setVisible(count => {
          if (count >= LINES.length) {
            if (timer !== undefined) window.clearInterval(timer);
            return count;
          }
          return count + 1;
        });
      }, LINE_INTERVAL_MS);
    }

    if (typeof IntersectionObserver === "undefined" || !el) {
      start();
      return () => {
        if (timer !== undefined) window.clearInterval(timer);
      };
    }

    const observer = new IntersectionObserver(
      entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          start();
          observer.disconnect();
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(el);
    return () => {
      observer.disconnect();
      if (timer !== undefined) window.clearInterval(timer);
    };
  }, []);

  const statsShown = visible > SUCCESS_LINE_INDEX;

  return (
    <div>
      <div
        ref={ref}
        className="grid overflow-hidden rounded-[var(--radius-4)] border border-[var(--border-subtle)] bg-[var(--surface-terminal)] lg:grid-cols-[minmax(0,1fr)_272px]"
      >
        <div className="min-w-0 p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <span className="flex gap-1.5" aria-hidden="true">
              <span className="size-2 rounded-full bg-[var(--terminal-text-muted)] opacity-40" />
              <span className="size-2 rounded-full bg-[var(--terminal-text-muted)] opacity-40" />
              <span className="size-2 rounded-full bg-[var(--terminal-text-muted)] opacity-40" />
            </span>
            <p className="text-xs font-medium text-[var(--terminal-text-muted)]">
              采集回放 · 已脱敏
            </p>
          </div>

          <div className="mt-4 overflow-x-auto">
            <div className="whitespace-pre font-mono text-[13px] leading-6">
              {LINES.map((line, index) => (
                <div
                  key={index}
                  className={`${revealClass(index < visible)} ${lineClass(index)}`}
                >
                  {line}
                </div>
              ))}
            </div>
          </div>
        </div>

        <aside className="flex flex-col justify-center gap-6 border-t border-[var(--terminal-divider)] p-5 sm:p-6 lg:border-l lg:border-t-0">
          <div className={revealClass(statsShown)}>
            <p className="text-xs text-[var(--terminal-text-muted)]">记录数</p>
            <p className="mt-1 text-3xl font-semibold tabular-nums text-[var(--terminal-text)]">
              {FEATURED.records}
            </p>
          </div>
          <div className={revealClass(statsShown)}>
            <p className="text-xs text-[var(--terminal-text-muted)]">耗时</p>
            <p className="mt-1 text-3xl font-semibold tabular-nums text-[var(--terminal-text)]">
              {FEATURED.seconds}
              <span className="ml-1 text-sm font-normal text-[var(--terminal-text-muted)]">
                秒
              </span>
            </p>
          </div>
          <p className={`${revealClass(statsShown)} text-xs text-[var(--terminal-text-muted)]`}>
            状态 success · 2026-10-13 12:28 UTC
          </p>
        </aside>
      </div>

      <p className="mt-3 text-xs text-[var(--text-tertiary)]">
        回放自生产运行记录（TaskRun），2026-10-13 至 10-14。run id 已截断。
      </p>
    </div>
  );
}
