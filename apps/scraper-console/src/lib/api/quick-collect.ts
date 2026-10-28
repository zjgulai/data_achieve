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

/**
 * 一次回执的全部内容。
 *
 * 后端 `QuickCollectResponse`（services/quick_collect_service.py:84）本来就返回
 * `records`、`output`、`usage`、`timing`。这里补齐，否则运行完只看得到记录条数，
 * 「运行即得结果」不成立。
 *
 * 四个字段都可能为空对象/空数组：采集失败、端点不返回结构化输出、
 * 或价格簿没有该端点的价格时都会如此。调用方必须容忍缺失。
 */
export type QuickCollectResponse = {
  task_run_id: string;
  task_id: string;
  source_id: string;
  status: string;
  records_count: number;
  error_message: string | null;
  /** 记录样本。后端最多给前 20 条。 */
  records: Record<string, unknown>[];
  /** 端点自己的结构化输出，形状随端点变化。 */
  output: Record<string, unknown>;
  /** 用量与费用。键名随后端变化，渲染前须自行判空。 */
  usage: Record<string, unknown>;
  /** 耗时。后端给 `duration_ms`。 */
  timing: Record<string, unknown>;
};

export async function postQuickCollect(
  req: QuickCollectRequest
): Promise<QuickCollectResponse> {
  return apiFetch<QuickCollectResponse>("/api/quick-collect", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
