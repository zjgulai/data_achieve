export type AlertChannel = "email" | "in_app" | "both";

export type AlertRule = {
  id: string;
  workspaceId: string;
  projectId: string | null;
  name: string;
  signalType: string;
  condition: Record<string, unknown>;
  channel: AlertChannel | string;
  enabled: boolean;
  createdAt: string;
};

export type AlertRuleCreateInput = {
  name: string;
  projectId?: string | null;
  signalType: string;
  condition: Record<string, unknown>;
  channel: AlertChannel;
  enabled: boolean;
};

export type AlertEvent = {
  id: string;
  ruleId: string;
  signalId: string;
  status: "triggered" | "sent" | "acknowledged" | "resolved" | string;
  payload: Record<string, unknown>;
  triggeredAt: string;
  sentAt: string | null;
};
