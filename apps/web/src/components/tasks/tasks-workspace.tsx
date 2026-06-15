"use client";

import {
  Activity,
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Database,
  FileWarning,
  ListFilter,
  PauseCircle,
  PlayCircle,
  RadioTower,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  SquareStack,
  TerminalSquare,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  getSchedulerOverview,
  listTaskRuns,
  listTasks,
  pauseTask,
  resumeTask,
  runTask,
} from "@/lib/api/tasks";
import { isTrainingTask } from "@/lib/training-data";
import { useTrainingOverview } from "@/lib/use-training-overview";
import { cn } from "@/lib/utils";
import type {
  CollectionTask,
  CollectorType,
  SchedulerOverview,
  TaskRun,
} from "@/types/source-task";

type DomainKey =
  | "osint"
  | "ecommerce"
  | "social"
  | "competitor"
  | "agent"
  | "platform"
  | "governance";
type DomainFilter = DomainKey | "all";
type StatusFilter = "all" | "healthy" | "warning" | "failed" | "paused";
type TaskScope = "all" | "training";

type TaskProfile = {
  domain: DomainKey;
  sourceType: string;
  sourceName: string;
  schedule: string;
  nextRun: string;
  latencyMinutes: number;
  records24h: number;
  trend: number[];
};

const domainLabels: Record<DomainKey, string> = {
  osint: "开源雷达",
  ecommerce: "电商风向",
  social: "社媒脉搏",
  competitor: "竞品守望",
  agent: "Agent 生态",
  platform: "平台采集",
  governance: "合规边界",
};

const collectorLabels: Record<CollectorType, string> = {
  github_repo: "GitHub Repo",
  github_topic: "GitHub Topic",
  generic_web: "网页",
  manual_json: "手动 JSON",
};

export function TasksWorkspace() {
  const [tasks, setTasks] = useState<CollectionTask[]>([]);
  const [schedulerOverview, setSchedulerOverview] = useState<SchedulerOverview | null>(null);
  const [latestRun, setLatestRun] = useState<TaskRun | null>(null);
  const [taskRuns, setTaskRuns] = useState<TaskRun[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [runLoading, setRunLoading] = useState(false);
  const [runningTaskId, setRunningTaskId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [domainFilter, setDomainFilter] = useState<DomainFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [taskScope, setTaskScope] = useState<TaskScope>("all");
  const [runLogOpen, setRunLogOpen] = useState(false);
  const [incidentSuppressed, setIncidentSuppressed] = useState(false);
  const trainingOverview = useTrainingOverview();

  useEffect(() => {
    let mounted = true;
    Promise.all([listTasks(), getSchedulerOverview()])
      .then(([items, scheduler]) => {
        if (mounted) {
          setTasks(items);
          setSchedulerOverview(scheduler);
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
      const matchesScope = taskScope === "all" || isTrainingTask(task);
      const matchesSearch =
        normalizedSearch.length === 0 ||
        task.name.toLowerCase().includes(normalizedSearch) ||
        profile.sourceName.toLowerCase().includes(normalizedSearch);
      const matchesDomain = domainFilter === "all" || profile.domain === domainFilter;
      const matchesStatus = statusFilter === "all" || health === statusFilter;
      return matchesScope && matchesSearch && matchesDomain && matchesStatus;
    });
  }, [domainFilter, searchTerm, statusFilter, taskScope, tasks]);

  const selectedTask =
    filteredTasks.find((task) => task.id === selectedTaskId) ?? filteredTasks[0] ?? tasks[0] ?? null;
  const selectedProfile = selectedTask ? getTaskProfile(selectedTask) : null;
  const selectedHealth = selectedTask ? getTaskHealth(selectedTask) : null;
  const selectedIssue = selectedTask ? getTaskIssue(selectedTask) : null;
  const selectedTaskRunId = selectedTask?.id ?? null;
  const selectedTaskRuns = useMemo(() => {
    if (!selectedTask) {
      return [];
    }
    const history = taskRuns.filter((runItem) => runItem.taskId === selectedTask.id);
    if (latestRun?.taskId === selectedTask.id && !history.some((item) => item.id === latestRun.id)) {
      return [latestRun, ...history];
    }
    return history;
  }, [latestRun, selectedTask, taskRuns]);
  const activeRun = selectedTaskRuns[0] ?? null;

  useEffect(() => {
    if (!runLogOpen || !selectedTaskRunId) {
      return;
    }
    void loadTaskRuns(selectedTaskRunId);
  }, [runLogOpen, selectedTaskRunId]);

  const summary = useMemo(() => {
    const totalRuns = tasks.reduce((sum, task) => sum + task.successCount + task.failureCount, 0);
    const totalSuccess = tasks.reduce((sum, task) => sum + task.successCount, 0);
    const successRate = totalRuns > 0 ? (totalSuccess / totalRuns) * 100 : 0;
    const enabledCount = tasks.filter((task) => task.status === "enabled").length;
    const failedCount = tasks.filter((task) => getTaskHealth(task) === "failed").length;
    const staleCount = tasks.filter((task) => getTaskHealth(task) === "warning").length;
    const maxLatency =
      tasks.length > 0
        ? Math.max(...tasks.map((task) => getTaskProfile(task).latencyMinutes))
        : 0;
    const latestRecords = tasks.reduce(
      (sum, task) => sum + (task.latestRunRecordsCount ?? 0),
      0,
    );
    return { enabledCount, failedCount, latestRecords, maxLatency, staleCount, successRate };
  }, [tasks]);
  const trainingTasks = useMemo(() => tasks.filter((task) => isTrainingTask(task)), [tasks]);
  const sourceHealthRows = useMemo(() => buildSourceHealthRows(tasks), [tasks]);
  const ingestionTimeline = useMemo(() => buildIngestionTimeline(tasks), [tasks]);

  async function run(task: CollectionTask) {
    setError(null);
    setNotice(null);
    if (task.status !== "enabled") {
      setError("Task must be enabled before manual run");
      return;
    }
    setRunningTaskId(task.id);
    setSelectedTaskId(task.id);
    try {
      const taskRun = await runTask(task.id);
      setLatestRun(taskRun);
      setTaskRuns((current) => [taskRun, ...current.filter((item) => item.id !== taskRun.id)]);
      setRunLogOpen(true);
      setIncidentSuppressed(false);
      setNotice(`${task.name}: run ${taskRun.status}`);
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
            lastRunAt: taskRun.finishedAt ?? taskRun.startedAt,
            freshnessStatus: taskRun.status === "failed" ? "failed" : "fresh",
            nextRunAt: nextRunAfterManualRun(item, taskRun),
            retryAfterAt: retryAfterManualRun(item, taskRun),
            staleHours: taskRun.status === "failed" ? item.staleHours : 0,
            latestRunStatus: taskRun.status,
            latestRunErrorMessage: taskRun.errorMessage,
            latestRunRecordsCount: taskRun.recordsCount,
            latestRunEntitiesCount: taskRun.entitiesCount,
            latestRunStartedAt: taskRun.startedAt,
            latestRunFinishedAt: taskRun.finishedAt,
            latestRunCreatedAt: taskRun.createdAt,
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
    setNotice(null);
    setSelectedTaskId(task.id);
    try {
      const updated = next === "paused" ? await pauseTask(task.id) : await resumeTask(task.id);
      setTasks((current) => current.map((item) => (item.id === task.id ? updated : item)));
      setNotice(`${task.name}: ${next === "paused" ? "paused" : "resumed"}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Task update failed");
    }
  }

  async function loadTaskRuns(taskId: string) {
    setRunLoading(true);
    try {
      const runs = await listTaskRuns(taskId);
      setTaskRuns(runs);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load task runs");
    } finally {
      setRunLoading(false);
    }
  }

  function openRunLog(task: CollectionTask) {
    setSelectedTaskId(task.id);
    setRunLogOpen(true);
    void loadTaskRuns(task.id);
  }

  return (
    <div className="grid w-full min-w-0 max-w-full gap-5 overflow-hidden 2xl:grid-cols-[minmax(0,1fr)_320px]">
      <section className="grid min-w-0 max-w-full gap-5 overflow-hidden">
        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <MetricTile
              caption={`${tasks.length || 0} 个总任务`}
              icon={SquareStack}
              label="启用任务"
              tone="rose"
              value={`${summary.enabledCount} / ${tasks.length || 0}`}
            />
            <MetricTile
              caption="累计成功 / 总运行"
              icon={CheckCircle2}
              label="累计成功率"
              tone="green"
              value={`${summary.successRate.toFixed(1)}%`}
            />
            <MetricTile
              caption="最近一次运行失败"
              icon={AlertTriangle}
              label="失败任务"
              tone="red"
              value={summary.failedCount.toString()}
            />
            <MetricTile
              caption={`${summary.staleCount} 个需刷新`}
              icon={Clock3}
              label="最大数据延迟"
              tone="blue"
              value={`${summary.maxLatency} 分钟`}
            />
            <MetricTile
              caption="最近一次任务输出"
              icon={Activity}
              label="最新记录数"
              tone="amber"
              value={summary.latestRecords.toString()}
            />
            <MetricTile
              caption={`${trainingOverview.overview?.metrics.evidenceCount ?? 0} 条证据`}
              icon={BookOpenCheck}
              label="培训任务"
              tone="rose"
              value={trainingTasks.length.toString()}
            />
          </div>
          <SchedulerObservationPanel overview={schedulerOverview} />
          <p className="mt-3 rounded-xl border border-[#F1D9A8] bg-[#FFF9E9] px-3 py-2 text-xs leading-5 text-[#87611B]">
            培训闭环：训练任务负责刷新工具、平台方法和风险边界，输出进入数据源、原始证据、情报和培训报告。
            {trainingOverview.loading ? " 正在同步培训资产指标。" : null}
          </p>
        </div>

        {error ? (
          <p className="rounded-xl border border-[#FFD7DF] bg-[#FFF7F8] px-3 py-2 text-sm text-[#C25B6E]">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="rounded-xl border border-[#BEEBD0] bg-[#EAF8EE] px-3 py-2 text-sm text-[#247A45]">
            {notice}
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
                setTaskScope("all");
                setSearchTerm("");
              }}
              type="button"
            >
              <RefreshCw size={16} aria-hidden="true" />
              刷新视图
            </button>
          </div>

          <div className="flex flex-wrap gap-2 border-b border-[#EDE6DF] px-5 py-3">
            {(["all", "training"] as const).map((scope) => (
              <button
                className={cn(
                  "inline-flex h-9 items-center gap-2 rounded-xl border px-3 text-xs font-semibold transition-colors",
                  taskScope === scope
                    ? "border-[#C25B6E] bg-[#C25B6E] text-white"
                    : "border-[#EDE6DF] bg-[#FBF8F5] text-[#5F5757] hover:border-[#C25B6E]",
                )}
                key={scope}
                onClick={() => setTaskScope(scope)}
                type="button"
              >
                {scope === "training" ? <BookOpenCheck size={14} aria-hidden="true" /> : null}
                {scope === "training" ? `培训任务 ${trainingTasks.length}` : "全部任务"}
              </button>
            ))}
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
                { label: "Agent 生态", value: "agent" },
                { label: "平台采集", value: "platform" },
                { label: "合规边界", value: "governance" },
              ]}
              value={domainFilter}
            />
            <SelectField
              label="状态"
              onChange={(value) => setStatusFilter(value as StatusFilter)}
              options={[
                { label: "全部状态", value: "all" },
                { label: "新鲜", value: "healthy" },
                { label: "需刷新", value: "warning" },
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
                  <th className="px-3 py-3 whitespace-nowrap">刷新目标</th>
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
                      <td className="px-3 py-3 text-[#5F5757]">
                        {formatTime(task.latestRunFinishedAt ?? task.lastRunAt)}
                      </td>
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
                            disabled={task.status !== "enabled" || runningTaskId === task.id}
                            label="立即运行"
                            onClick={() => void run(task)}
                            pressed={runningTaskId === task.id}
                          >
                            <PlayCircle size={16} aria-hidden="true" />
                          </IconButton>
                          <IconButton
                            disabled={runningTaskId === task.id}
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
                            onClick={() => openRunLog(task)}
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
                    <span>刷新：{profile.nextRun}</span>
                  </span>
                  <span className="flex items-center justify-between gap-2 border-t border-[#EDE6DF] pt-3">
                    <span className="text-xs text-[#86868B]">
                      最近运行 {formatTime(task.latestRunFinishedAt ?? task.lastRunAt)}
                    </span>
                    <span className="flex gap-1.5">
                      <IconButton
                        disabled={task.status !== "enabled" || runningTaskId === task.id}
                        label="立即运行"
                        onClick={() => void run(task)}
                        pressed={runningTaskId === task.id}
                      >
                        <PlayCircle size={16} aria-hidden="true" />
                      </IconButton>
                      <IconButton
                        disabled={runningTaskId === task.id}
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
                        onClick={() => openRunLog(task)}
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
                <p className="mt-1 text-sm text-[#86868B]">按真实任务类型和项目域查看采集可用性</p>
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
                    <th className="py-2">Agent</th>
                    <th className="py-2">平台</th>
                    <th className="py-2">合规</th>
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
                      <HealthCell value={row.agent} />
                      <HealthCell value={row.platform} />
                      <HealthCell value={row.governance} />
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
                <h2 className="text-base font-semibold text-[#1D1D1F]">最近任务运行分布</h2>
                <p className="mt-1 text-sm text-[#86868B]">按任务最新运行结果聚合 records、失败标记与延迟</p>
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
              <TrendStat label="最新 records" value={summary.latestRecords.toString()} />
              <TrendStat label="新鲜任务" value={tasks.filter((task) => getTaskHealth(task) === "healthy").length.toString()} />
              <TrendStat label="需处理任务" value={(summary.failedCount + summary.staleCount).toString()} tone="red" />
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

              {selectedIssue && !incidentSuppressed ? (
                <div className="rounded-xl border border-[#FFD7DF] bg-[#FFF7F8] p-3">
                  <div className="flex items-start gap-2">
                    <FileWarning size={16} className="mt-0.5 text-[#FF3B30]" aria-hidden="true" />
                    <div>
                      <p className="text-sm font-semibold text-[#C25B6E]">{selectedIssue.title}</p>
                      <p className="mt-1 text-xs leading-5 text-[#7A3D49]">
                        {selectedIssue.detail}
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
                value={`源 ID: ${selectedTask.sourceId}`}
              />
              <div>
                <h3 className="mb-2 text-sm font-semibold text-[#1D1D1F]">重试历史</h3>
                <div className="grid gap-2">
                  {runHistoryRows(selectedTask, selectedTaskRuns).map((item) => (
                    <div
                      className="grid grid-cols-[70px_1fr_48px] items-center gap-2 text-xs"
                      key={`${item.time}-${item.label}`}
                    >
                      <span className="text-[#86868B]">{item.time}</span>
                      <span className="text-[#5F5757]">{item.label}</span>
                      <span
                        className={cn(
                          "rounded-lg px-2 py-1 text-center font-semibold",
                          item.code === "OK"
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
                label="新鲜度状态"
                title={freshnessStatusLabel(selectedTask)}
                value={`目标 ${selectedTask.freshnessTargetHours}h · 过期 ${formatStaleHours(selectedTask.staleHours)}`}
              />
              <DiagnosticBlock
                icon={Clock3}
                label="执行计划"
                title={schedulePolicyLabel(selectedTask)}
                value={schedulePlanValue(selectedTask)}
              />
              <DiagnosticBlock
                icon={AlertTriangle}
                label="最近运行输出"
                title={selectedTask.latestRunStatus ? runStatusLabel(selectedTask.latestRunStatus) : "无运行记录"}
                value={`${selectedTask.latestRunRecordsCount ?? 0} records · ${selectedTask.latestRunEntitiesCount ?? 0} entities`}
              />

              <div className="grid grid-cols-2 gap-2">
                <button
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#C25B6E] text-sm font-semibold text-white transition-colors hover:bg-[#A8495B] disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={runningTaskId === selectedTask.id}
                  onClick={() =>
                    void (selectedTask.status === "paused" || selectedTask.status === "disabled"
                      ? updateTaskStatus(selectedTask, "enabled")
                      : run(selectedTask))
                  }
                  type="button"
                >
                  {selectedTask.status === "paused" || selectedTask.status === "disabled" ? (
                    <RotateCcw size={16} aria-hidden="true" />
                  ) : (
                    <PlayCircle size={16} aria-hidden="true" />
                  )}
                  {selectedTask.status === "paused" || selectedTask.status === "disabled"
                    ? "恢复任务"
                    : "立即重试"}
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
              {runLoading ? (
                <p className="rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-xs text-[#86868B]">
                  正在加载运行历史...
                </p>
              ) : null}
              {activeRun ? (
                <div className="rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] p-3 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-[#1D1D1F]">最近一次运行详情</span>
                    <span
                      className={cn(
                        "rounded-lg px-2 py-1 font-semibold",
                        activeRun.status === "failed"
                          ? "bg-[#FFE5E2] text-[#FF3B30]"
                          : "bg-[#EAF8EE] text-[#2EBA62]",
                      )}
                    >
                      {activeRun.status}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <RunFact label="Records" value={String(activeRun.recordsCount)} />
                    <RunFact label="Entities" value={String(activeRun.entitiesCount)} />
                    <RunFact label="Started" value={formatTime(activeRun.startedAt)} />
                    <RunFact label="Finished" value={formatTime(activeRun.finishedAt)} />
                  </div>
                  {activeRun.errorMessage ? (
                    <p className="mt-3 rounded-lg bg-[#FFF7F8] px-2 py-1 text-[#C25B6E]">
                      {activeRun.errorMessage}
                    </p>
                  ) : null}
                </div>
              ) : null}
              {(activeRun?.logs ?? defaultLogs(selectedTask)).map((log, index) => (
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
              <div>
                <h3 className="mb-2 mt-2 text-sm font-semibold text-[#1D1D1F]">运行历史</h3>
                <div className="grid gap-2">
                  {selectedTaskRuns.length > 0 ? (
                    selectedTaskRuns.slice(0, 5).map((runItem) => (
                      <div
                        className="grid grid-cols-[1fr_auto] gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 py-2 text-xs"
                        key={runItem.id}
                      >
                        <span className="min-w-0">
                          <span className="block truncate font-semibold text-[#1D1D1F]">
                            {runItem.id}
                          </span>
                          <span className="mt-1 block text-[#86868B]">
                            {formatTime(runItem.startedAt)} 至 {formatTime(runItem.finishedAt)}
                          </span>
                        </span>
                        <span className="text-right text-[#5F5757]">
                          {runItem.status}
                          <br />
                          {runItem.recordsCount} records
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-xs text-[#86868B]">
                      暂无运行历史
                    </p>
                  )}
                </div>
              </div>
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
  caption,
  icon: Icon,
  label,
  tone,
  value,
}: {
  caption: string;
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
        <span className="mt-1 block text-xs font-medium text-[#C25B6E]">{caption}</span>
      </span>
    </div>
  );
}

function SchedulerObservationPanel({ overview }: { overview: SchedulerOverview | null }) {
  const latestTick = overview?.latestTick ?? null;
  const statusTone =
    !overview?.enabled || !latestTick
      ? "text-[#86868B]"
      : latestTick.status === "completed" && latestTick.taskErrors + latestTick.reportSubscriptionErrors === 0
        ? "text-[#2EBA62]"
        : "text-[#FF9800]";
  return (
    <div className="mt-4 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] p-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-[#C25B6E]">
            <RadioTower size={18} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-[#1D1D1F]">自动调度观测</h3>
              <span className={cn("text-xs font-semibold", statusTone)}>
                {schedulerStatusLabel(overview)}
              </span>
            </div>
            <p className="mt-1 text-xs leading-5 text-[#86868B]">
              {latestTick
                ? `最近 tick ${formatDateTime(latestTick.finishedAt)} · lease ${
                    latestTick.lockAcquired ? "已获取" : "被占用"
                  }`
                : "等待 scheduler 产生首次 tick 记录"}
            </p>
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-4 lg:min-w-[520px]">
          <SchedulerFact
            label="扫描 / 到期"
            value={latestTick ? `${latestTick.scanned} / ${latestTick.due}` : "0 / 0"}
          />
          <SchedulerFact
            label="启动 / 异常"
            tone={latestTick && latestTick.taskErrors > 0 ? "red" : "default"}
            value={
              latestTick
                ? `${latestTick.started} / ${latestTick.taskErrors}`
                : "0 / 0"
            }
          />
          <SchedulerFact
            label="跳过调度"
            value={
              latestTick
                ? `${latestTick.skippedRunning + latestTick.skippedInvalidSchedule}`
                : "0"
            }
          />
          <SchedulerFact
            label="报告队列"
            tone={latestTick && latestTick.reportSubscriptionErrors > 0 ? "red" : "default"}
            value={
              latestTick
                ? `${latestTick.reportSubscriptionsStarted} / ${latestTick.reportSubscriptionErrors}`
                : "0 / 0"
            }
          />
        </div>
      </div>
    </div>
  );
}

function SchedulerFact({
  label,
  tone = "default",
  value,
}: {
  label: string;
  tone?: "default" | "red";
  value: string;
}) {
  return (
    <div className="rounded-lg bg-white px-2 py-2">
      <p className="text-[10px] font-semibold uppercase text-[#86868B]">{label}</p>
      <p className={cn("mt-1 text-sm font-semibold", tone === "red" ? "text-[#FF3B30]" : "text-[#1D1D1F]")}>
        {value}
      </p>
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
  disabled = false,
  label,
  onClick,
  pressed = false,
}: {
  children: React.ReactNode;
  disabled?: boolean;
  label: string;
  onClick: () => void;
  pressed?: boolean;
}) {
  return (
    <button
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#EDE6DF] bg-white text-[#86868B] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E]",
        disabled ? "cursor-not-allowed opacity-45 hover:border-[#EDE6DF] hover:text-[#86868B]" : null,
        pressed ? "border-[#C25B6E] bg-[#FCEBF0] text-[#C25B6E]" : null,
      )}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        if (disabled) {
          return;
        }
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
    healthy: { label: "新鲜", className: "bg-[#EAF8EE] text-[#2EBA62]" },
    paused: { label: "已暂停", className: "bg-[#FBF8F5] text-[#86868B]" },
    warning: { label: "需刷新", className: "bg-[#FFF4DE] text-[#FF9800]" },
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

function RunFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white px-2 py-1">
      <p className="text-[10px] font-semibold uppercase text-[#86868B]">{label}</p>
      <p className="mt-1 break-words text-xs font-semibold text-[#1D1D1F]">{value}</p>
    </div>
  );
}

function getTaskProfile(task: CollectionTask): TaskProfile {
  return {
    domain: normalizeDomain(task.projectDomain),
    sourceType: collectorLabels[task.collectorType],
    sourceName: task.sourceName ?? task.name,
    schedule: formatSchedule(task),
    nextRun: formatNextRun(task),
    latencyMinutes: taskLatencyMinutes(task),
    records24h: task.latestRunRecordsCount ?? 0,
    trend: buildTaskTrend(task),
  };
}

function getTaskHealth(task: CollectionTask): StatusFilter {
  if (task.status === "paused" || task.status === "disabled") {
    return "paused";
  }
  if (task.freshnessStatus === "failed" || task.latestRunStatus === "failed") {
    return "failed";
  }
  if (task.freshnessStatus === "stale" || task.freshnessStatus === "never_run") {
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

function formatTime(value: string | null | undefined) {
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

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(date);
}

function normalizeDomain(value: string | null | undefined): DomainKey {
  if (
    value === "ecommerce" ||
    value === "social" ||
    value === "competitor" ||
    value === "agent" ||
    value === "platform" ||
    value === "governance"
  ) {
    return value;
  }
  return "osint";
}

function formatSchedule(task: CollectionTask) {
  if (!task.scheduleCron) {
    return task.schedulePolicy === "auto_freshness" ? "自动保鲜" : "手动";
  }
  const labels: Record<string, string> = {
    "0 8 * * *": "每天 08:00",
    "0 */1 * * *": "每小时",
    "*/30 * * * *": "每 30 分钟",
  };
  return labels[task.scheduleCron] ?? task.scheduleCron;
}

function formatNextRun(task: CollectionTask) {
  if (task.status === "paused" || task.status === "disabled") {
    return "已暂停";
  }
  if (task.retryAfterAt) {
    return `重试 ${formatDateTime(task.retryAfterAt)}`;
  }
  if (task.nextRunAt) {
    return `下次 ${formatDateTime(task.nextRunAt)}`;
  }
  if (task.freshnessStatus === "never_run") {
    return `首次运行 · ${task.freshnessTargetHours}h`;
  }
  if (task.freshnessStatus === "stale") {
    return `过期 ${formatStaleHours(task.staleHours)}`;
  }
  return `目标 ${task.freshnessTargetHours}h`;
}

function schedulePolicyLabel(task: CollectionTask) {
  if (task.scheduleCron) {
    return "Cron 调度";
  }
  if (task.schedulePolicy === "auto_freshness") {
    return "自动保鲜";
  }
  return "手动刷新";
}

function schedulePlanValue(task: CollectionTask) {
  const nextRun = task.nextRunAt ? formatDateTime(task.nextRunAt) : "无自动计划";
  const retry = task.retryAfterAt
    ? `重试 ${formatDateTime(task.retryAfterAt)}`
    : `失败 ${task.retryDelayMinutes} 分钟后重试`;
  return `${nextRun} · ${retry}`;
}

function schedulerStatusLabel(overview: SchedulerOverview | null) {
  if (!overview?.enabled) {
    return "scheduler 未启用";
  }
  const latestTick = overview.latestTick;
  if (!latestTick) {
    return "等待首次 tick";
  }
  const errors = latestTick.taskErrors + latestTick.reportSubscriptionErrors;
  if (errors > 0) {
    return `${errors} 个调度异常`;
  }
  if (!latestTick.lockAcquired) {
    return "lease 被占用";
  }
  return latestTick.status === "completed" ? "调度正常" : latestTick.status;
}

function nextRunAfterManualRun(task: CollectionTask, taskRun: TaskRun) {
  if (taskRun.status === "failed") {
    return task.nextRunAt;
  }
  if (task.scheduleCron || task.schedulePolicy !== "auto_freshness") {
    return task.nextRunAt;
  }
  const base = taskRun.finishedAt ?? taskRun.startedAt ?? taskRun.createdAt;
  return new Date(new Date(base).getTime() + task.freshnessTargetHours * 60 * 60_000).toISOString();
}

function retryAfterManualRun(task: CollectionTask, taskRun: TaskRun) {
  if (taskRun.status !== "failed") {
    return null;
  }
  const base = taskRun.finishedAt ?? taskRun.startedAt ?? taskRun.createdAt;
  return new Date(new Date(base).getTime() + task.retryDelayMinutes * 60_000).toISOString();
}

function taskLatencyMinutes(task: CollectionTask) {
  if (task.staleHours !== null && task.staleHours > 0) {
    return Math.round(task.staleHours * 60);
  }
  const value = task.latestRunFinishedAt ?? task.lastRunAt;
  if (!value) {
    return 0;
  }
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) {
    return 0;
  }
  return Math.max(Math.round((Date.now() - timestamp) / 60000), 0);
}

function buildTaskTrend(task: CollectionTask) {
  const base = Math.max(task.latestRunRecordsCount ?? 0, 1);
  return [0.55, 0.7, 0.62, 0.88, 0.76, 1].map((ratio) =>
    Math.max(Math.round(base * ratio), 1),
  );
}

function formatStaleHours(value: number | null) {
  if (value === null) {
    return "未计时";
  }
  if (value < 1) {
    return `${Math.round(value * 60)} 分钟`;
  }
  return `${value.toFixed(1)} 小时`;
}

function freshnessStatusLabel(task: CollectionTask) {
  const labels: Record<CollectionTask["freshnessStatus"], string> = {
    disabled: "已停用",
    failed: "最近失败",
    fresh: "数据新鲜",
    never_run: "尚未运行",
    paused: "已暂停",
    running: "运行中",
    stale: "数据过期",
    unknown: "状态未知",
  };
  return labels[task.freshnessStatus] ?? task.freshnessStatus;
}

function runStatusLabel(status: string) {
  const labels: Record<string, string> = {
    failed: "失败",
    partial_success: "部分成功",
    running: "运行中",
    success: "成功",
  };
  return labels[status] ?? status;
}

function getTaskIssue(task: CollectionTask) {
  if (task.latestRunErrorMessage) {
    return { title: "最新错误", detail: task.latestRunErrorMessage };
  }
  if (task.freshnessStatus === "stale") {
    return {
      title: "数据过期",
      detail: `上次运行已超过 ${task.freshnessTargetHours} 小时目标，当前过期 ${formatStaleHours(task.staleHours)}。`,
    };
  }
  if (task.freshnessStatus === "never_run") {
    return { title: "尚未运行", detail: "任务已启用，但还没有产生任何采集运行记录。" };
  }
  return null;
}

function runHistoryRows(task: CollectionTask, runs: TaskRun[]) {
  if (runs.length > 0) {
    return runs.slice(0, 4).map((runItem) => ({
      time: formatTime(runItem.finishedAt ?? runItem.startedAt),
      label: runStatusLabel(runItem.status),
      code: runItem.status === "failed" ? "ERR" : "OK",
    }));
  }
  return [
    {
      time: formatTime(task.latestRunFinishedAt ?? task.lastRunAt),
      label: task.latestRunStatus ? runStatusLabel(task.latestRunStatus) : "无运行记录",
      code: task.latestRunStatus === "failed" ? "ERR" : "OK",
    },
  ];
}

function buildSourceHealthRows(tasks: CollectionTask[]) {
  const rows = new Map<
    string,
    {
      competitor: number | null;
      ecommerce: number | null;
      agent: number | null;
      governance: number | null;
      health: string;
      osint: number | null;
      platform: number | null;
      social: number | null;
      type: string;
    }
  >();
  for (const task of tasks) {
    const type = collectorLabels[task.collectorType];
    const domain = normalizeDomain(task.projectDomain);
    const current =
      rows.get(type) ??
      {
        competitor: null,
        ecommerce: null,
        agent: null,
        governance: null,
        health: "0 / 0",
        osint: null,
        platform: null,
        social: null,
        type,
      };
    current[domain] = (current[domain] ?? 0) + 1;
    rows.set(type, current);
  }
  return Array.from(rows.values())
    .map((row) => {
      const related = tasks.filter((task) => collectorLabels[task.collectorType] === row.type);
      const healthy = related.filter((task) => getTaskHealth(task) === "healthy").length;
      return { ...row, health: `${healthy} / ${related.length}` };
    })
    .sort((left, right) => left.type.localeCompare(right.type));
}

function buildIngestionTimeline(tasks: CollectionTask[]) {
  return tasks
    .filter((task) => task.latestRunFinishedAt ?? task.lastRunAt)
    .sort((left, right) =>
      String(left.latestRunFinishedAt ?? left.lastRunAt).localeCompare(
        String(right.latestRunFinishedAt ?? right.lastRunAt),
      ),
    )
    .slice(-12)
    .map((task) => ({
      failed: task.latestRunStatus === "failed" ? 1 : 0,
      latency: taskLatencyMinutes(task),
      success: task.latestRunRecordsCount ?? 0,
      time: formatTime(task.latestRunFinishedAt ?? task.lastRunAt),
    }));
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
      step: "no_run_history",
      message: task ? `${task.name} 暂无可展示的运行日志。` : "等待选择任务。",
      timestamp: "n/a",
    },
  ];
}
