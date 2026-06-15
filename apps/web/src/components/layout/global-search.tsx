"use client";

import { Search } from "lucide-react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { listEntities } from "@/lib/api/entities";
import { listIntelligence } from "@/lib/api/intelligence";
import { listProjects } from "@/lib/api/projects";

type SearchResult = {
  id: string;
  title: string;
  subtitle: string;
  href: Route;
  group: "项目" | "实体" | "情报";
};

export function GlobalSearch() {
  const router = useRouter();
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const normalizedQuery = query.trim().toLowerCase();
  const groupedResults = useMemo(() => {
    return results.reduce<Record<SearchResult["group"], SearchResult[]>>(
      (groups, result) => {
        groups[result.group].push(result);
        return groups;
      },
      { 项目: [], 实体: [], 情报: [] },
    );
  }, [results]);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  useEffect(() => {
    if (normalizedQuery.length < 2) {
      setResults([]);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    const timer = window.setTimeout(() => {
      Promise.all([listProjects(), listEntities(), listIntelligence()])
        .then(([projects, entities, intelligence]) => {
          if (cancelled) {
            return;
          }
          const nextResults: SearchResult[] = [
            ...projects
              .filter((project) =>
                matchesSearch(normalizedQuery, [
                  project.name,
                  project.description,
                  project.domain,
                  project.status,
                ]),
              )
              .slice(0, 4)
              .map((project) => ({
                id: `project-${project.id}`,
                title: project.name,
                subtitle: `${domainLabel(project.domain)} · ${project.status}`,
                href: "/projects" as Route,
                group: "项目" as const,
              })),
            ...entities
              .filter((entity) =>
                matchesSearch(normalizedQuery, [
                  entity.name,
                  entity.externalId,
                  entity.entityType,
                  entity.domain,
                ]),
              )
              .slice(0, 4)
              .map((entity) => ({
                id: `entity-${entity.id}`,
                title: entity.name,
                subtitle: `${entity.entityType} · ${entity.domain}`,
                href: "/entities" as Route,
                group: "实体" as const,
              })),
            ...intelligence
              .filter((item) =>
                matchesSearch(normalizedQuery, [
                  item.title,
                  item.summary,
                  item.domain,
                  item.intelligenceType,
                  item.status,
                ]),
              )
              .slice(0, 5)
              .map((item) => ({
                id: `intelligence-${item.id}`,
                title: item.title,
                subtitle: `${item.domain} · score ${item.finalScore.toFixed(0)}`,
                href: `/intelligence/${item.id}` as Route,
                group: "情报" as const,
              })),
          ];
          setResults(nextResults);
        })
        .catch(() => {
          if (!cancelled) {
            setResults([]);
            setError("搜索暂不可用");
          }
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false);
          }
        });
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [normalizedQuery]);

  function openResult(result: SearchResult) {
    setOpen(false);
    setQuery("");
    router.push(result.href);
  }

  function handleSubmit() {
    const firstResult = results[0];
    if (firstResult) {
      openResult(firstResult);
    }
  }

  return (
    <div className="relative w-full max-w-sm" ref={wrapperRef}>
      <label className="flex items-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-sm text-[#86868B]">
        <Search size={17} className="text-[#86868B]" aria-hidden="true" />
        <input
          aria-label="全局搜索"
          className="w-full border-0 bg-transparent outline-none"
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              handleSubmit();
            }
            if (event.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder="搜索项目、实体、情报"
          type="search"
          value={query}
        />
      </label>
      {open && query.trim().length > 0 ? (
        <div className="absolute right-0 z-30 mt-2 max-h-[420px] w-full overflow-y-auto rounded-2xl border border-[#E9E5E2] bg-white p-2 shadow-[0_18px_44px_rgba(35,26,26,0.12)]">
          {normalizedQuery.length < 2 ? (
            <p className="px-3 py-2 text-xs text-[#86868B]">继续输入至少 2 个字符</p>
          ) : null}
          {loading ? <p className="px-3 py-2 text-xs text-[#86868B]">搜索中</p> : null}
          {error ? <p className="px-3 py-2 text-xs font-semibold text-[#C25B6E]">{error}</p> : null}
          {!loading && !error && normalizedQuery.length >= 2 && results.length === 0 ? (
            <p className="px-3 py-2 text-xs text-[#86868B]">没有匹配结果</p>
          ) : null}
          {(["项目", "实体", "情报"] as const).map((group) =>
            groupedResults[group].length > 0 ? (
              <section className="py-1" key={group}>
                <p className="px-3 py-1 text-[11px] font-semibold uppercase text-[#B47767]">{group}</p>
                <div className="grid gap-1">
                  {groupedResults[group].map((result) => (
                    <button
                      className="min-w-0 rounded-xl px-3 py-2 text-left transition hover:bg-[#FBF8F5]"
                      key={result.id}
                      onClick={() => openResult(result)}
                      type="button"
                    >
                      <span className="block truncate text-sm font-semibold text-[#1D1D1F]">
                        {result.title}
                      </span>
                      <span className="mt-0.5 block truncate text-xs text-[#86868B]">
                        {result.subtitle}
                      </span>
                    </button>
                  ))}
                </div>
              </section>
            ) : null,
          )}
        </div>
      ) : null}
    </div>
  );
}

function matchesSearch(query: string, values: Array<string | null | undefined>) {
  return values.some((value) => value?.toLowerCase().includes(query));
}

function domainLabel(domain: string) {
  const labels: Record<string, string> = {
    agent: "Agent 生态",
    competitor: "竞品守望",
    ecommerce: "电商风向",
    governance: "合规边界",
    mixed: "混合项目",
    osint: "开源雷达",
    platform: "平台采集",
    social: "社媒脉搏",
  };
  return labels[domain] ?? domain;
}
