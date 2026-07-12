"use client";

import { useEffect, useState } from "react";

import { listProjects } from "@/lib/api/projects";
import {
  readSelectedProjectPreference,
  resolveSelectedProjectId,
  writeSelectedProjectId,
} from "@/lib/project-selection";
import type { Project } from "@/types/project";

const projectListUnavailableMessage = "项目列表暂不可用";
const projectPreferenceUnavailableMessage =
  "项目偏好暂不可用；当前选择未保存";

export function ProjectSelector() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [preferenceError, setPreferenceError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listProjects()
      .then((items) => {
        if (cancelled) {
          return;
        }
        const active = items.filter((item) => item.status === "active");
        const preference = readSelectedProjectPreference();
        const resolved = resolveSelectedProjectId(items, preference.value);
        let preferenceAvailable = preference.available;
        if (
          preferenceAvailable &&
          resolved !== preference.value &&
          !writeSelectedProjectId(resolved)
        ) {
          preferenceAvailable = false;
        }
        setProjects(active);
        setSelectedId(resolved);
        setError(null);
        setPreferenceError(
          preferenceAvailable ? null : projectPreferenceUnavailableMessage,
        );
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setProjects([]);
          setSelectedId(null);
          setError(projectListUnavailableMessage);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function select(value: string) {
    const next = value || null;
    if (writeSelectedProjectId(next)) {
      setSelectedId(next);
      setPreferenceError(null);
    } else {
      setPreferenceError(projectPreferenceUnavailableMessage);
    }
  }

  return (
    <div
      className="min-w-0 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2"
      data-project-filter-applied="false"
    >
      <label className="flex min-w-0 items-center gap-2 text-xs font-semibold text-[#5F5757]">
        <span className="shrink-0">项目</span>
        <select
          aria-describedby="global-project-filter-status"
          className="min-w-0 max-w-48 bg-transparent text-sm font-medium text-[#2E201C] outline-none disabled:cursor-not-allowed disabled:opacity-60"
          data-testid="global-project-selector"
          disabled={loading || Boolean(error)}
          onChange={(event) => select(event.target.value)}
          value={selectedId ?? ""}
        >
          <option value="">全部项目</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </label>
      <p
        className="mt-1 text-[11px] leading-4 text-[#8B7770]"
        id="global-project-filter-status"
      >
        当前页面未应用项目过滤（全局数据）
      </p>
      {error ? (
        <p className="mt-1 text-xs font-semibold text-[#B85F4F]" role="alert">
          {error}
        </p>
      ) : null}
      {preferenceError ? (
        <p className="mt-1 text-xs font-semibold text-[#B85F4F]" role="alert">
          {preferenceError}
        </p>
      ) : null}
    </div>
  );
}
