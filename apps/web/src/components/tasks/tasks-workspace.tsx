"use client";

import { PauseCircle, PlayCircle, RotateCcw, SquareStack } from "lucide-react";
import { useEffect, useState } from "react";

import { listTasks, pauseTask, resumeTask, runTask } from "@/lib/api/tasks";
import type { CollectionTask, TaskRun } from "@/types/source-task";

export function TasksWorkspace() {
  const [tasks, setTasks] = useState<CollectionTask[]>([]);
  const [latestRun, setLatestRun] = useState<TaskRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    listTasks()
      .then((items) => {
        if (mounted) {
          setTasks(items);
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

  async function run(task: CollectionTask) {
    setError(null);
    try {
      const taskRun = await runTask(task.id);
      setLatestRun(taskRun);
      setTasks((current) =>
        current.map((item) => {
          if (item.id !== task.id) {
            return item;
          }
          return {
            ...item,
            failureCount:
              taskRun.status === "failed" ? item.failureCount + 1 : item.failureCount,
            successCount:
              taskRun.status === "failed" ? item.successCount : item.successCount + 1,
            lastRunAt: taskRun.finishedAt,
          };
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Task run failed");
    }
  }

  async function updateTaskStatus(task: CollectionTask, next: "paused" | "enabled") {
    setError(null);
    try {
      const updated = next === "paused" ? await pauseTask(task.id) : await resumeTask(task.id);
      setTasks((current) => current.map((item) => (item.id === task.id ? updated : item)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Task update failed");
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
      <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">任务列表</h2>
            <p className="mt-1 text-sm text-[#6b7280]">Source 启用后自动创建 CollectionTask</p>
          </div>
          <SquareStack size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {loading ? <p className="text-sm text-[#6b7280]">加载任务中</p> : null}
        {error ? (
          <p className="mb-4 rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3">
          {tasks.map((task) => (
            <article className="rounded-md border border-[#dfe3ea] p-4" key={task.id}>
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <h3 className="text-sm font-semibold">{task.name}</h3>
                  <p className="mt-2 text-sm text-[#6b7280]">
                    {task.collectorType} · {task.scheduleCron ?? "manual"}
                  </p>
                </div>
                <span className="rounded-md bg-[#f1f5f9] px-2.5 py-1 text-xs font-semibold">
                  {task.status}
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-[#6b7280]">
                <span className="rounded-md bg-[#f7f8fa] px-2 py-1">
                  success {task.successCount}
                </span>
                <span className="rounded-md bg-[#f7f8fa] px-2 py-1">
                  failed {task.failureCount}
                </span>
                <span className="rounded-md bg-[#f7f8fa] px-2 py-1">
                  last {task.lastRunAt ?? "never"}
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  className="inline-flex items-center gap-2 rounded-md bg-[#0f766e] px-3 py-2 text-sm font-semibold text-white"
                  onClick={() => void run(task)}
                  type="button"
                >
                  <PlayCircle size={16} aria-hidden="true" />
                  Run Now
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-md border border-[#dfe3ea] px-3 py-2 text-sm"
                  onClick={() => void updateTaskStatus(task, "paused")}
                  type="button"
                >
                  <PauseCircle size={16} aria-hidden="true" />
                  Pause
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-md border border-[#dfe3ea] px-3 py-2 text-sm"
                  onClick={() => void updateTaskStatus(task, "enabled")}
                  type="button"
                >
                  <RotateCcw size={16} aria-hidden="true" />
                  Resume
                </button>
              </div>
            </article>
          ))}
          {!loading && tasks.length === 0 ? (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
              暂无采集任务
            </div>
          ) : null}
        </div>
      </section>

      <aside className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <h2 className="text-base font-semibold">最近运行</h2>
        <p className="mt-1 text-sm text-[#6b7280]">任务运行日志与 RawRecord 写入结果</p>
        {latestRun ? (
          <div className="mt-5 grid gap-3">
            <div className="rounded-md bg-[#f7f8fa] px-3 py-2 text-sm">
              <span className="text-[#6b7280]">Status</span>
              <span className="ml-2 font-semibold">{latestRun.status}</span>
            </div>
            {latestRun.errorMessage ? (
              <p className="rounded-md border border-[#fde68a] bg-[#fffbeb] px-3 py-2 text-sm text-[#92400e]">
                {latestRun.errorMessage}
              </p>
            ) : null}
            <div className="grid gap-2">
              {latestRun.logs.map((log, index) => (
                <div
                  className="rounded-md border border-[#dfe3ea] px-3 py-2 text-sm"
                  key={`${log.step}-${index}`}
                >
                  <span className="font-semibold">{log.step}</span>
                  <p className="mt-1 text-[#6b7280]">{log.message}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="mt-5 rounded-md border border-dashed border-[#dfe3ea] p-6 text-sm text-[#6b7280]">
            尚未手动运行任务
          </div>
        )}
      </aside>
    </div>
  );
}
