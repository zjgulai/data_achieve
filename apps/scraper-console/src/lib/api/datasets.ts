import { apiFetch } from "./client";

export type Dataset = {
  id: string;
  name: string;
  project_id: string;
  source_type: string;
  record_type: string | null;
  created_at: string;
  updated_at: string;
};

export type DatasetVersion = {
  id: string;
  dataset_id: string;
  version_number: number;
  row_count: number;
  created_at: string;
  status: string;
};

export type DatasetListItem = {
  dataset: Dataset;
  latest_version: DatasetVersion | null;
  version_count: number;
};

export type DatasetsListResponse = {
  items: DatasetListItem[];
  total: number;
};

export type ExportJob = {
  id: string;
  status: string;
  filename: string;
  row_count: number;
  export_format: "csv" | "json" | "jsonl";
  download_url: string | null;
  created_at: string;
  finished_at: string | null;
};

export async function fetchDatasets(params?: {
  project_id?: string;
  limit?: number;
  offset?: number;
}): Promise<DatasetsListResponse> {
  const qs = new URLSearchParams();
  if (params?.project_id) qs.set("project_id", params.project_id);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const q = qs.toString();
  return apiFetch<DatasetsListResponse>(`/api/automation/product-datasets${q ? `?${q}` : ""}`);
}

export async function createExport(
  datasetId: string,
  versionId: string,
  format: "csv" | "json" | "jsonl" = "csv"
): Promise<{ export_job_id: string }> {
  return apiFetch<{ export_job_id: string }>("/api/automation/product-dataset-exports", {
    method: "POST",
    body: JSON.stringify({
      dataset_id: datasetId,
      dataset_version_id: versionId,
      export_format: format,
    }),
  });
}

export async function fetchExportJob(exportJobId: string): Promise<ExportJob> {
  return apiFetch<ExportJob>(`/api/automation/product-dataset-exports/${exportJobId}`);
}
