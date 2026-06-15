"use client";

import {
  BookOpenCheck,
  CheckCircle2,
  Activity,
  Database,
  Github,
  Globe2,
  Link2,
  Pencil,
  PlayCircle,
  Plus,
  Power,
  RotateCcw,
  ShieldCheck,
  UploadCloud,
  XCircle,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { listProjects } from "@/lib/api/projects";
import { listTasks } from "@/lib/api/tasks";
import {
  createSource,
  disableSource,
  enableSource,
  listCollectors,
  listSources,
  testSource,
  updateSource,
} from "@/lib/api/sources";
import {
  getTrainingCategory,
  getTrainingRiskLevel,
  isTrainingSource,
  trainingCategoryLabel,
  trainingRiskLabel,
} from "@/lib/training-data";
import { cn } from "@/lib/utils";
import type { Project } from "@/types/project";
import type { CollectionTask, Collector, CollectorType, Source } from "@/types/source-task";

const collectorTypeLabels: Record<CollectorType, string> = {
  github_repo: "GitHub Repo",
  github_topic: "GitHub Topic",
  generic_web: "Generic Web",
  manual_json: "Manual JSON",
};

const collectorShortLabels: Record<CollectorType, string> = {
  github_repo: "Repo",
  github_topic: "Topic",
  generic_web: "Web",
  manual_json: "JSON",
};

const collectorVisuals: Record<
  CollectorType,
  {
    icon: typeof Github;
    eyebrow: string;
    tone: string;
    accent: string;
    text: string;
  }
> = {
  github_repo: {
    icon: Github,
    eyebrow: "持续仓库监控",
    tone: "border-[#E8D4CB] bg-[#FFF7F2]",
    accent: "bg-[#C96F5C]",
    text: "text-[#9E4F41]",
  },
  github_topic: {
    icon: Zap,
    eyebrow: "Topic 发现",
    tone: "border-[#E7D8B8] bg-[#FFF9E9]",
    accent: "bg-[#D5A642]",
    text: "text-[#8C6824]",
  },
  generic_web: {
    icon: Globe2,
    eyebrow: "页面变更监控",
    tone: "border-[#D9E2CC] bg-[#F7FBF1]",
    accent: "bg-[#7D9A68]",
    text: "text-[#536B40]",
  },
  manual_json: {
    icon: UploadCloud,
    eyebrow: "结构化导入",
    tone: "border-[#DFD5E8] bg-[#FAF6FF]",
    accent: "bg-[#8D75A8]",
    text: "text-[#6B5685]",
  },
};

const domainLabels: Record<string, string> = {
  osint: "开源雷达",
  ecommerce: "电商风向",
  social: "社媒脉搏",
  competitor: "竞品守望",
  agent: "Agent 生态",
  platform: "平台采集",
  governance: "合规边界",
  mixed: "混合项目",
};

const cadenceLabels: Record<string, string> = {
  "0 8 * * *": "每天 08:00",
  "*/30 * * * *": "每 30 分钟",
  "0 */1 * * *": "每小时",
};

type SourceScope = "all" | "training";

export function SourcesWorkspace() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [collectors, setCollectors] = useState<Collector[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [tasks, setTasks] = useState<CollectionTask[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [collectorType, setCollectorType] = useState<CollectorType>("github_repo");
  const [name, setName] = useState("OpenAI Codex");
  const [scheduleCron, setScheduleCron] = useState("0 8 * * *");
  const [owner, setOwner] = useState("openai");
  const [repo, setRepo] = useState("codex");
  const [topic, setTopic] = useState("web-scraping");
  const [url, setUrl] = useState("https://example.com");
  const [entityType, setEntityType] = useState("product");
  const [jsonText, setJsonText] = useState('{"name":"Demo Product","price":99}');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
  const [busySourceId, setBusySourceId] = useState<string | null>(null);
  const [sourceScope, setSourceScope] = useState<SourceScope>("all");
  const sourceFormRef = useRef<HTMLFormElement | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([listProjects(), listCollectors(), listSources(), listTasks()])
      .then(([projectItems, collectorItems, sourceItems, taskItems]) => {
        if (!mounted) {
          return;
        }
        setProjects(projectItems);
        setCollectors(collectorItems);
        setSources(sourceItems);
        setTasks(taskItems);
        setSelectedProjectId(projectItems[0]?.id ?? "");
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load sources");
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

  const projectById = useMemo(() => {
    return new Map(projects.map((project) => [project.id, project]));
  }, [projects]);

  const taskBySourceId = useMemo(() => {
    return new Map(tasks.map((task) => [task.sourceId, task]));
  }, [tasks]);

  const selectedCollector = collectors.find((collector) => collector.type === collectorType);
  const editingSource = sources.find((source) => source.id === editingSourceId);

  const enabledCount = sources.filter((source) => source.enabled).length;
  const sourceTypeCounts = useMemo(() => {
    return sources.reduce<Record<CollectorType, number>>(
      (counts, source) => {
        counts[source.type] += 1;
        return counts;
      },
      {
        github_repo: 0,
        github_topic: 0,
        generic_web: 0,
        manual_json: 0,
      },
    );
  }, [sources]);
  const latestTaskRunAt = useMemo(() => {
    return latestTimestamp(
      tasks
        .map((task) => task.latestRunFinishedAt ?? task.lastRunAt)
        .filter((value): value is string => Boolean(value)),
    );
  }, [tasks]);
  const latestFailedRunCount = tasks.filter((task) => task.latestRunStatus === "failed").length;
  const trainingSources = useMemo(
    () => sources.filter((source) => isTrainingSource(source)),
    [sources],
  );
  const visibleSources = sourceScope === "training" ? trainingSources : sources;

  const configPreview = (() => {
    try {
      return JSON.stringify(buildConfig(), null, 2);
    } catch {
      return "Manual JSON must be valid JSON";
    }
  })();

  async function submitSource() {
    setError(null);
    setMessage(null);
    try {
      if (!selectedProjectId) {
        setError("Project is required");
        return;
      }
      if (editingSourceId) {
        const source = await updateSource(editingSourceId, {
          name,
          url: collectorType === "generic_web" ? url : undefined,
          config: buildConfig(),
          scheduleCron: normalizeScheduleCron(scheduleCron) ?? null,
        });
        setSources((current) => current.map((item) => (item.id === source.id ? source : item)));
        setTasks((current) =>
          current.map((task) =>
            task.sourceId === source.id
              ? {
                  ...task,
                  name: source.name,
                  scheduleCron: source.scheduleCron,
                }
              : task,
          ),
        );
        setEditingSourceId(null);
        setMessage(`${source.name}: source updated; retest before next run`);
        return;
      }
      const source = await createSource({
        projectId: selectedProjectId,
        name,
        type: collectorType,
        url: collectorType === "generic_web" ? url : undefined,
        config: buildConfig(),
        scheduleCron: normalizeScheduleCron(scheduleCron),
      });
      setSources((current) => [source, ...current]);
      setMessage("Source created");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to create source");
    }
  }

  async function testExistingSource(source: Source) {
    setError(null);
    setMessage(null);
    setBusySourceId(source.id);
    try {
      const result = await testSource(source.id);
      setMessage(`${source.name}: ${result.message}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Source test failed");
    } finally {
      setBusySourceId(null);
    }
  }

  async function enableExistingSource(source: Source) {
    setError(null);
    setMessage(null);
    setBusySourceId(source.id);
    try {
      const task = await enableSource(source.id);
      setSources((current) =>
        current.map((item) => (item.id === source.id ? { ...item, enabled: true } : item)),
      );
      setTasks((current) => upsertTask(current, task));
      setMessage(`${source.name}: task enabled`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to enable source");
    } finally {
      setBusySourceId(null);
    }
  }

  async function disableExistingSource(source: Source) {
    setError(null);
    setMessage(null);
    setBusySourceId(source.id);
    try {
      const disabledSource = await disableSource(source.id);
      setSources((current) =>
        current.map((item) =>
          item.id === disabledSource.id ? { ...item, enabled: disabledSource.enabled } : item,
        ),
      );
      setTasks((current) =>
        current.map((task) =>
          task.sourceId === disabledSource.id ? { ...task, status: "disabled" } : task,
        ),
      );
      setMessage(`${source.name}: source disabled`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to disable source");
    } finally {
      setBusySourceId(null);
    }
  }

  function startEditingSource(source: Source) {
    setEditingSourceId(source.id);
    setSelectedProjectId(source.projectId);
    setCollectorType(source.type);
    setName(source.name);
    setScheduleCron(source.scheduleCron ?? "");
    hydrateConfigFields(source);
    setError(null);
    setMessage(`${source.name}: editing`);
    window.requestAnimationFrame(() => {
      sourceFormRef.current?.scrollIntoView({ block: "start", behavior: "auto" });
    });
  }

  function cancelEditingSource() {
    setEditingSourceId(null);
    setError(null);
    setMessage(null);
  }

  function buildConfig(): Record<string, unknown> {
    if (collectorType === "github_repo") {
      return { owner, repo };
    }
    if (collectorType === "github_topic") {
      return { topic, max_results: 30 };
    }
    if (collectorType === "generic_web") {
      return { url, extract_mode: "main_content" };
    }
    try {
      return { entity_type: entityType, json_data: JSON.parse(jsonText) as unknown };
    } catch {
      throw new Error("Manual JSON must be valid JSON");
    }
  }

  function hydrateConfigFields(source: Source) {
    if (source.type === "github_repo") {
      setOwner(formatConfigValue(source.config.owner) || "openai");
      setRepo(formatConfigValue(source.config.repo) || "codex");
      return;
    }
    if (source.type === "github_topic") {
      setTopic(formatConfigValue(source.config.topic) || "web-scraping");
      return;
    }
    if (source.type === "generic_web") {
      setUrl(source.url ?? (formatConfigValue(source.config.url) || "https://example.com"));
      return;
    }
    setEntityType(formatConfigValue(source.config.entity_type) || "product");
    setJsonText(JSON.stringify(source.config.json_data ?? {}, null, 2));
  }

  return (
    <div className="grid min-w-0 gap-5">
      <section className="overflow-hidden rounded-2xl border border-[#EDDCD3] bg-[#FFF8F4] shadow-[0_18px_60px_rgba(115,70,58,0.08)]">
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <Database size={14} aria-hidden="true" />
              Collector Intake
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C] sm:text-3xl">
              数据源接入工作台
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#7A625A]">
              先验证配置，再启用调度任务；所有采集结果进入原始事实层，后续再生成实体快照、信号和情报。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricPill icon={Link2} label="数据源" value={String(sources.length)} />
              <MetricPill icon={ShieldCheck} label="已启用" value={`${enabledCount}/${sources.length}`} />
              <MetricPill icon={BookOpenCheck} label="培训源" value={`${trainingSources.length}/${sources.length}`} />
              <MetricPill
                icon={Activity}
                label="最近采集"
                value={latestTaskRunAt ? formatRelativeTime(latestTaskRunAt) : "无"}
              />
            </div>
            {latestFailedRunCount > 0 ? (
              <p className="mt-3 inline-flex rounded-full border border-[#F0C8C0] bg-white/75 px-3 py-1 text-xs font-semibold text-[#B85F4F]">
                {latestFailedRunCount} 个任务最近一次运行失败
              </p>
            ) : null}
          </div>

          <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">Collector Mix</p>
                <h3 className="mt-1 text-base font-semibold text-[#2E201C]">当前采集覆盖</h3>
              </div>
              <span className="rounded-full bg-[#C96F5C] px-3 py-1 text-xs font-semibold text-white">
                {collectors.length} types
              </span>
            </div>
            <div className="mt-4 grid gap-2">
              {(Object.keys(collectorTypeLabels) as CollectorType[]).map((type) => {
                const visual = collectorVisuals[type];
                const Icon = visual.icon;
                return (
                  <div
                    className="flex items-center justify-between rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2"
                    key={type}
                  >
                    <span className="inline-flex min-w-0 items-center gap-2 text-sm font-medium text-[#3B2924]">
                      <span
                        className={cn(
                          "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white",
                          visual.accent,
                        )}
                      >
                        <Icon size={15} aria-hidden="true" />
                      </span>
                      <span className="truncate">{collectorTypeLabels[type]}</span>
                    </span>
                    <span className="text-sm font-semibold text-[#8C6257]">
                      {sourceTypeCounts[type]}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">Source Assets</p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">数据源资产池</h2>
              <p className="mt-1 text-sm text-[#7A625A]">按 Collector、项目和启用状态快速判断采集入口是否健康。</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {(["all", "training"] as const).map((scope) => (
                <button
                  className={cn(
                    "inline-flex h-9 items-center gap-2 rounded-full border px-3 text-xs font-semibold transition",
                    sourceScope === scope
                      ? "border-[#C96F5C] bg-[#C96F5C] text-white"
                      : "border-[#E8D4CB] bg-[#FFF7F2] text-[#9E5C4D] hover:border-[#C96F5C]",
                  )}
                  key={scope}
                  onClick={() => setSourceScope(scope)}
                  type="button"
                >
                  {scope === "training" ? <BookOpenCheck size={14} aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
                  {scope === "training" ? `培训数据 ${trainingSources.length}` : "全部数据源"}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
              加载数据源中
            </div>
          ) : null}
          <StatusNotice error={error} message={message} />

          <div className="grid gap-3">
            {visibleSources.map((source) => (
              <SourceAssetCard
                busy={busySourceId === source.id}
                key={source.id}
                onDisable={() => void disableExistingSource(source)}
                onEdit={() => startEditingSource(source)}
                onEnable={() => void enableExistingSource(source)}
                onTest={() => void testExistingSource(source)}
                project={projectById.get(source.projectId)}
                source={source}
                task={taskBySourceId.get(source.id)}
              />
            ))}
            {!loading && visibleSources.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
                {sourceScope === "training"
                  ? "暂无培训数据源。先执行 curated_training 种子或切回全部数据源。"
                  : "暂无数据源。先从右侧创建一个 Collector 配置。"}
              </div>
            ) : null}
          </div>
        </section>

        <form
          ref={sourceFormRef}
          className="rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5"
          onSubmit={(event) => {
            event.preventDefault();
            void submitSource();
          }}
        >
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">
                {editingSource ? "Edit Source" : "New Source"}
              </p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">
                {editingSource ? "编辑采集入口" : "新增采集入口"}
              </h2>
              <p className="mt-1 text-sm text-[#7A625A]">
                {selectedCollector?.description ?? "选择 Collector 后补齐必要配置。"}
              </p>
            </div>
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#C96F5C] text-white">
              <Plus size={18} aria-hidden="true" />
            </span>
          </div>
          <div className="mb-5 flex flex-col gap-2 sm:flex-row">
            <button
              className="inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.24)] transition hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!selectedProjectId}
              type="submit"
            >
              {editingSource ? (
                <CheckCircle2 size={16} aria-hidden="true" />
              ) : (
                <PlayCircle size={16} aria-hidden="true" />
              )}
              {editingSource ? "保存 Source" : "创建 Source"}
            </button>
            {editingSource ? (
              <button
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-[#DDBEAF] bg-white px-4 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C] hover:text-[#B85F4F]"
                onClick={cancelEditingSource}
                type="button"
              >
                <XCircle size={16} aria-hidden="true" />
                取消
              </button>
            ) : null}
          </div>

          <div className="grid gap-4">
            <FieldLabel label="Project">
              <select
                className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                disabled={Boolean(editingSource)}
                onChange={(event) => setSelectedProjectId(event.target.value)}
                value={selectedProjectId}
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </FieldLabel>

            <div className="grid gap-2">
              <span className="text-sm font-semibold text-[#3B2924]">Collector</span>
              <div className="grid grid-cols-2 gap-2">
                {collectors.map((collector) => (
                  <CollectorOption
                    collector={collector}
                    disabled={Boolean(editingSource)}
                    key={collector.type}
                    onSelect={() => {
                      if (!editingSource) {
                        setCollectorType(collector.type);
                      }
                    }}
                    selected={collectorType === collector.type}
                  />
                ))}
              </div>
            </div>

            <TextField label="名称" onChange={setName} value={name} />

            <DynamicConfigFields
              collectorType={collectorType}
              entityType={entityType}
              jsonText={jsonText}
              owner={owner}
              repo={repo}
              setEntityType={setEntityType}
              setJsonText={setJsonText}
              setOwner={setOwner}
              setRepo={setRepo}
              setTopic={setTopic}
              setUrl={setUrl}
              topic={topic}
              url={url}
            />

            <TextField label="Cron" onChange={setScheduleCron} value={scheduleCron} />
            <ConfigPreviewPanel collectorType={collectorType} configPreview={configPreview} />

          </div>
        </form>
      </div>
    </div>
  );
}

type DynamicConfigFieldsProps = {
  collectorType: CollectorType;
  owner: string;
  repo: string;
  topic: string;
  url: string;
  entityType: string;
  jsonText: string;
  setOwner: (value: string) => void;
  setRepo: (value: string) => void;
  setTopic: (value: string) => void;
  setUrl: (value: string) => void;
  setEntityType: (value: string) => void;
  setJsonText: (value: string) => void;
};

function DynamicConfigFields(props: DynamicConfigFieldsProps) {
  if (props.collectorType === "github_repo") {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField label="Owner" onChange={props.setOwner} value={props.owner} />
        <TextField label="Repo" onChange={props.setRepo} value={props.repo} />
      </div>
    );
  }
  if (props.collectorType === "github_topic") {
    return <TextField label="Topic" onChange={props.setTopic} value={props.topic} />;
  }
  if (props.collectorType === "generic_web") {
    return <TextField label="URL" onChange={props.setUrl} value={props.url} />;
  }
  return (
    <div className="grid gap-3">
      <TextField label="Entity Type" onChange={props.setEntityType} value={props.entityType} />
      <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
        <span>JSON</span>
        <textarea
          className="min-h-28 resize-none rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 py-2 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
          onChange={(event) => props.setJsonText(event.target.value)}
          value={props.jsonText}
        />
      </label>
    </div>
  );
}

function MetricPill({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Database;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 px-4 py-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
        <Icon size={14} aria-hidden="true" />
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

function CollectorOption({
  collector,
  selected,
  disabled,
  onSelect,
}: {
  collector: Collector;
  selected: boolean;
  disabled: boolean;
  onSelect: () => void;
}) {
  const visual = collectorVisuals[collector.type];
  const Icon = visual.icon;
  return (
    <button
      className={cn(
        "min-h-24 rounded-2xl border p-3 text-left transition disabled:cursor-not-allowed disabled:opacity-70",
        selected
          ? "border-[#C96F5C] bg-[#FFF7F2] shadow-[0_10px_24px_rgba(201,111,92,0.16)]"
          : "border-[#E8D4CB] bg-[#FFFDFC] hover:border-[#D9B8AD]",
      )}
      disabled={disabled}
      onClick={onSelect}
      type="button"
    >
      <span
        className={cn(
          "inline-flex h-9 w-9 items-center justify-center rounded-full text-white",
          visual.accent,
        )}
      >
        <Icon size={16} aria-hidden="true" />
      </span>
      <span className="mt-3 block text-sm font-semibold text-[#2E201C]">{collector.name}</span>
      <span className={cn("mt-1 block text-xs font-medium", visual.text)}>{visual.eyebrow}</span>
    </button>
  );
}

function SourceAssetCard({
  source,
  project,
  task,
  busy,
  onTest,
  onEdit,
  onEnable,
  onDisable,
}: {
  source: Source;
  project: Project | undefined;
  task: CollectionTask | undefined;
  busy: boolean;
  onTest: () => void;
  onEdit: () => void;
  onEnable: () => void;
  onDisable: () => void;
}) {
  const visual = collectorVisuals[source.type];
  const Icon = visual.icon;
  const domainLabel = domainLabels[project?.domain ?? "mixed"] ?? "未知域";
  const training = isTrainingSource(source);
  const trainingCategory = trainingCategoryLabel(getTrainingCategory(source.config));
  const trainingRisk = trainingRiskLabel(getTrainingRiskLevel(source.config));

  return (
    <article
      className={cn(
        "rounded-2xl border p-4 transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(72,45,38,0.1)]",
        visual.tone,
      )}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-3">
            <span
              className={cn(
                "inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-white",
                visual.accent,
              )}
            >
              <Icon size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="truncate text-base font-semibold text-[#2E201C]">{source.name}</h3>
                <span
                  className={cn(
                    "rounded-full px-2.5 py-1 text-xs font-semibold",
                    source.enabled
                      ? "bg-[#ECF7EA] text-[#4E7C45]"
                      : "bg-[#F6ECE8] text-[#9E5C4D]",
                  )}
                >
                  {source.enabled ? "enabled" : "disabled"}
                </span>
                {training ? (
                  <span className="rounded-full border border-[#E8D4CB] bg-white/80 px-2.5 py-1 text-xs font-semibold text-[#9E5C4D]">
                    培训数据
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-sm text-[#7A625A]">
                {collectorTypeLabels[source.type]} · {project?.name ?? "Unknown project"}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
            <SourceFact label="业务域" value={domainLabel} />
            {training ? <SourceFact label="训练分类" value={trainingCategory} /> : null}
            {training ? <SourceFact label="风险边界" value={trainingRisk} /> : null}
            <SourceFact
              label="调度"
              value={source.scheduleCron ? cadenceLabels[source.scheduleCron] ?? source.scheduleCron : "手动"}
            />
            <SourceFact label="任务状态" value={task ? formatTaskStatus(task.status) : "未启用"} />
            <SourceFact
              label="最近运行"
              value={formatLatestRun(task?.latestRunFinishedAt ?? task?.lastRunAt)}
            />
            <SourceFact label="最近结果" value={formatLatestRunOutcome(task)} />
            <SourceFact label="配置摘要" value={getSourceConfigSummary(source)} />
          </div>
          {task ? (
            <div className="mt-3 inline-flex flex-wrap items-center gap-2 rounded-xl border border-white/70 bg-white/70 px-3 py-2 text-xs font-semibold text-[#7A625A]">
              <Activity size={14} aria-hidden="true" />
              <span>success {task.successCount}</span>
              <span>failure {task.failureCount}</span>
              {task.latestRunStatus ? <span>latest {formatRunStatus(task.latestRunStatus)}</span> : null}
              {task.latestRunRecordsCount !== null && task.latestRunRecordsCount !== undefined ? (
                <span>{task.latestRunRecordsCount} records</span>
              ) : null}
              {task.latestRunEntitiesCount !== null && task.latestRunEntitiesCount !== undefined ? (
                <span>{task.latestRunEntitiesCount} entities</span>
              ) : null}
            </div>
          ) : null}
          {task?.latestRunErrorMessage ? (
            <p className="mt-3 rounded-xl border border-[#F0C8C0] bg-white/80 px-3 py-2 text-xs leading-5 text-[#B85F4F]">
              最近失败原因：{formatTaskErrorMessage(task.latestRunErrorMessage)}
            </p>
          ) : null}

          <p className="mt-3 break-all rounded-xl border border-white/70 bg-white/70 px-3 py-2 text-xs text-[#7A625A]">
            {source.url ?? getSourceEndpointLabel(source)}
          </p>
        </div>

        <div className="grid shrink-0 grid-cols-2 gap-2 sm:flex sm:flex-wrap lg:justify-end">
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#DDBEAF] bg-white px-3 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C] hover:text-[#B85F4F] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={busy}
            onClick={onEdit}
            type="button"
          >
            <Pencil size={16} aria-hidden="true" />
            编辑
          </button>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#DDBEAF] bg-white px-3 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C] hover:text-[#B85F4F] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={busy}
            onClick={onTest}
            type="button"
          >
            <RotateCcw size={16} aria-hidden="true" />
            重测配置
          </button>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white transition hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:bg-[#D8C8C0]"
            disabled={source.enabled || busy}
            onClick={onEnable}
            type="button"
          >
            <CheckCircle2 size={16} aria-hidden="true" />
            启用
          </button>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#DDBEAF] bg-white px-3 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C] hover:text-[#B85F4F] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={!source.enabled || busy}
            onClick={onDisable}
            type="button"
          >
            <Power size={16} aria-hidden="true" />
            停用
          </button>
        </div>
      </div>
    </article>
  );
}

function SourceFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-white/80 bg-white/70 px-3 py-2">
      <p className="text-xs font-semibold text-[#B47767]">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold leading-5 text-[#3B2924]">{value}</p>
    </div>
  );
}

function StatusNotice({ message, error }: { message: string | null; error: string | null }) {
  if (!message && !error) {
    return null;
  }
  return (
    <div className="mb-4 grid gap-2">
      {message ? (
        <p className="rounded-xl border border-[#CDE6C4] bg-[#F3FAEF] px-3 py-2 text-sm font-medium text-[#4E7C45]">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function FieldLabel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
      <span>{label}</span>
      {children}
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
      <span>{label}</span>
      <input
        className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}

function ConfigPreviewPanel({
  collectorType,
  configPreview,
}: {
  collectorType: CollectorType;
  configPreview: string;
}) {
  return (
    <div className="hidden rounded-2xl border border-[#E8D4CB] bg-[#FFF8F4] p-3 sm:block">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase text-[#B47767]">Config Preview</p>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#7D4F43]">
          {collectorShortLabels[collectorType]}
        </span>
      </div>
      <pre className="pointer-events-none mt-3 max-h-32 overflow-hidden whitespace-pre-wrap rounded-xl bg-[#2E201C] p-3 text-xs leading-5 text-[#FFF8F4] sm:max-h-48 sm:overflow-auto">
        {configPreview}
      </pre>
    </div>
  );
}

function getSourceConfigSummary(source: Source): string {
  if (source.type === "github_repo") {
    return `${formatConfigValue(source.config.owner)}/${formatConfigValue(source.config.repo)}`;
  }
  if (source.type === "github_topic") {
    return `topic:${formatConfigValue(source.config.topic)}`;
  }
  if (source.type === "generic_web") {
    return formatConfigValue(source.config.extract_mode) || "main_content";
  }
  const jsonData = source.config.json_data;
  if (jsonData && typeof jsonData === "object" && !Array.isArray(jsonData)) {
    return `${formatConfigValue(source.config.entity_type) || "entity"} · ${
      Object.keys(jsonData).length
    } fields`;
  }
  return formatConfigValue(source.config.entity_type) || "manual";
}

function getSourceEndpointLabel(source: Source): string {
  if (source.type === "github_repo") {
    return `github.com/${formatConfigValue(source.config.owner)}/${formatConfigValue(source.config.repo)}`;
  }
  if (source.type === "github_topic") {
    return `github topic: ${formatConfigValue(source.config.topic)}`;
  }
  if (source.type === "manual_json") {
    return "手动录入事实";
  }
  return "No URL";
}

function formatConfigValue(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function formatTaskStatus(status: CollectionTask["status"]): string {
  const labels: Record<CollectionTask["status"], string> = {
    draft: "草稿",
    enabled: "已启用",
    running: "运行中",
    paused: "已暂停",
    disabled: "已停用",
  };
  return labels[status];
}

function formatRunStatus(status: string): string {
  const labels: Record<string, string> = {
    failed: "失败",
    partial_success: "部分成功",
    running: "运行中",
    success: "成功",
  };
  return labels[status] ?? status;
}

function formatLatestRunOutcome(task: CollectionTask | undefined): string {
  if (!task) {
    return "未启用";
  }
  if (!task.latestRunStatus) {
    return "无运行记录";
  }
  const records = task.latestRunRecordsCount ?? 0;
  const entities = task.latestRunEntitiesCount ?? 0;
  return `${formatRunStatus(task.latestRunStatus)} · ${records} records · ${entities} entities`;
}

function formatLatestRun(value: string | null | undefined): string {
  if (!value) {
    return "尚未运行";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatRelativeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "时间无效";
  }
  const diffMs = Math.max(Date.now() - date.getTime(), 0);
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) {
    return "刚刚";
  }
  if (minutes < 60) {
    return `${minutes} 分钟前`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} 小时前`;
  }
  return `${Math.floor(hours / 24)} 天前`;
}

function latestTimestamp(values: string[]) {
  const timestamps = values
    .map((value) => new Date(value).getTime())
    .filter((value) => Number.isFinite(value));
  if (timestamps.length === 0) {
    return null;
  }
  return new Date(Math.max(...timestamps)).toISOString();
}

function formatTaskErrorMessage(value: string) {
  return value.length > 180 ? `${value.slice(0, 180)}...` : value;
}

function normalizeScheduleCron(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function upsertTask(tasks: CollectionTask[], task: CollectionTask): CollectionTask[] {
  const exists = tasks.some((item) => item.id === task.id);
  if (!exists) {
    return [task, ...tasks];
  }
  return tasks.map((item) => (item.id === task.id ? task : item));
}
