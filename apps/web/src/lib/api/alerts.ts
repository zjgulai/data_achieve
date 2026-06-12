import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockAlertEvents, getMockAlertRules } from "@/lib/api/mock";
import type { AlertEvent, AlertRule, AlertRuleCreateInput } from "@/types/alert";

type AlertRuleResponse = {
  id: string;
  workspace_id: string;
  project_id: string | null;
  name: string;
  signal_type: string;
  condition: Record<string, unknown>;
  channel: string;
  enabled: boolean;
  created_at: string;
};

type AlertEventResponse = {
  id: string;
  rule_id: string;
  signal_id: string;
  status: string;
  payload: Record<string, unknown>;
  triggered_at: string;
  sent_at: string | null;
};

export async function listAlertRules(): Promise<AlertRule[]> {
  if (mockApiEnabled) {
    return getMockAlertRules();
  }
  const response = await apiFetch<AlertRuleResponse[]>("/api/alert-rules");
  return response.map(mapAlertRule);
}

export async function createAlertRule(input: AlertRuleCreateInput): Promise<AlertRule> {
  if (mockApiEnabled) {
    return {
      id: `rule_${Date.now()}`,
      workspaceId: "workspace_mock",
      projectId: input.projectId ?? null,
      name: input.name,
      signalType: input.signalType,
      condition: input.condition,
      channel: input.channel,
      enabled: input.enabled,
      createdAt: new Date().toISOString(),
    };
  }
  const response = await apiFetch<AlertRuleResponse>("/api/alert-rules", {
    method: "POST",
    body: JSON.stringify({
      name: input.name,
      project_id: input.projectId ?? null,
      signal_type: input.signalType,
      condition: input.condition,
      channel: input.channel,
      enabled: input.enabled,
    }),
  });
  return mapAlertRule(response);
}

export async function listAlertEvents(filters: {
  ruleId?: string;
  status?: string;
} = {}): Promise<AlertEvent[]> {
  if (mockApiEnabled) {
    return getMockAlertEvents().filter((event) => {
      return (
        (!filters.ruleId || event.ruleId === filters.ruleId) &&
        (!filters.status || event.status === filters.status)
      );
    });
  }
  const query = new URLSearchParams();
  if (filters.ruleId) {
    query.set("rule_id", filters.ruleId);
  }
  if (filters.status) {
    query.set("status", filters.status);
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  const response = await apiFetch<AlertEventResponse[]>(`/api/alert-events${suffix}`);
  return response.map(mapAlertEvent);
}

function mapAlertRule(response: AlertRuleResponse): AlertRule {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    name: response.name,
    signalType: response.signal_type,
    condition: response.condition,
    channel: response.channel,
    enabled: response.enabled,
    createdAt: response.created_at,
  };
}

function mapAlertEvent(response: AlertEventResponse): AlertEvent {
  return {
    id: response.id,
    ruleId: response.rule_id,
    signalId: response.signal_id,
    status: response.status,
    payload: response.payload,
    triggeredAt: response.triggered_at,
    sentAt: response.sent_at,
  };
}
