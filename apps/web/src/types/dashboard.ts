export type DashboardSummary = {
  intelligenceCount: number;
  taskSuccessRate: number;
  fieldCompleteness: number;
  activeAlerts: number;
  failedTasks: number;
  recentRuns: number;
  sourceCount: number;
  typeBreakdown: TypeBreakdownItem[];
  domainBreakdown: DomainBreakdownItem[];
  topIntelligence: IntelligenceSummaryItem[];
  taskHealth: TaskHealth;
};

export type TypeBreakdownItem = {
  type: string;
  count: number;
  percent: number;
};

export type IntelligenceSummaryItem = {
  id: string;
  title: string;
  summary: string;
  domain: string;
  type: string;
  evidenceCount: number;
  finalScore: number;
  status: string;
  createdAt: string;
};

export type DomainBreakdownItem = {
  domain: string;
  intelligenceCount: number;
  signalCount: number;
  projectCount: number;
};

export type TaskHealth = {
  totalTasks: number;
  enabledTasks: number;
  failedTasks: number;
  recentRuns: number;
  recentFailures: RecentFailureItem[];
};

export type RecentFailureItem = {
  taskId: string;
  taskName: string;
  status: string;
  errorMessage: string | null;
  createdAt: string;
};

export type DashboardFilters = {
  projectId?: string;
  domain?: string;
  from?: string;
  to?: string;
  limit?: number;
};
