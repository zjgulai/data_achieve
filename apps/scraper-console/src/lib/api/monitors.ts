import { apiFetch } from "./client";

export type Monitor = Readonly<{
  id: string;
  project_id: string;
  name: string;
  endpoint_type: string;
  params: Record<string, unknown>;
  interval_hours: number;
  status: string;
  task_id: string | null;
  last_checked_at: string | null;
  last_new_count: number | null;
  created_at: string;
}>;

export function fetchMonitors(projectId?: string): Promise<Monitor[]> {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return apiFetch<Monitor[]>(`/api/monitors${query}`);
}

export function createMonitor(payload: {
  project_id: string;
  name: string;
  endpoint_type: string;
  params: Record<string, unknown>;
  interval_hours: number;
}): Promise<Monitor> {
  return apiFetch<Monitor>("/api/monitors", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function setMonitorStatus(
  monitorId: string,
  action: "pause" | "resume"
): Promise<Monitor> {
  return apiFetch<Monitor>(`/api/monitors/${monitorId}/${action}`, {
    method: "POST",
  });
}