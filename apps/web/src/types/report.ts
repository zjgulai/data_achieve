export type Report = {
  id: string;
  workspaceId: string;
  projectId: string | null;
  reportType: "daily" | string;
  title: string;
  content: string;
  status: "draft" | "generated" | "sent" | string;
  periodStart: string;
  periodEnd: string;
  createdAt: string;
};

export type ReportGenerateInput = {
  projectId?: string;
  reportType?: "daily";
};
