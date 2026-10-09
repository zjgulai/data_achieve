import { API_BASE_URL, ApiError, apiFetch } from "./client";

export type DatasetExportFormat = "csv" | "json" | "jsonl" | "xlsx";

export type Dataset = {
  id: string;
  project_id: string;
  name: string;
  /** Backend field is `dataset_type` (not `source_type`). */
  dataset_type: string;
  status: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type DatasetVersion = {
  id: string;
  dataset_id: string;
  cleaning_plan_id: string | null;
  version_number: number;
  source_task_run_ids: string[];
  source_workflow_run_id: string | null;
  selected_fields: string[];
  cleaning_script: string[];
  row_count: number;
  average_completeness_percent: number;
  status: string;
  created_at: string;
  export_preview: Record<string, unknown>;
};

export type DatasetListItem = {
  dataset: Dataset;
  latest_version: DatasetVersion | null;
  version_count: number;
  latest_drift_event: Record<string, unknown> | null;
  drift_event_count: number;
  /** Platforms derived server-side from the originating endpoint(s); may be empty. */
  platforms: string[];
  /** Coarse category from `dataset_type`; may be null. */
  category: string | null;
  collector_types: string[];
};

export type DatasetsListResponse = {
  items: DatasetListItem[];
  total: number;
};

export type ExportJob = {
  id: string;
  dataset: Dataset;
  version: DatasetVersion;
  export_format: DatasetExportFormat;
  status: string;
  filename: string;
  content_type: string;
  artifact_size_bytes: number;
  row_count: number;
  checksum_sha256: string;
  error_message: string | null;
  created_at: string;
  finished_at: string | null;
  download_url: string | null;
  blocked_reasons: string[];
};

export type DatasetPreviewRow = {
  row_id: string;
  task_run_id: string | null;
  raw_record_id: string | null;
  source_url: string | null;
  values: Record<string, unknown>;
  missing_fields: string[];
  completeness_percent: number;
};

export type DatasetVersionPreview = {
  dataset: Dataset;
  version: DatasetVersion;
  fields: string[];
  rows: DatasetPreviewRow[];
  total_rows: number;
  preview_row_count: number;
  average_completeness_percent: number;
  export_preview: Record<string, unknown>;
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

/**
 * Kick off an export.
 *
 * The backend requires `authorized` + `confirm_create` and returns the full
 * job — exports are rendered synchronously, so the response already carries a
 * `download_url` on success.
 */
export async function createExport(
  datasetId: string,
  versionId: string,
  format: DatasetExportFormat = "csv",
): Promise<ExportJob> {
  return apiFetch<ExportJob>("/api/automation/product-dataset-exports", {
    method: "POST",
    body: JSON.stringify({
      authorized: true,
      confirm_create: true,
      dataset_id: datasetId,
      dataset_version_id: versionId,
      export_format: format,
    }),
  });
}

/** Poll/refresh a single export job by id. */
export async function fetchExportJob(exportJobId: string): Promise<ExportJob> {
  return apiFetch<ExportJob>(
    `/api/automation/product-dataset-exports/${encodeURIComponent(exportJobId)}`,
  );
}

export type DatasetVersionsResponse = {
  dataset: Dataset;
  versions: DatasetVersion[];
  total: number;
};

export async function fetchDatasetVersions(
  datasetId: string,
  limit = 50,
): Promise<DatasetVersionsResponse> {
  const qs = new URLSearchParams({ limit: String(limit) });
  return apiFetch<DatasetVersionsResponse>(
    `/api/automation/product-datasets/${encodeURIComponent(datasetId)}/versions?${qs.toString()}`,
  );
}

/**
 * Archive a dataset (backend soft-deletes: `status = "archived"`).
 * Archived datasets leave the default list; pass `include_archived=true`
 * to the list call to still see them.
 */
export async function archiveDataset(datasetId: string): Promise<Dataset> {
  return apiFetch<Dataset>(
    `/api/automation/product-datasets/${encodeURIComponent(datasetId)}`,
    { method: "DELETE" },
  );
}

export async function fetchVersionPreview(
  datasetId: string,
  versionId: string,
  limit = 50,
): Promise<DatasetVersionPreview> {
  const qs = new URLSearchParams({ limit: String(limit) });
  return apiFetch<DatasetVersionPreview>(
    `/api/automation/product-datasets/${encodeURIComponent(datasetId)}` +
      `/versions/${encodeURIComponent(versionId)}/preview?${qs.toString()}`,
  );
}

function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null;
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (utf8) {
    try {
      return decodeURIComponent(utf8[1]);
    } catch {
      /* fall through to the ascii form */
    }
  }
  const ascii = /filename="?([^";]+)"?/i.exec(header);
  return ascii ? ascii[1] : null;
}

/**
 * Download an export artifact through the API (cookie-authenticated), then
 * hand the bytes to the browser. A plain `<a href>` cannot carry the API
 * origin or credentials reliably.
 */
export async function downloadExport(job: ExportJob): Promise<void> {
  if (!job.download_url) {
    throw new Error("导出尚未就绪");
  }
  const res = await fetch(`${API_BASE_URL}${job.download_url}`, {
    credentials: "include",
  });
  if (!res.ok) {
    throw new ApiError(res.status, `下载失败（HTTP ${res.status}）`);
  }
  const blob = await res.blob();
  const filename = filenameFromDisposition(res.headers.get("Content-Disposition")) ?? job.filename;
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

/** Export + download in one step, for the common "just give me the file" path. */
export async function exportAndDownload(
  datasetId: string,
  versionId: string,
  format: DatasetExportFormat = "csv",
): Promise<void> {
  const job = await createExport(datasetId, versionId, format);
  await downloadExport(job);
}
