export type SuccessfulRunStatus = "success" | "completed";

export function isSuccessfulRunStatus(status: string): status is SuccessfulRunStatus {
  return status === "success" || status === "completed";
}
