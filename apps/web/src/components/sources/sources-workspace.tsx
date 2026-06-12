"use client";

import { CheckCircle2, FlaskConical, Link2, PlayCircle, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listProjects } from "@/lib/api/projects";
import {
  createSource,
  enableSource,
  listCollectors,
  listSources,
  testSource,
} from "@/lib/api/sources";
import type { Project } from "@/types/project";
import type { Collector, CollectorType, Source } from "@/types/source-task";

const collectorTypeLabels: Record<CollectorType, string> = {
  github_repo: "GitHub Repo",
  github_topic: "GitHub Topic",
  generic_web: "Generic Web",
  manual_json: "Manual JSON",
};

export function SourcesWorkspace() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [collectors, setCollectors] = useState<Collector[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
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

  useEffect(() => {
    let mounted = true;
    Promise.all([listProjects(), listCollectors(), listSources()])
      .then(([projectItems, collectorItems, sourceItems]) => {
        if (!mounted) {
          return;
        }
        setProjects(projectItems);
        setCollectors(collectorItems);
        setSources(sourceItems);
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

  async function submitSource() {
    setError(null);
    setMessage(null);
    try {
      if (!selectedProjectId) {
        setError("Project is required");
        return;
      }
      const source = await createSource({
        projectId: selectedProjectId,
        name,
        type: collectorType,
        url: collectorType === "generic_web" ? url : undefined,
        config: buildConfig(),
        scheduleCron,
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
    try {
      const result = await testSource(source.id);
      setMessage(`${source.name}: ${result.message}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Source test failed");
    }
  }

  async function enableExistingSource(source: Source) {
    setError(null);
    setMessage(null);
    try {
      await enableSource(source.id);
      setSources((current) =>
        current.map((item) => (item.id === source.id ? { ...item, enabled: true } : item)),
      );
      setMessage(`${source.name}: task enabled`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to enable source");
    }
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

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
      <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">数据源列表</h2>
            <p className="mt-1 text-sm text-[#6b7280]">配置校验先行，任务运行写入 RawRecord</p>
          </div>
          <Link2 size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {loading ? <p className="text-sm text-[#6b7280]">加载数据源中</p> : null}
        {message ? (
          <p className="mb-4 rounded-md border border-[#bbf7d0] bg-[#f0fdf4] px-3 py-2 text-sm text-[#166534]">
            {message}
          </p>
        ) : null}
        {error ? (
          <p className="mb-4 rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3">
          {sources.map((source) => (
            <article className="rounded-md border border-[#dfe3ea] p-4" key={source.id}>
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <h3 className="text-sm font-semibold">{source.name}</h3>
                  <p className="mt-2 text-sm text-[#6b7280]">
                    {collectorTypeLabels[source.type]} ·{" "}
                    {projectById.get(source.projectId)?.name ?? "Unknown project"}
                  </p>
                  <p className="mt-2 break-all text-xs text-[#6b7280]">{source.url ?? "No URL"}</p>
                </div>
                <span className="rounded-md bg-[#f1f5f9] px-2.5 py-1 text-xs font-semibold">
                  {source.enabled ? "enabled" : "disabled"}
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  className="inline-flex items-center gap-2 rounded-md border border-[#dfe3ea] px-3 py-2 text-sm"
                  onClick={() => void testExistingSource(source)}
                  type="button"
                >
                  <FlaskConical size={16} aria-hidden="true" />
                  测试配置
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-md bg-[#0f766e] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                  disabled={source.enabled}
                  onClick={() => void enableExistingSource(source)}
                  type="button"
                >
                  <CheckCircle2 size={16} aria-hidden="true" />
                  启用
                </button>
              </div>
            </article>
          ))}
          {!loading && sources.length === 0 ? (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
              暂无数据源
            </div>
          ) : null}
        </div>
      </section>

      <form
        className="rounded-lg border border-[#dfe3ea] bg-white p-5"
        onSubmit={(event) => {
          event.preventDefault();
          void submitSource();
        }}
      >
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">新增 Source</h2>
            <p className="mt-1 text-sm text-[#6b7280]">{collectors.length} collectors available</p>
          </div>
          <Plus size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        <div className="grid gap-4">
          <label className="grid gap-2 text-sm font-medium">
            Project
            <select
              className="rounded-md border border-[#dfe3ea] px-3 py-2 outline-none"
              onChange={(event) => setSelectedProjectId(event.target.value)}
              value={selectedProjectId}
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-2 text-sm font-medium">
            Collector
            <select
              className="rounded-md border border-[#dfe3ea] px-3 py-2 outline-none"
              onChange={(event) => setCollectorType(event.target.value as CollectorType)}
              value={collectorType}
            >
              {collectors.map((collector) => (
                <option key={collector.type} value={collector.type}>
                  {collector.name}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-2 text-sm font-medium">
            名称
            <input
              className="rounded-md border border-[#dfe3ea] px-3 py-2 outline-none"
              onChange={(event) => setName(event.target.value)}
              value={name}
            />
          </label>

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

          <label className="grid gap-2 text-sm font-medium">
            Cron
            <input
              className="rounded-md border border-[#dfe3ea] px-3 py-2 outline-none"
              onChange={(event) => setScheduleCron(event.target.value)}
              value={scheduleCron}
            />
          </label>

          <button
            className="inline-flex items-center justify-center gap-2 rounded-md bg-[#0f766e] px-4 py-2.5 text-sm font-semibold text-white"
            type="submit"
          >
            <PlayCircle size={16} aria-hidden="true" />
            创建 Source
          </button>
        </div>
      </form>
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
      <div className="grid grid-cols-2 gap-3">
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
      <label className="grid gap-2 text-sm font-medium">
        JSON
        <textarea
          className="min-h-28 resize-none rounded-md border border-[#dfe3ea] px-3 py-2 outline-none"
          onChange={(event) => props.setJsonText(event.target.value)}
          value={props.jsonText}
        />
      </label>
    </div>
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
    <label className="grid gap-2 text-sm font-medium">
      {label}
      <input
        className="rounded-md border border-[#dfe3ea] px-3 py-2 outline-none"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}
