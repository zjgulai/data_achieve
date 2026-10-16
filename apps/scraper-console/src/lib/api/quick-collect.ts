import { apiFetch } from "./client";

/** 提交参数值。后端模型是 `dict[str, Any]`。 */
export type QuickCollectParamValue =
  | string
  | number
  | boolean
  | null
  | string[]
  | number[]
  | Record<string, unknown>;

export type QuickCollectRequest = {
  project_id: string;
  endpoint_type: string;
  params: Record<string, QuickCollectParamValue>;
  label?: string;
};

export type QuickCollectResponse = {
  task_run_id: string;
  task_id: string;
  source_id: string;
  status: string;
  records_count: number;
  error_message: string | null;
};

export async function postQuickCollect(
  req: QuickCollectRequest
): Promise<QuickCollectResponse> {
  return apiFetch<QuickCollectResponse>("/api/quick-collect", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
