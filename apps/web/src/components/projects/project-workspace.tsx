"use client";

import {
  Archive,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  Filter,
  FolderKanban,
  Globe2,
  LayoutGrid,
  LineChart,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Table2,
  Target,
  X,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { createProject, listProjects } from "@/lib/api/projects";
import { cn } from "@/lib/utils";
import type { Project, ProjectDomain, ProjectStatus } from "@/types/project";

type DomainFilter = ProjectDomain | "all";
type StatusFilter = ProjectStatus | "all";

const domains: Array<{ label: string; value: DomainFilter }> = [
  { label: "全部域", value: "all" },
  { label: "开源雷达", value: "osint" },
  { label: "电商风向", value: "ecommerce" },
  { label: "社媒脉搏", value: "social" },
  { label: "竞品守望", value: "competitor" },
  { label: "混合项目", value: "mixed" },
];

const statusFilters: Array<{ label: string; value: StatusFilter }> = [
  { label: "All status", value: "all" },
  { label: "Active", value: "active" },
  { label: "Archived", value: "archived" },
];

const domainProfiles: Record<
  ProjectDomain,
  {
    label: string;
    shortLabel: string;
    description: string;
    icon: typeof FolderKanban;
    tone: string;
    accent: string;
    text: string;
    href: Route;
  }
> = {
  osint: {
    label: "开源雷达",
    shortLabel: "OSINT",
    description: "GitHub 趋势、仓库动态和开源项目信号",
    icon: Globe2,
    tone: "border-[#E8D4CB] bg-[#FFF7F2]",
    accent: "bg-[#C96F5C]",
    text: "text-[#9E4F41]",
    href: "/domain/osint" as Route,
  },
  ecommerce: {
    label: "电商风向",
    shortLabel: "ECOM",
    description: "商品、价格、Listing 和渠道变化",
    icon: BarChart3,
    tone: "border-[#E7D8B8] bg-[#FFF9E9]",
    accent: "bg-[#D5A642]",
    text: "text-[#8C6824]",
    href: "/domain/ecommerce" as Route,
  },
  social: {
    label: "社媒脉搏",
    shortLabel: "SOCIAL",
    description: "帖子、声量、活动和手动导入线索",
    icon: LineChart,
    tone: "border-[#D9E2CC] bg-[#F7FBF1]",
    accent: "bg-[#7D9A68]",
    text: "text-[#536B40]",
    href: "/domain/social" as Route,
  },
  competitor: {
    label: "竞品守望",
    shortLabel: "COMP",
    description: "官网、定价、产品页和页面快照变化",
    icon: ShieldCheck,
    tone: "border-[#DFD5E8] bg-[#FAF6FF]",
    accent: "bg-[#8D75A8]",
    text: "text-[#6B5685]",
    href: "/domain/competitor" as Route,
  },
  mixed: {
    label: "混合项目",
    shortLabel: "MIXED",
    description: "跨域监控、临时研究和组合型情报流",
    icon: FolderKanban,
    tone: "border-[#E8D4CB] bg-[#FFFDFC]",
    accent: "bg-[#B47767]",
    text: "text-[#8A5A4E]",
    href: "/dashboard",
  },
};

const statusProfiles: Record<
  ProjectStatus,
  { label: string; icon: typeof CheckCircle2; className: string }
> = {
  active: {
    label: "active",
    icon: CheckCircle2,
    className: "bg-[#ECF7EA] text-[#4E7C45]",
  },
  archived: {
    label: "archived",
    icon: Archive,
    className: "bg-[#F6ECE8] text-[#9E5C4D]",
  },
};

export function ProjectWorkspace() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [domain, setDomain] = useState<DomainFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [newDomain, setNewDomain] = useState<ProjectDomain>("osint");
  const [owner, setOwner] = useState("self");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    listProjects()
      .then((items) => {
        if (mounted) {
          setProjects(items);
          setSelectedId(items[0]?.id ?? null);
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

  useEffect(() => {
    if (!modalOpen) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setModalOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [modalOpen]);

  const domainCounts = useMemo(() => {
    return projects.reduce<Record<ProjectDomain, number>>(
      (counts, project) => {
        counts[project.domain] += 1;
        return counts;
      },
      {
        osint: 0,
        ecommerce: 0,
        social: 0,
        competitor: 0,
        mixed: 0,
      },
    );
  }, [projects]);

  const filteredProjects = useMemo(() => {
    const term = query.trim().toLowerCase();
    return projects.filter((project) => {
      const matchesDomain = domain === "all" || project.domain === domain;
      const matchesStatus = statusFilter === "all" || project.status === statusFilter;
      const matchesQuery =
        term.length === 0 ||
        [
          project.name,
          project.description ?? "",
          project.domain,
          domainProfiles[project.domain].label,
          project.status,
        ]
          .join(" ")
          .toLowerCase()
          .includes(term);
      return matchesDomain && matchesStatus && matchesQuery;
    });
  }, [domain, projects, query, statusFilter]);

  const selectedProject = useMemo(() => {
    return filteredProjects.find((project) => project.id === selectedId) ?? filteredProjects[0] ?? null;
  }, [filteredProjects, selectedId]);

  const stats = useMemo(() => {
    const active = projects.filter((project) => project.status === "active").length;
    const archived = projects.filter((project) => project.status === "archived").length;
    const sources = projects.reduce((total, project) => total + project.sourceCount, 0);
    const intelligence = projects.reduce((total, project) => total + project.intelligenceCount, 0);
    return {
      active,
      archived,
      sources,
      intelligence,
      total: projects.length,
    };
  }, [projects]);

  async function submitProject() {
    setError(null);
    setMessage(null);
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
      setSelectedId(project.id);
      setName("");
      setDescription("");
      setNewDomain("osint");
      setOwner("self");
      setModalOpen(false);
      setMessage(`${project.name} created for ${owner.trim() || "self"}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to create project");
    }
  }

  return (
    <div className="grid min-w-0 gap-5">
      <section className="overflow-hidden rounded-2xl border border-[#EDDCD3] bg-[#FFF8F4] shadow-[0_18px_60px_rgba(115,70,58,0.08)]">
        <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <FolderKanban size={14} aria-hidden="true" />
              Project Control Room
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C] sm:text-3xl">
              项目组合控制台
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#7A625A]">
              按业务域组织监控主题，把数据源、采集任务、信号和情报回收到同一个项目语境。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-4">
              <MetricPill icon={FolderKanban} label="项目数" value={String(stats.total)} />
              <MetricPill icon={CheckCircle2} label="Active" value={String(stats.active)} />
              <MetricPill icon={Archive} label="Archived" value={String(stats.archived)} />
              <MetricPill icon={Sparkles} label="情报数" value={String(stats.intelligence)} />
            </div>
          </div>

          <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">Portfolio State</p>
                <h3 className="mt-1 text-base font-semibold text-[#2E201C]">当前筛选</h3>
              </div>
              <span className="rounded-full bg-[#C96F5C] px-3 py-1 text-xs font-semibold text-white">
                {filteredProjects.length}
              </span>
            </div>
            <div className="mt-4 grid gap-2">
              <StateRow label="Domain" value={domain === "all" ? "all" : domainProfiles[domain].label} />
              <StateRow label="Status" value={statusFilter} />
              <StateRow label="Sources" value={String(stats.sources)} />
            </div>
          </div>
        </div>
      </section>

      <StatusNotice error={error} message={message} />

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="grid min-w-0 gap-5">
          <section className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
            <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">Filters</p>
                <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">项目筛选</h2>
                <p className="mt-1 text-sm text-[#7A625A]">按 domain、状态和关键字定位监控主题。</p>
              </div>
              <button
                className="inline-flex h-10 w-fit items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.22)] transition hover:bg-[#B85F4F]"
                onClick={() => setModalOpen(true)}
                type="button"
              >
                <Plus size={16} aria-hidden="true" />
                New Project
              </button>
            </div>

            <div className="grid gap-3">
              <div className="flex flex-wrap gap-2">
                {domains.map((item) => {
                  const count = item.value === "all" ? projects.length : domainCounts[item.value];
                  return (
                    <button
                      className={cn(
                        "inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-sm font-semibold transition",
                        domain === item.value
                          ? "border-[#C96F5C] bg-[#FFF1EB] text-[#9E4F41]"
                          : "border-[#E8D4CB] bg-[#FFFDFC] text-[#7D4F43] hover:border-[#C96F5C]",
                      )}
                      key={item.value}
                      onClick={() => setDomain(item.value)}
                      type="button"
                    >
                      {item.label}
                      <span className="rounded-full bg-white/85 px-2 py-0.5 text-xs">{count}</span>
                    </button>
                  );
                })}
              </div>

              <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_180px]">
                <label className="relative block min-w-0">
                  <Search
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                    size={16}
                    aria-hidden="true"
                  />
                  <input
                    className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="搜索项目、域、状态"
                    value={query}
                  />
                </label>
                <label className="relative block min-w-0">
                  <Filter
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                    size={16}
                    aria-hidden="true"
                  />
                  <select
                    className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-8 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                    onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                    value={statusFilter}
                  >
                    {statusFilters.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          </section>

          <section className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
            <div className="mb-5 flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">Card View</p>
                <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">项目卡片</h2>
              </div>
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#C96F5C] text-white">
                <LayoutGrid size={18} aria-hidden="true" />
              </span>
            </div>

            {loading ? (
              <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
                加载项目中
              </div>
            ) : null}

            <div className="grid gap-3 lg:grid-cols-2">
              {filteredProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  onSelect={() => setSelectedId(project.id)}
                  project={project}
                  selected={project.id === selectedProject?.id}
                />
              ))}
            </div>
            {!loading && filteredProjects.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
                没有匹配的项目。
              </div>
            ) : null}
          </section>

          <ProjectTable
            onSelect={(project) => setSelectedId(project.id)}
            projects={filteredProjects}
            selectedId={selectedProject?.id ?? null}
          />
        </div>

        <aside className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">Project Detail</p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">项目作战室</h2>
              <p className="mt-1 text-sm text-[#7A625A]">查看项目状态、监控覆盖和关联工作台入口。</p>
            </div>
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#C96F5C] text-white">
              <Target size={18} aria-hidden="true" />
            </span>
          </div>
          {selectedProject ? (
            <ProjectDetail project={selectedProject} />
          ) : (
            <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
              选择一个项目查看详情。
            </div>
          )}
        </aside>
      </div>

      {modalOpen ? (
        <ProjectCreateModal
          description={description}
          domain={newDomain}
          name={name}
          onClose={() => setModalOpen(false)}
          onDescriptionChange={setDescription}
          onDomainChange={setNewDomain}
          onNameChange={setName}
          onOwnerChange={setOwner}
          onSubmit={() => void submitProject()}
          owner={owner}
        />
      ) : null}
    </div>
  );
}

function ProjectCard({
  project,
  selected,
  onSelect,
}: {
  project: Project;
  selected: boolean;
  onSelect: () => void;
}) {
  const domain = domainProfiles[project.domain];
  const status = statusProfiles[project.status];
  const DomainIcon = domain.icon;
  const StatusIcon = status.icon;
  const health = getProjectHealth(project);
  return (
    <article
      className={cn(
        "min-w-0 rounded-2xl border p-4 transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(72,45,38,0.1)]",
        domain.tone,
        selected ? "ring-2 ring-[#C96F5C] ring-offset-2 ring-offset-white" : "",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <button className="min-w-0 text-left" onClick={onSelect} type="button">
          <div className="flex min-w-0 items-center gap-3">
            <span
              className={cn(
                "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white",
                domain.accent,
              )}
            >
              <DomainIcon size={17} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h3 className="break-words text-base font-semibold text-[#2E201C]">{project.name}</h3>
              <p className={cn("mt-1 text-xs font-semibold uppercase", domain.text)}>
                {domain.shortLabel} · {domain.label}
              </p>
            </div>
          </div>
        </button>
        <span className={cn("inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold", status.className)}>
          <StatusIcon size={13} aria-hidden="true" />
          {status.label}
        </span>
      </div>

      <p className="mt-4 min-h-12 text-sm leading-6 text-[#5F4A43]">
        {project.description ?? "No description"}
      </p>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <MiniStat label="Sources" value={String(project.sourceCount)} />
        <MiniStat label="Intel" value={String(project.intelligenceCount)} />
        <MiniStat label="Health" value={`${health.score}`} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          className="inline-flex h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-white/80 px-3 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C]"
          href={domain.href}
        >
          <ArrowUpRight size={16} aria-hidden="true" />
          Domain
        </Link>
        <Link
          className="inline-flex h-10 items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.18)] transition hover:bg-[#B85F4F]"
          href="/sources"
        >
          <ClipboardList size={16} aria-hidden="true" />
          Sources
        </Link>
      </div>
    </article>
  );
}

function ProjectTable({
  projects,
  selectedId,
  onSelect,
}: {
  projects: Project[];
  selectedId: string | null;
  onSelect: (project: Project) => void;
}) {
  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-[#EDDCD3] bg-white shadow-[0_16px_48px_rgba(72,45,38,0.07)]">
      <div className="flex items-start justify-between gap-3 border-b border-[#F0E1D9] p-4 sm:p-5">
        <div>
          <p className="text-xs font-semibold uppercase text-[#B47767]">Table View</p>
          <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">项目表格</h2>
        </div>
        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#FFF1EB] text-[#C96F5C]">
          <Table2 size={18} aria-hidden="true" />
        </span>
      </div>

      <table className="w-full table-fixed text-left text-sm">
        <thead className="bg-[#FFF8F4] text-xs uppercase text-[#B47767]">
          <tr>
            <th className="w-[44%] px-4 py-3 font-semibold sm:px-5">Project</th>
            <th className="hidden px-3 py-3 font-semibold md:table-cell">Domain</th>
            <th className="w-[24%] px-3 py-3 font-semibold sm:w-[18%]">Status</th>
            <th className="hidden px-3 py-3 font-semibold lg:table-cell">Coverage</th>
            <th className="w-[32%] px-4 py-3 text-right font-semibold sm:w-[24%] sm:px-5">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#F0E1D9]">
          {projects.map((project) => {
            const domain = domainProfiles[project.domain];
            const status = statusProfiles[project.status];
            const StatusIcon = status.icon;
            return (
              <tr
                className={cn(
                  "align-top transition hover:bg-[#FFFDFC]",
                  selectedId === project.id ? "bg-[#FFF7F2]" : "bg-white",
                )}
                key={project.id}
              >
                <td className="px-4 py-4 sm:px-5">
                  <button
                    className="break-words text-left font-semibold text-[#2E201C] hover:text-[#C96F5C]"
                    onClick={() => onSelect(project)}
                    type="button"
                  >
                    {project.name}
                  </button>
                  <p className="mt-1 hidden break-words text-xs leading-5 text-[#7A625A] sm:block">
                    {project.description ?? "No description"}
                  </p>
                </td>
                <td className="hidden px-3 py-4 md:table-cell">
                  <span className={cn("rounded-full px-2.5 py-1 text-xs font-semibold", domain.tone, domain.text)}>
                    {domain.label}
                  </span>
                </td>
                <td className="px-3 py-4">
                  <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold", status.className)}>
                    <StatusIcon size={13} aria-hidden="true" />
                    {status.label}
                  </span>
                </td>
                <td className="hidden px-3 py-4 text-[#5F4A43] lg:table-cell">
                  {project.sourceCount} sources / {project.intelligenceCount} intel
                </td>
                <td className="px-4 py-4 text-right sm:px-5">
                  <Link
                    className="inline-flex h-9 items-center justify-center rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-xs font-semibold text-[#7D4F43] transition hover:border-[#C96F5C]"
                    href={domain.href}
                  >
                    Open
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function ProjectDetail({ project }: { project: Project }) {
  const domain = domainProfiles[project.domain];
  const status = statusProfiles[project.status];
  const DomainIcon = domain.icon;
  const StatusIcon = status.icon;
  const health = getProjectHealth(project);
  return (
    <div className="grid gap-4">
      <div className={cn("rounded-2xl border p-4", domain.tone)}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={cn("text-xs font-semibold uppercase", domain.text)}>{domain.label}</p>
            <h3 className="mt-1 break-words text-lg font-semibold text-[#2E201C]">{project.name}</h3>
            <p className="mt-3 text-sm leading-6 text-[#5F4A43]">
              {project.description ?? "No description"}
            </p>
          </div>
          <span className={cn("inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white", domain.accent)}>
            <DomainIcon size={18} aria-hidden="true" />
          </span>
        </div>
      </div>

      <div className="grid gap-2">
        <DetailRow label="Project ID" value={project.id} />
        <DetailRow label="Status" value={status.label} icon={StatusIcon} />
        <DetailRow label="Sources" value={String(project.sourceCount)} />
        <DetailRow label="Intelligence" value={String(project.intelligenceCount)} />
      </div>

      <div className="rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase text-[#B47767]">Readiness</p>
            <h4 className="mt-1 text-sm font-semibold text-[#2E201C]">{health.label}</h4>
          </div>
          <span className="text-lg font-semibold text-[#2E201C]">{health.score}</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#F3E3DC]">
          <div className={cn("h-full rounded-full bg-[#C96F5C]", health.widthClass)} />
        </div>
      </div>

      <div className="grid gap-2">
        <Link
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.22)] transition hover:bg-[#B85F4F]"
          href={domain.href}
        >
          <ArrowUpRight size={16} aria-hidden="true" />
          打开业务域
        </Link>
        <div className="grid gap-2 sm:grid-cols-3">
          <LinkButton href="/sources" label="Sources" />
          <LinkButton href="/tasks" label="Tasks" />
          <LinkButton href="/signals" label="Signals" />
        </div>
      </div>
    </div>
  );
}

function ProjectCreateModal({
  name,
  description,
  domain,
  owner,
  onNameChange,
  onDescriptionChange,
  onDomainChange,
  onOwnerChange,
  onSubmit,
  onClose,
}: {
  name: string;
  description: string;
  domain: ProjectDomain;
  owner: string;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onDomainChange: (value: ProjectDomain) => void;
  onOwnerChange: (value: string) => void;
  onSubmit: () => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[#2E201C]/35 px-4 py-6 backdrop-blur-sm">
      <form
        aria-labelledby="create-project-title"
        aria-modal="true"
        className="max-h-[calc(100vh-48px)] w-full max-w-xl overflow-y-auto rounded-2xl border border-[#E8D4CB] bg-white p-5 shadow-[0_24px_80px_rgba(46,32,28,0.24)]"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
        role="dialog"
      >
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase text-[#B47767]">Create Project</p>
            <h2 className="mt-1 text-lg font-semibold text-[#2E201C]" id="create-project-title">
              创建项目
            </h2>
          </div>
          <button
            aria-label="Close create project modal"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[#E8D4CB] bg-[#FFFDFC] text-[#7D4F43] transition hover:border-[#C96F5C]"
            onClick={onClose}
            type="button"
          >
            <X size={17} aria-hidden="true" />
          </button>
        </div>

        <div className="grid gap-4">
          <FieldLabel label="Name">
            <input
              className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
              onChange={(event) => onNameChange(event.target.value)}
              placeholder="AI Scrapy Tools"
              value={name}
            />
          </FieldLabel>
          <div className="grid gap-4 sm:grid-cols-2">
            <FieldLabel label="Domain">
              <select
                className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                onChange={(event) => onDomainChange(event.target.value as ProjectDomain)}
                value={domain}
              >
                {domains
                  .filter((item): item is { label: string; value: ProjectDomain } => item.value !== "all")
                  .map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
              </select>
            </FieldLabel>
            <FieldLabel label="Owner">
              <input
                className="h-11 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                onChange={(event) => onOwnerChange(event.target.value)}
                placeholder="self"
                value={owner}
              />
            </FieldLabel>
          </div>
          <FieldLabel label="Description">
            <textarea
              className="min-h-28 resize-none rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 py-2 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
              onChange={(event) => onDescriptionChange(event.target.value)}
              placeholder="监控主题、数据源范围和情报用途"
              value={description}
            />
          </FieldLabel>
          <button
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.22)] transition hover:bg-[#B85F4F]"
            type="submit"
          >
            <Plus size={16} aria-hidden="true" />
            创建
          </button>
        </div>
      </form>
    </div>
  );
}

function MetricPill({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FolderKanban;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 px-4 py-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
        <Icon size={14} aria-hidden="true" />
        {label}
      </div>
      <p className="mt-2 break-words text-xl font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#F0E1D9] bg-white/70 px-3 py-2">
      <p className="text-xs font-semibold uppercase text-[#B47767]">{label}</p>
      <p className="mt-1 text-base font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

function StateRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2">
      <span className="text-sm font-medium text-[#7A625A]">{label}</span>
      <span className="break-words text-right text-sm font-semibold text-[#3B2924]">{value}</span>
    </div>
  );
}

function DetailRow({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon?: typeof CheckCircle2;
}) {
  return (
    <div className="rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 py-2 text-sm">
      <span className="text-xs font-semibold uppercase text-[#B47767]">{label}</span>
      <p className="mt-1 flex items-center gap-2 break-all font-semibold text-[#3B2924]">
        {Icon ? <Icon size={14} aria-hidden="true" /> : null}
        {value}
      </p>
    </div>
  );
}

function LinkButton({ href, label }: { href: Route; label: string }) {
  return (
    <Link
      className="inline-flex h-10 items-center justify-center rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C]"
      href={href}
    >
      {label}
    </Link>
  );
}

function FieldLabel({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-2 text-sm font-semibold text-[#3B2924]">
      {label}
      {children}
    </label>
  );
}

function StatusNotice({ message, error }: { message: string | null; error: string | null }) {
  if (!message && !error) {
    return null;
  }
  return (
    <div className="grid gap-2">
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

function getProjectHealth(project: Project) {
  if (project.status === "archived") {
    return { label: "Archived", score: 18, widthClass: "w-[18%]" };
  }
  const score = Math.min(96, 52 + project.sourceCount * 10 + project.intelligenceCount * 4);
  if (score >= 82) {
    return { label: "High coverage", score, widthClass: "w-[92%]" };
  }
  if (score >= 64) {
    return { label: "In progress", score, widthClass: "w-[72%]" };
  }
  return { label: "Needs setup", score, widthClass: "w-[52%]" };
}
