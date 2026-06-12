"use client";

import { Plus, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { createProject, listProjects } from "@/lib/api/projects";
import type { Project, ProjectDomain } from "@/types/project";

const domains: Array<{ label: string; value: ProjectDomain | "all" }> = [
  { label: "全部", value: "all" },
  { label: "开源", value: "osint" },
  { label: "电商", value: "ecommerce" },
  { label: "社媒", value: "social" },
  { label: "竞品", value: "competitor" },
  { label: "混合", value: "mixed" },
];

export function ProjectWorkspace() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [domain, setDomain] = useState<ProjectDomain | "all">("all");
  const [query, setQuery] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [newDomain, setNewDomain] = useState<ProjectDomain>("osint");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    listProjects()
      .then((items) => {
        if (mounted) {
          setProjects(items);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load projects");
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

  const filteredProjects = useMemo(() => {
    return projects.filter((project) => {
      const matchesDomain = domain === "all" || project.domain === domain;
      const matchesQuery = `${project.name} ${project.description ?? ""}`
        .toLowerCase()
        .includes(query.toLowerCase());
      return matchesDomain && matchesQuery;
    });
  }, [domain, projects, query]);

  async function submitProject() {
    setError(null);
    if (name.trim().length === 0) {
      setError("Project name is required");
      return;
    }
    try {
      const project = await createProject({
        name: name.trim(),
        description: description.trim() || undefined,
        domain: newDomain,
      });
      setProjects((current) => [project, ...current]);
      setName("");
      setDescription("");
      setNewDomain("osint");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to create project");
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
      <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2">
            {domains.map((item) => (
              <button
                className={`rounded-md border px-3 py-2 text-sm ${
                  domain === item.value
                    ? "border-[#0f766e] bg-[#ecfdf5] text-[#0f766e]"
                    : "border-[#dfe3ea]"
                }`}
                key={item.value}
                onClick={() => setDomain(item.value)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
          <label className="flex min-w-0 items-center gap-2 rounded-md border border-[#dfe3ea] px-3 py-2 text-sm lg:w-72">
            <Search size={17} className="text-[#6b7280]" aria-hidden="true" />
            <input
              className="w-full border-0 outline-none"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索项目"
              value={query}
            />
          </label>
        </div>

        {loading ? <p className="text-sm text-[#6b7280]">加载项目中</p> : null}
        {error ? (
          <p className="mb-4 rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3">
          {filteredProjects.map((project) => (
            <article className="rounded-md border border-[#dfe3ea] p-4" key={project.id}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 className="text-sm font-semibold">{project.name}</h2>
                  <p className="mt-2 text-sm leading-6 text-[#6b7280]">
                    {project.description ?? "No description"}
                  </p>
                </div>
                <span className="rounded-md bg-[#f1f5f9] px-2.5 py-1 text-xs font-semibold">
                  {project.domain}
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-[#6b7280]">
                <span className="rounded-md bg-[#f7f8fa] px-2 py-1">{project.status}</span>
                <span className="rounded-md bg-[#f7f8fa] px-2 py-1">
                  {project.sourceCount} sources
                </span>
                <span className="rounded-md bg-[#f7f8fa] px-2 py-1">
                  {project.intelligenceCount} intelligence
                </span>
              </div>
            </article>
          ))}
          {!loading && filteredProjects.length === 0 ? (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
              没有匹配的项目
            </div>
          ) : null}
        </div>
      </section>

      <form
        className="rounded-lg border border-[#dfe3ea] bg-white p-5"
        onSubmit={(event) => {
          event.preventDefault();
          void submitProject();
        }}
      >
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">创建项目</h2>
            <p className="mt-1 text-sm text-[#6b7280]">按业务主题组织监控源</p>
          </div>
          <Plus size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        <div className="grid gap-4">
          <label className="grid gap-2 text-sm font-medium">
            名称
            <input
              className="rounded-md border border-[#dfe3ea] px-3 py-2 outline-none"
              onChange={(event) => setName(event.target.value)}
              value={name}
            />
          </label>
          <label className="grid gap-2 text-sm font-medium">
            业务域
            <select
              className="rounded-md border border-[#dfe3ea] px-3 py-2 outline-none"
              onChange={(event) => setNewDomain(event.target.value as ProjectDomain)}
              value={newDomain}
            >
              {domains
                .filter((item) => item.value !== "all")
                .map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
            </select>
          </label>
          <label className="grid gap-2 text-sm font-medium">
            描述
            <textarea
              className="min-h-28 resize-none rounded-md border border-[#dfe3ea] px-3 py-2 outline-none"
              onChange={(event) => setDescription(event.target.value)}
              value={description}
            />
          </label>
          <button
            className="rounded-md bg-[#0f766e] px-4 py-2.5 text-sm font-semibold text-white"
            type="submit"
          >
            创建
          </button>
        </div>
      </form>
    </div>
  );
}
