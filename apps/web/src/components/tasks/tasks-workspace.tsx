"use client";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Database,
  FileWarning,
  ListFilter,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  SquareStack,
  TerminalSquare,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listTasks, pauseTask, resumeTask, runTask } from "@/lib/api/tasks";
import { cn } from "@/lib/utils";
import type { CollectionTask, CollectorType, TaskRun } from "@/types/source-task";

type DomainKey = "osint" | "ecommerce" | "social" | "competitor";
type DomainFilter = DomainKey | "all";
type StatusFilter = "all" | "healthy" | "warning" | "failed" | "paused";

type TaskProfile = {
  domain: DomainKey;
  sourceType: string;
  sourceName: string;
  schedule: string;
  nextRun: string;
  latencyMinutes: number;
  records24h: number;
  trend: number[];
  incident?: {
    title: string;
    latestError: string;
    requestId: string;
    sourceId: string;
    generatedSignalId: string;
    alertEventId: string;
    retryHistory: Array<{ time: string; label: string; code: string }>;
  };
};

const domainLabels: Record<DomainKey, string> = {
  osint: "开源雷达",
  ecommerce: "电商风向",
  social: "社媒脉搏",
  competitor: "竞品守望",
};

const collectorLabels: Record<CollectorType, string> = {
  github_repo: "GitHub Repo",
  github_topic: "GitHub Topic",
  generic_web: "网页",
  manual_json: "手动 JSON",
};

const taskProfiles: Record<string, TaskProfile> = {
  task_twitter_keywords: {
    domain: "social",
    sourceType: "社媒",
    sourceName: "Twitter Search Stream",
    schedule: "每 5 分钟",
    nextRun: "16:30:00",
    latencyMinutes: 8,
    records24h: 18420,
    trend: [56, 61, 58, 66, 71, 69, 75],
  },
  task_reddit_hot_posts: {
    domain: "social",
    sourceType: "社媒",
    sourceName: "Reddit Hot API",
    schedule: "每 10 分钟",
    nextRun: "16:30:00",
    latencyMinutes: 12,
    records24h: 12780,
    trend: [43, 46, 52, 50, 55, 57, 61],
  },
  task_amazon_best_sellers: {
    domain: "ecommerce",
    sourceType: "电商",
    sourceName: "Amazon US Best Sellers",
    schedule: "每 30 分钟",
    nextRun: "16:30:00",
    latencyMinutes: 10,
    records24h: 31860,
    trend: [82, 80, 88, 91, 94, 92, 96],
  },
  task_amazon_review_scrape: {
    domain: "ecommerce",
    sourceType: "电商",
    sourceName: "Amazon Review Pages",
    schedule: "每 30 分钟",
    nextRun: "16:30:00",
    latencyMinutes: 15,
    records24h: 22940,
    trend: [76, 74, 80, 78, 82, 85, 84],
  },
  task_google_trends: {
    domain: "osint",
    sourceType: "开源",
    sourceName: "Google Trends",
    schedule: "每 1 小时",
    nextRun: "17:00:00",
    latencyMinutes: 9,
    records24h: 7620,
    trend: [38, 42, 45, 47, 51, 49, 53],
  },
  task_news_site_aggregate: {
    domain: "osint",
    sourceType: "新闻",
    sourceName: "News RSS Mesh",
    schedule: "每 15 分钟",
    nextRun: "16:30:00",
    latencyMinutes: 13,
    records24h: 16840,
    trend: [62, 61, 63, 67, 66, 70, 72],
  },
  task_brand_site_watch: {
    domain: "competitor",
    sourceType: "网页",
    sourceName: "Brand Site Watcher",
    schedule: "每 30 分钟",
    nextRun: "16:30:00",
    latencyMinutes: 18,
    records24h: 4820,
    trend: [31, 34, 33, 36, 40, 38, 42],
  },
  task_google_play_rank: {
    domain: "ecommerce",
    sourceType: "应用商店",
    sourceName: "Google Play Ranking",
    schedule: "每 1 小时",
    nextRun: "17:00:00",
    latencyMinutes: 22,
    records24h: 5420,
    trend: [28, 30, 29, 33, 34, 32, 35],
  },
  task_linkedin_company: {
    domain: "competitor",
    sourceType: "社媒",
    sourceName: "LinkedIn Public API",
    schedule: "每 15 分钟",
    nextRun: "16:30:00",
    latencyMinutes: 42,
    records24h: 3180,
    trend: [51, 48, 45, 42, 36, 31, 28],
    incident: {
      title: "LinkedIn 公司动态",
      latestError:
        "HTTP 429 Too Many Requests. rate limit exceeded for https://www.linkedin.com/company/updates",
      requestId: "8f6b3c2e-4e2a-4a6c-8fa5-9c766f2a1d9b",
      sourceId: "src_10045",
      generatedSignalId: "sig_dq_20250611_0007",
      alertEventId: "alt_20250611_0003",
      retryHistory: [
        { time: "16:15:03", label: "第 3 次重试", code: "429" },
        { time: "16:14:02", label: "第 2 次重试", code: "429" },
        { time: "16:13:01", label: "第 1 次重试", code: "429" },
        { time: "16:12:00", label: "首次请求", code: "429" },
      ],
    },
  },
  task_tiktok_topic: {
    domain: "social",
    sourceType: "社媒",
    sourceName: "TikTok Topic Import",
    schedule: "每 10 分钟",
    nextRun: "16:20:00",
    latencyMinutes: 37,
    records24h: 8920,
    trend: [48, 52, 47, 45, 43, 39, 37],
  },
};

const ingestionTimeline = [
  { time: "16:00", success: 64000, failed: 2200, latency: 17 },
  { time: "18:00", success: 42000, failed: 5200, latency: 48 },
  { time: "20:00", success: 51000, failed: 3400, latency: 22 },
  { time: "22:00", success: 35000, failed: 2700, latency: 34 },
  { time: "00:00", success: 46000, failed: 3100, latency: 18 },
  { time: "02:00", success: 28000, failed: 1900, latency: 16 },
  { time: "04:00", success: 31000, failed: 2100, latency: 13 },
  { time: "06:00", success: 39000, failed: 2600, latency: 21 },
  { time: "08:00", success: 44000, failed: 4200, latency: 27 },
  { time: "10:00", success: 52000, failed: 2900, latency: 18 },
  { time: "12:00", success: 37000, failed: 7600, latency: 45 },
  { time: "14:00", success: 56000, failed: 3300, latency: 19 },
];

const sourceHealthRows = [
  { type: "社媒", osint: 2, ecommerce: null, social: 5, competitor: 2, health: "9 / 10" },
  { type: "电商", osint: null, ecommerce: 4, social: null, competitor: 1, health: "5 / 5" },
  { type: "新闻", osint: 3, ecommerce: null, social: null, competitor: 1, health: "4 / 5" },
  { type: "网页", osint: 4, ecommerce: 1, social: null, competitor: 3, health: "7 / 8" },
  { type: "应用商店", osint: null, ecommerce: 2, social: null, competitor: null, health: "2 / 2" },
];

export function TasksWorkspace() {
  const [tasks, setTasks] = useState<CollectionTask[]>([]);
  const [latestRun, setLatestRun] = useState<TaskRun | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningTaskId, setRunningTaskId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [domainFilter, setDomainFilter] = useState<DomainFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [runLogOpen, setRunLogOpen] = useState(false);
  const [incidentSuppressed, setIncidentSuppressed] = useState(false);

  useEffect(() => {
    let mounted = true;
    listTasks()
      .then((items) => {
        if (mounted) {
          setTasks(items);
          setSelectedTaskId(
            items.find((item) => item.failureCount >= 10)?.id ?? items[0]?.id ?? null,
          );
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load tasks");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const filteredTasks = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    return tasks.filter((task) => {
      const profile = getTaskProfile(task);
      const health = getTaskHealth(task);
      const matchesSearch =
        normalizedSearch.length === 0 ||
        task.name.toLowerCase().includes(normalizedSearch) ||
        profile.sourceName.toLowerCase().includes(normalizedSearch);
      const matchesDomain = domainFilter === "all" || profile.domain === domainFilter;
      const matchesStatus = statusFilter === "all" || health === statusFilter;
      return matchesSearch && matchesDomain && matchesStatus;
    });
  }, [domainFilter, searchTerm, statusFilter, tasks]);

  const selectedTask =
    tasks.find((task) => task.id === selectedTaskId) ?? filteredTasks[0] ?? tasks[0] ?? null;
  const selectedProfile = selectedTask ? getTaskProfile(selectedTask) : null;
  const selectedHealth = selectedTask ? getTaskHealth(selectedTask) : null;

  const summary = useMemo(() => {
    const totalRuns = tasks.reduce((sum, task) => sum + task.successCount + task.failureCount, 0);
    const totalSuccess = tasks.reduce((sum, task) => sum + task.successCount, 0);
    const successRate = totalRuns > 0 ? (totalSuccess / totalRuns) * 100 : 0;
    const runningCount = tasks.filter((task) => getTaskHealth(task) === "healthy").length;
    const failedCount = tasks.filter((task) => getTaskHealth(task) === "failed").length;
    const maxLatency =
      tasks.length > 0
        ? Math.max(...tasks.map((task) => getTaskProfile(task).latencyMinutes))
        : 0;
    const records24h = tasks.reduce((sum, task) => sum + getTaskProfile(task).records24h, 0);
    return { failedCount, maxLatency, records24h, runningCount, successRate };
  }, [tasks]);

  async function run(task: CollectionTask) {
    setError(null);
    setRunningTaskId(task.id);
    setSelectedTaskId(task.id);
    try {
      const taskRun = await runTask(task.id);
      setLatestRun(taskRun);
      setRunLogOpen(true);
      setIncidentSuppressed(false);
      setTasks((current) =>
        current.map((item) => {
          if (item.id !== task.id) {
            return item;
          }
          return {
            ...item,
            failureCount:
              taskRun.status === "failed" ? item.failureCount + 1 : Math.max(item.failureCount - 1, 0),
            successCount:
              taskRun.status === "failed" ? item.successCount : item.successCount + 1,
            lastRunAt: taskRun.finishedAt,
          };
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Task run failed");
    } finally {
      setRunningTaskId(null);
    }
  }

  async function updateTaskStatus(task: CollectionTask, next: "paused" | "enabled") {
    setError(null);
    setSelectedTaskId(task.id);
    try {
      const updated = next === "paused" ? await pauseTask(task.id) : await resumeTask(task.id);
      setTasks((current) => current.map((item) => (item.id === task.id ? updated : item)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Task update failed");
    }
  }

  return (
    <div className="grid w-full min-w-0 max-w-full gap-5 overflow-hidden 2xl:grid-cols-[minmax(0,1fr)_320px]">
      <section className="grid min-w-0 max-w-full gap-5 overflow-hidden">
        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <MetricTile
              delta="+4"
              icon={SquareStack}
              label="运行中任务"
              tone="rose"
              value={`${summary.runningCount} / ${tasks.length || 0}`}
            />
            <MetricTile
              delta="+1.2pp"
              icon={CheckCircle2}
              label="今日成功率"
              tone="green"
              value={`${summary.successRate.toFixed(1)}%`}
            />
            <MetricTile
              delta="-1"
              icon={AlertTriangle}
              label="连续失败"
              tone="red"
              value={summary.failedCount.toString()}
            />
            <MetricTile
              delta="-6 分钟"
              icon={Clock3}
              label="数据延迟 P95"
              tone="blue"
              value={`${summary.maxLatency} 分钟`}
            />
            <MetricTile
              delta="+186"
              icon={Activity}
              label="新信号 24h"
              tone="amber"
              value={(summary.records24h / 100).toFixed(0)}
            />
          </div>
        </div>

        {error ? (
          <p className="rounded-xl border border-[#FFD7DF] bg-[#FFF7F8] px-3 py-2 text-sm text-[#C25B6E]">
            {error}
          </p>
        ) : null}

        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white">
          <div className="flex flex-col gap-4 border-b border-[#EDE6DF] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-base font-semibold text-[#1D1D1F]">任务运行列表</h2>
              <p className="mt-1 text-sm text-[#86868B]">
                监控采集任务、运行状态、成功率与下一次调度
              </p>
            </div>
            <button
              className="inline-flex h-9 items-center justify-center gap-2 self-start rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 text-sm font-medium text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E]"
              onClick={() => {
                setDomainFilter("all");
                setStatusFilter("all");
                setSearchTerm("");
              }}
              type="button"
            >
              <RefreshCw size={16} aria-hidden="true" />
              刷新视图
            </button>
          </div>

          <div className="grid gap-3 border-b border-[#EDE6DF] px-5 py-4 lg:grid-cols-[150px_150px_1fr_120px]">
            <SelectField
              label="业务域"
              onChange={(value) => setDomainFilter(value as DomainFilter)}
              options={[
                { label: "全部业务域", value: "all" },
                { label: "开源雷达", value: "osint" },
                { label: "电商风向", value: "ecommerce" },
                { label: "社媒脉搏", value: "social" },
                { label: "竞品守望", value: "competitor" },
              ]}
              value={domainFilter}
            />
            <SelectField
              label="状态"
              onChange={(value) => setStatusFilter(value as StatusFilter)}
              options={[
                { label: "全部状态", value: "all" },
                { label: "运行中", value: "healthy" },
                { label: "警告", value: "warning" },
                { label: "失败", value: "failed" },
                { label: "已暂停", value: "paused" },
              ]}
              value={statusFilter}
            />
            <label className="flex h-10 items-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 text-sm text-[#86868B]">
              <Search size={16} className="text-[#86868B]" aria-hidden="true" />
              <input
                className="w-full border-0 bg-transparent outline-none"
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="搜索任务名称或数据源..."
                type="search"
                value={searchTerm}
              />
            </label>
            <button
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] text-sm font-medium text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E]"
              type="button"
            >
              <ListFilter size={16} aria-hidden="true" />
              批量操作
            </button>
          </div>

          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead className="bg-[#FBF8F5] text-xs font-semibold text-[#86868B]">
                <tr>
                  <th className="w-10 px-5 py-3">
                    <span className="sr-only">选择</span>
                  </th>
                  <th className="px-3 py-3 whitespace-nowrap">任务名称</th>
                  <th className="px-3 py-3 whitespace-nowrap">数据源类型</th>
                  <th className="px-3 py-3 whitespace-nowrap">业务域</th>
                  <th className="px-3 py-3 whitespace-nowrap">调度策略</th>
                  <th className="px-3 py-3 whitespace-nowrap">最近一次运行</th>
                  <th className="px-3 py-3 whitespace-nowrap">成功率 7d</th>
                  <th className="px-3 py-3 whitespace-nowrap">状态</th>
                  <th className="px-3 py-3 whitespace-nowrap">下次运行</th>
                  <th className="px-5 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EDE6DF]">
                {loading ? (
                  <tr>
                    <td className="px-5 py-8 text-sm text-[#86868B]" colSpan={10}>
                      正在加载采集任务...
                    </td>
                  </tr>
                ) : null}
                {!loading && filteredTasks.length === 0 ? (
                  <tr>
                    <td className="px-5 py-8 text-sm text-[#86868B]" colSpan={10}>
                      当前筛选条件下没有任务
                    </td>
                  </tr>
                ) : null}
                {filteredTasks.map((task) => {
                  const profile = getTaskProfile(task);
                  const health = getTaskHealth(task);
                  const selected = selectedTask?.id === task.id;
                  return (
                    <tr
                      className={cn(
                        "cursor-pointer transition hover:bg-[#FBF8F5]",
                        selected ? "bg-[#FFF7F8]" : "bg-white",
                      )}
                      key={task.id}
                      onClick={() => {
                        setSelectedTaskId(task.id);
                        setIncidentSuppressed(false);
                      }}
                    >
                      <td className="px-5 py-3">
                        <span
                          className={cn(
                            "block h-4 w-4 rounded border",
                            selected
                              ? "border-[#C25B6E] bg-[#C25B6E]"
                              : "border-[#E9E5E2] bg-white",
                          )}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <div className="font-medium text-[#1D1D1F]">{task.name}</div>
                        <div className="mt-1 text-xs text-[#86868B]">{profile.sourceName}</div>
                      </td>
                      <td className="px-3 py-3 text-[#5F5757]">{profile.sourceType}</td>
                      <td className="px-3 py-3 text-[#5F5757]">{domainLabels[profile.domain]}</td>
                      <td className="px-3 py-3 text-[#5F5757]">{profile.schedule}</td>
                      <td className="px-3 py-3 text-[#5F5757]">{formatTime(task.lastRunAt)}</td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-2">
                          <span className="w-12 text-[#5F5757]">{successRate(task).toFixed(1)}%</span>
                          <MiniTrend values={profile.trend} tone={health} />
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <HealthBadge health={health} />
                      </td>
                      <td className="px-3 py-3 text-[#5F5757]">{profile.nextRun}</td>
                      <td className="px-5 py-3">
                        <div className="flex justify-end gap-1.5">
                          <IconButton
                            label="立即运行"
                            onClick={() => void run(task)}
                            pressed={runningTaskId === task.id}
                          >
                            <PlayCircle size={16} aria-hidden="true" />
                          </IconButton>
                          <IconButton
                            label={task.status === "paused" || task.status === "disabled" ? "恢复" : "暂停"}
                            onClick={() =>
                              void updateTaskStatus(
                                task,
                                task.status === "paused" || task.status === "disabled"
                                  ? "enabled"
                                  : "paused",
                              )
                            }
                          >
                            {task.status === "paused" || task.status === "disabled" ? (
                              <RotateCcw size={16} aria-hidden="true" />
                            ) : (
                              <PauseCircle size={16} aria-hidden="true" />
                            )}
                          </IconButton>
                          <IconButton
                            label="日志"
                            onClick={() => {
                              setSelectedTaskId(task.id);
                              setRunLogOpen(true);
                            }}
                          >
                            <TerminalSquare size={16} aria-hidden="true" />
                          </IconButton>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="grid gap-3 px-4 py-4 md:hidden">
            {loading ? <p className="text-sm text-[#86868B]">正在加载采集任务...</p> : null}
            {!loading && filteredTasks.length === 0 ? (
              <p className="text-sm text-[#86868B]">当前筛选条件下没有任务</p>
            ) : null}
            {filteredTasks.map((task) => {
              const profile = getTaskProfile(task);
              const health = getTaskHealth(task);
              const selected = selectedTask?.id === task.id;
              return (
                <div
                  className={cn(
                    "grid gap-3 rounded-2xl border p-3 text-left transition-colors",
                    selected
                      ? "border-[#C25B6E] bg-[#FFF7F8]"
                      : "border-[#EDE6DF] bg-[#FBF8F5]",
                  )}
                  key={task.id}
                  onClick={() => {
                    setSelectedTaskId(task.id);
                    setIncidentSuppressed(false);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedTaskId(task.id);
                      setIncidentSuppressed(false);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <span className="flex items-start justify-between gap-3">
                    <span>
                      <span className="block text-sm font-semibold text-[#1D1D1F]">{task.name}</span>
                      <span className="mt-1 block text-xs text-[#86868B]">{profile.sourceName}</span>
                    </span>
                    <HealthBadge health={health} />
                  </span>
                  <span className="grid grid-cols-2 gap-2 text-xs text-[#5F5757]">
                    <span>业务域：{domainLabels[profile.domain]}</span>
                    <span>调度：{profile.schedule}</span>
                    <span>成功率：{successRate(task).toFixed(1)}%</span>
                    <span>下次：{profile.nextRun}</span>
                  </span>
                  <span className="flex items-center justify-between gap-2 border-t border-[#EDE6DF] pt-3">
                    <span className="text-xs text-[#86868B]">最近运行 {formatTime(task.lastRunAt)}</span>
                    <span className="flex gap-1.5">
                      <IconButton
                        label="立即运行"
                        onClick={() => void run(task)}
                        pressed={runningTaskId === task.id}
                      >
                        <PlayCircle size={16} aria-hidden="true" />
                      </IconButton>
                      <IconButton
                        label="日志"
                        onClick={() => {
                          setSelectedTaskId(task.id);
                          setRunLogOpen(true);
                        }}
                      >
                        <TerminalSquare size={16} aria-hidden="true" />
                      </IconButton>
                    </span>
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="grid min-w-0 max-w-full gap-5 overflow-hidden xl:grid-cols-[0.95fr_1.05fr]">
          <section className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-[#1D1D1F]">数据源健康矩阵</h2>
                <p className="mt-1 text-sm text-[#86868B]">按类型和业务域查看采集可用性</p>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-[#EAF8EE] px-2.5 py-1 text-xs font-semibold text-[#2EBA62]">
                <CheckCircle2 size={14} aria-hidden="true" />
                健康
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-[#86868B]">
                  <tr>
                    <th className="py-2">数据源类型</th>
                    <th className="py-2">开源雷达</th>
                    <th className="py-2">电商风向</th>
                    <th className="py-2">社媒脉搏</th>
                    <th className="py-2">竞品守望</th>
                    <th className="py-2 text-right">总体健康</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EDE6DF]">
                  {sourceHealthRows.map((row) => (
                    <tr key={row.type}>
                      <td className="py-3 font-medium text-[#1D1D1F]">{row.type}</td>
                      <HealthCell value={row.osint} />
                      <HealthCell value={row.ecommerce} />
                      <HealthCell value={row.social} />
                      <HealthCell value={row.competitor} />
                      <td className="py-3 text-right">
                        <span className="rounded-lg bg-[#EAF8EE] px-2 py-1 text-xs font-semibold text-[#2EBA62]">
                          {row.health}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-[#1D1D1F]">原始数据入库趋势（近 24 小时）</h2>
                <p className="mt-1 text-sm text-[#86868B]">成功条数、失败条数与 P95 延迟</p>
              </div>
              <Database size={18} className="text-[#86868B]" aria-hidden="true" />
            </div>
            <div className="grid h-56 grid-cols-12 items-end gap-2 border-b border-l border-[#EDE6DF] px-2 pb-4">
              {ingestionTimeline.map((point) => {
                const successHeight = Math.max(18, (point.success / 70000) * 150);
                const failedHeight = Math.max(6, (point.failed / 8000) * 64);
                return (
                  <div className="flex h-full flex-col items-center justify-end gap-1" key={point.time}>
                    <div className="flex h-[170px] items-end gap-1">
                      <span
                        className="w-2 rounded-t-sm bg-[#C25B6E]"
                        style={{ height: `${successHeight}px` }}
                      />
                      <span
                        className="w-2 rounded-t-sm bg-[#FF3B30]"
                        style={{ height: `${failedHeight}px` }}
                      />
                    </div>
                    <span
                      className="h-1.5 w-1.5 rounded-full bg-[#FF9800]"
                      title={`延迟 ${point.latency} 分钟`}
                    />
                    <span className="text-[10px] text-[#86868B]">{point.time}</span>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
              <TrendStat label="总入库条数" value="1,287,221" />
              <TrendStat label="成功条数" value="1,234,556" />
              <TrendStat label="失败条数" value="52,665" tone="red" />
            </div>
          </section>
        </div>
      </section>

      <aside className="grid min-w-0 max-w-full gap-5 overflow-hidden">
        <section className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white">
          <div className="flex items-center justify-between border-b border-[#EDE6DF] px-5 py-4">
            <div>
              <h2 className="text-base font-semibold text-[#1D1D1F]">失败任务诊断</h2>
              <p className="mt-1 text-sm text-[#86868B]">
                {selectedTask ? selectedTask.name : "选择任务查看诊断"}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <button
                className="rounded-lg border border-[#EDE6DF] bg-[#FBF8F5] p-1.5 text-[#86868B] transition-colors hover:text-[#C25B6E]"
                onClick={() => moveSelection(filteredTasks, selectedTask, setSelectedTaskId, -1)}
                type="button"
              >
                <ChevronDown className="rotate-90" size={16} aria-hidden="true" />
                <span className="sr-only">上一个任务</span>
              </button>
              <button
                className="rounded-lg border border-[#EDE6DF] bg-[#FBF8F5] p-1.5 text-[#86868B] transition-colors hover:text-[#C25B6E]"
                onClick={() => moveSelection(filteredTasks, selectedTask, setSelectedTaskId, 1)}
                type="button"
              >
                <ChevronDown className="-rotate-90" size={16} aria-hidden="true" />
                <span className="sr-only">下一个任务</span>
              </button>
            </div>
          </div>

          {selectedTask && selectedProfile && selectedHealth ? (
            <div className="grid gap-4 px-5 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-[#1D1D1F]">{selectedProfile.sourceName}</p>
                  <p className="mt-1 text-xs text-[#86868B]">
                    {domainLabels[selectedProfile.domain]} · {collectorLabels[selectedTask.collectorType]}
                  </p>
                </div>
                <HealthBadge health={selectedHealth} />
              </div>

              {selectedProfile.incident && !incidentSuppressed ? (
                <div className="rounded-xl border border-[#FFD7DF] bg-[#FFF7F8] p-3">
                  <div className="flex items-start gap-2">
                    <FileWarning size={16} className="mt-0.5 text-[#FF3B30]" aria-hidden="true" />
                    <div>
                      <p className="text-sm font-semibold text-[#C25B6E]">最新错误</p>
                      <p className="mt-1 text-xs leading-5 text-[#7A3D49]">
                        {selectedProfile.incident.latestError}
                      </p>
                      <p className="mt-2 text-xs text-[#9B4A5A]">
                        请求 ID: {selectedProfile.incident.requestId}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-[#BEEBD0] bg-[#EAF8EE] p-3 text-sm text-[#247A45]">
                  当前任务未发现阻塞性异常，最近运行可继续观察。
                </div>
              )}

              <DiagnosticBlock
                icon={Database}
                label="影响的数据源"
                title={selectedProfile.sourceName}
                value={`源 ID: ${selectedProfile.incident?.sourceId ?? selectedTask.sourceId}`}
              />
              <div>
                <h3 className="mb-2 text-sm font-semibold text-[#1D1D1F]">重试历史</h3>
                <div className="grid gap-2">
                  {(selectedProfile.incident?.retryHistory ?? [
                    { time: formatTime(selectedTask.lastRunAt), label: "最近一次运行", code: "200" },
                  ]).map((item) => (
                    <div
                      className="grid grid-cols-[70px_1fr_48px] items-center gap-2 text-xs"
                      key={`${item.time}-${item.label}`}
                    >
                      <span className="text-[#86868B]">{item.time}</span>
                      <span className="text-[#5F5757]">{item.label}</span>
                      <span
                        className={cn(
                          "rounded-lg px-2 py-1 text-center font-semibold",
                          item.code === "200"
                            ? "bg-[#EAF8EE] text-[#2EBA62]"
                            : "bg-[#FFE5E2] text-[#FF3B30]",
                        )}
                      >
                        {item.code}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <DiagnosticBlock
                icon={ShieldAlert}
                label="已生成信号"
                title="数据质量异常"
                value={`信号 ID: ${selectedProfile.incident?.generatedSignalId ?? "sig_health_ok"}`}
              />
              <DiagnosticBlock
                icon={AlertTriangle}
                label="关联预警事件"
                title={selectedProfile.incident ? "数据延迟告警" : "无活跃告警"}
                value={`事件 ID: ${selectedProfile.incident?.alertEventId ?? "none"}`}
              />

              <div className="grid grid-cols-2 gap-2">
                <button
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#C25B6E] text-sm font-semibold text-white transition-colors hover:bg-[#A8495B]"
                  onClick={() => void run(selectedTask)}
                  type="button"
                >
                  <PlayCircle size={16} aria-hidden="true" />
                  立即重试
                </button>
                <button
                  className="inline-flex h-10 items-center justify-center rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] text-sm font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E]"
                  onClick={() => setIncidentSuppressed(true)}
                  type="button"
                >
                  跳过本次
                </button>
              </div>
            </div>
          ) : (
            <div className="px-5 py-8 text-sm text-[#86868B]">暂无诊断对象</div>
          )}
        </section>

        <section className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white">
          <div className="flex items-center justify-between border-b border-[#EDE6DF] px-5 py-4">
            <div>
              <h2 className="text-base font-semibold text-[#1D1D1F]">运行日志</h2>
              <p className="mt-1 text-sm text-[#86868B]">
                {runLogOpen ? "查看最近一次运行详情" : "点击日志按钮展开"}
              </p>
            </div>
            <button
              className="rounded-lg border border-[#EDE6DF] bg-[#FBF8F5] p-1.5 text-[#86868B] transition-colors hover:text-[#C25B6E]"
              onClick={() => setRunLogOpen((current) => !current)}
              type="button"
            >
              {runLogOpen ? <X size={16} aria-hidden="true" /> : <TerminalSquare size={16} aria-hidden="true" />}
              <span className="sr-only">{runLogOpen ? "收起日志" : "展开日志"}</span>
            </button>
          </div>
          {runLogOpen ? (
            <div className="grid gap-2 px-5 py-4">
              {(latestRun?.logs ?? defaultLogs(selectedTask)).map((log, index) => (
                <div
                  className="rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-xs"
                  key={`${log.step}-${index}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold text-[#1D1D1F]">{log.step}</span>
                    <span className="text-[#86868B]">{log.timestamp ?? "刚刚"}</span>
                  </div>
                  <p className="mt-1 leading-5 text-[#5F5757]">{log.message}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="px-5 py-6 text-sm text-[#86868B]">
              日志抽屉已收起。选择任务或点击表格中的日志图标查看运行明细。
            </div>
          )}
        </section>
      </aside>
    </div>
  );
}

function MetricTile({
  delta,
  icon: Icon,
  label,
  tone,
  value,
}: {
  delta: string;
  icon: typeof SquareStack;
  label: string;
  tone: "amber" | "blue" | "green" | "red" | "rose";
  value: string;
}) {
  const toneClasses = {
    amber: "bg-[#FFF4DE] text-[#FF9800]",
    blue: "bg-[#F5F0FF] text-[#6E5CF6]",
    green: "bg-[#EAF8EE] text-[#2EBA62]",
    red: "bg-[#FFE5E2] text-[#FF3B30]",
    rose: "bg-[#FCEBF0] text-[#C25B6E]",
  };
  return (
    <div className="flex items-center gap-3 border-b border-[#EDE6DF] pb-3 sm:border-b-0 sm:border-r sm:pb-0 sm:pr-3 last:sm:border-r-0">
      <span className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-full", toneClasses[tone])}>
        <Icon size={20} aria-hidden="true" />
      </span>
      <span className="min-w-0">
        <span className="block text-xs text-[#86868B]">{label}</span>
        <span className="mt-1 block text-2xl font-semibold leading-none text-[#1D1D1F]">{value}</span>
        <span className="mt-1 block text-xs font-medium text-[#C25B6E]">较昨日 {delta}</span>
      </span>
    </div>
  );
}

function SelectField({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: string }>;
  value: string;
}) {
  return (
    <label className="relative flex h-10 items-center rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] text-sm text-[#5F5757]">
      <span className="sr-only">{label}</span>
      <select
        className="h-full w-full appearance-none rounded-xl border-0 bg-transparent px-3 pr-8 outline-none"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown
        size={16}
        className="pointer-events-none absolute right-3 text-[#86868B]"
        aria-hidden="true"
      />
    </label>
  );
}

function IconButton({
  children,
  label,
  onClick,
  pressed = false,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  pressed?: boolean;
}) {
  return (
    <button
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#EDE6DF] bg-white text-[#86868B] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E]",
        pressed ? "border-[#C25B6E] bg-[#FCEBF0] text-[#C25B6E]" : null,
      )}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      title={label}
      type="button"
    >
      {children}
      <span className="sr-only">{label}</span>
    </button>
  );
}

function HealthBadge({ health }: { health: StatusFilter }) {
  const map: Record<StatusFilter, { label: string; className: string }> = {
    all: { label: "全部", className: "bg-[#FBF8F5] text-[#86868B]" },
    failed: { label: "失败", className: "bg-[#FFE5E2] text-[#FF3B30]" },
    healthy: { label: "运行中", className: "bg-[#EAF8EE] text-[#2EBA62]" },
    paused: { label: "已暂停", className: "bg-[#FBF8F5] text-[#86868B]" },
    warning: { label: "警告", className: "bg-[#FFF4DE] text-[#FF9800]" },
  };
  return (
    <span className={cn("inline-flex rounded-lg px-2.5 py-1 text-xs font-semibold", map[health].className)}>
      {map[health].label}
    </span>
  );
}

function MiniTrend({ tone, values }: { tone: StatusFilter; values: number[] }) {
  const color =
    tone === "failed" ? "bg-[#FF3B30]" : tone === "warning" ? "bg-[#FF9800]" : "bg-[#C25B6E]";
  const max = Math.max(...values);
  return (
    <span className="flex h-7 w-20 items-end gap-0.5" aria-hidden="true">
      {values.map((value, index) => (
        <span
          className={cn("w-1.5 rounded-t-sm", color)}
          key={`${value}-${index}`}
          style={{ height: `${Math.max(6, (value / max) * 24)}px` }}
        />
      ))}
    </span>
  );
}

function HealthCell({ value }: { value: number | null }) {
  return (
    <td className="py-3">
      {value === null ? (
        <span className="text-[#D8D1CD]">-</span>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-[#5F5757]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#C25B6E]" />
          {value}
        </span>
      )}
    </td>
  );
}

function DiagnosticBlock({
  icon: Icon,
  label,
  title,
  value,
}: {
  icon: typeof Database;
  label: string;
  title: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] p-3">
      <div className="flex items-start gap-2">
        <Icon size={16} className="mt-0.5 text-[#C25B6E]" aria-hidden="true" />
        <div>
          <p className="text-xs font-semibold text-[#86868B]">{label}</p>
          <p className="mt-1 text-sm font-semibold text-[#1D1D1F]">{title}</p>
          <p className="mt-1 text-xs text-[#86868B]">{value}</p>
        </div>
      </div>
    </div>
  );
}

function TrendStat({
  label,
  tone = "default",
  value,
}: {
  label: string;
  tone?: "default" | "red";
  value: string;
}) {
  return (
    <div>
      <p className="text-xs text-[#86868B]">{label}</p>
      <p className={cn("mt-1 text-lg font-semibold", tone === "red" ? "text-[#FF3B30]" : "text-[#1D1D1F]")}>
        {value}
      </p>
    </div>
  );
}

function getTaskProfile(task: CollectionTask): TaskProfile {
  return (
    taskProfiles[task.id] ?? {
      domain: "osint",
      sourceType: collectorLabels[task.collectorType],
      sourceName: task.name,
      schedule: task.scheduleCron ?? "手动",
      nextRun: "待调度",
      latencyMinutes: 12,
      records24h: 1200,
      trend: [24, 28, 27, 31, 32, 34, 36],
    }
  );
}

function getTaskHealth(task: CollectionTask): StatusFilter {
  if (task.status === "paused" || task.status === "disabled") {
    return "paused";
  }
  if (task.failureCount >= 10) {
    return "failed";
  }
  if (task.failureCount >= 4) {
    return "warning";
  }
  return "healthy";
}

function successRate(task: CollectionTask) {
  const total = task.successCount + task.failureCount;
  if (total === 0) {
    return 0;
  }
  return (task.successCount / total) * 100;
}

function formatTime(value: string | null) {
  if (!value) {
    return "从未运行";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function moveSelection(
  tasks: CollectionTask[],
  selectedTask: CollectionTask | null,
  setSelectedTaskId: (id: string) => void,
  direction: -1 | 1,
) {
  if (tasks.length === 0) {
    return;
  }
  const currentIndex = selectedTask ? tasks.findIndex((task) => task.id === selectedTask.id) : 0;
  const nextIndex = currentIndex < 0 ? 0 : (currentIndex + direction + tasks.length) % tasks.length;
  setSelectedTaskId(tasks[nextIndex].id);
}

function defaultLogs(task: CollectionTask | null) {
  return [
    {
      step: "scheduler_tick",
      message: task ? `${task.name} 等待下一次调度窗口。` : "等待选择任务。",
      timestamp: "16:15:03",
    },
    {
      step: "health_probe",
      message: "任务健康探针已写入最新状态。",
      timestamp: "16:15:04",
    },
    {
      step: "signal_scan",
      message: "已检查 data_quality_anomaly 触发条件。",
      timestamp: "16:15:06",
    },
  ];
}
