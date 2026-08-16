import type { Route } from "next";

export type IntelligenceScope = "all" | "training";

export type IntelligenceNavigationContext = {
  evidenceId: string | null;
  intelligenceId: string | null;
  projectId: string | null;
  scope: IntelligenceScope;
  status: string;
  type: string;
};

function optionalQueryValue(query: URLSearchParams, key: string): string | null {
  return query.get(key)?.trim() || null;
}

export function readIntelligenceNavigationContext(
  search: string,
): IntelligenceNavigationContext {
  const query = new URLSearchParams(search);
  return {
    evidenceId: optionalQueryValue(query, "evidence_id"),
    intelligenceId: optionalQueryValue(query, "intelligence_id"),
    projectId: optionalQueryValue(query, "project_id"),
    scope: query.get("scope") === "training" ? "training" : "all",
    status: optionalQueryValue(query, "status") ?? "",
    type: optionalQueryValue(query, "type") ?? "",
  };
}

function navigationQuery(
  context: IntelligenceNavigationContext,
): URLSearchParams {
  const query = new URLSearchParams();
  if (context.projectId) query.set("project_id", context.projectId);
  if (context.type) query.set("type", context.type);
  if (context.status) query.set("status", context.status);
  if (context.scope === "training") query.set("scope", context.scope);
  if (context.intelligenceId) {
    query.set("intelligence_id", context.intelligenceId);
    if (context.evidenceId) query.set("evidence_id", context.evidenceId);
  }
  return query;
}

function hrefWithQuery(pathname: string, query: URLSearchParams): Route {
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return `${pathname}${suffix}` as Route;
}

export function buildIntelligenceListHref(
  context: IntelligenceNavigationContext,
): Route {
  return hrefWithQuery("/intelligence", navigationQuery(context));
}

export function buildIntelligenceDetailHref(
  intelligenceId: string,
  context: IntelligenceNavigationContext,
): Route {
  return hrefWithQuery(
    `/intelligence/${encodeURIComponent(intelligenceId)}`,
    navigationQuery({
      ...context,
      intelligenceId,
    }),
  );
}

export function buildProjectScopedHref(
  href: string,
  projectId: string | null,
): Route {
  const url = new URL(href, "http://localhost");
  if (projectId) {
    url.searchParams.set("project_id", projectId);
  } else {
    url.searchParams.delete("project_id");
  }
  return `${url.pathname}${url.search}${url.hash}` as Route;
}
