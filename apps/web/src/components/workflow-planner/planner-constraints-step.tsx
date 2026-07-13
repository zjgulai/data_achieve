"use client";

import {
  plannerFieldErrorId,
  type PlannerFieldErrors,
  type WorkflowPlannerDraft,
} from "@/lib/workflow-planner";
import type { CapabilityPlatform } from "@/types/capability";
import type { ScheduleIntent } from "@/types/workflow-planner";

export type PlannerConstraintsStepProps = {
  draft: WorkflowPlannerDraft;
  fieldErrors: PlannerFieldErrors;
  onDraftChange: (draft: WorkflowPlannerDraft) => void;
};

const platforms: CapabilityPlatform[] = [
  "youtube",
  "reddit",
  "x",
  "instagram",
  "threads",
  "tiktok",
  "linkedin",
];

const deliveryOutputs = ["dataset", "alert", "brief"] as const;

function lines(value: string): string[] {
  return value.split(/\r?\n/);
}

function positiveInteger(value: string): number {
  return value === "" ? 0 : Number(value);
}

function FieldError({
  fieldId,
  fieldErrors,
}: {
  fieldId: string;
  fieldErrors: PlannerFieldErrors;
}) {
  const message = fieldErrors[fieldId];
  return message ? (
    <p
      className="mt-1 text-sm font-medium text-[#B85F4F]"
      id={plannerFieldErrorId(fieldId)}
      role="alert"
    >
      {message}
    </p>
  ) : null;
}

function errorProps(fieldId: string, fieldErrors: PlannerFieldErrors) {
  const invalid = Boolean(fieldErrors[fieldId]);
  return {
    "aria-describedby": invalid ? plannerFieldErrorId(fieldId) : undefined,
    "aria-invalid": invalid ? ("true" as const) : undefined,
  };
}

export function PlannerConstraintsStep({
  draft,
  fieldErrors,
  onDraftChange,
}: PlannerConstraintsStepProps) {
  function commit(update: Partial<WorkflowPlannerDraft>) {
    onDraftChange({ ...draft, ...update, revision: draft.revision + 1 });
  }

  function toggleDefaultPlatform(
    platform: CapabilityPlatform,
    checked: boolean,
  ) {
    commit({
      defaultPlatforms: checked
        ? [...new Set([...draft.defaultPlatforms, platform])]
        : draft.defaultPlatforms.filter((value) => value !== platform),
    });
  }

  function updateScheduleCadence(value: string) {
    if (!value) {
      commit({ scheduleIntent: null });
      return;
    }
    commit({
      scheduleIntent: {
        cadence: value as ScheduleIntent["cadence"],
        timezone: draft.scheduleIntent?.timezone ?? "",
      },
    });
  }

  function updateDelivery(output: (typeof deliveryOutputs)[number], checked: boolean) {
    const current = draft.deliveryIntent?.outputs ?? [];
    const outputs = checked
      ? [...new Set([...current, output])]
      : current.filter((value) => value !== output);
    commit({ deliveryIntent: outputs.length ? { outputs } : null });
  }

  return (
    <section aria-labelledby="planner-constraints-heading" className="min-w-0">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9A7467]">
          Step 3
        </p>
        <h2
          className="mt-2 text-xl font-semibold text-[#2E201C]"
          id="planner-constraints-heading"
        >
          配置平台与声明式约束
        </h2>
        <p className="mt-2 text-sm leading-6 text-[#716562]">
          这些值只参与计划预览，不会创建调度、预算账本或保留任务。
        </p>
      </div>

      <div className="grid min-w-0 gap-5">
        <fieldset
          {...errorProps("planner-default-platforms", fieldErrors)}
          className="min-w-0 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4"
          id="planner-default-platforms"
          tabIndex={-1}
        >
          <legend className="px-1 text-sm font-semibold text-[#463530]">
            默认平台
          </legend>
          <div className="mt-2 flex min-w-0 flex-wrap gap-3">
            {platforms.map((platform) => {
              const id = `planner-platform-${platform}`;
              return (
                <label
                  className="flex items-center gap-2 text-sm text-[#5F5757]"
                  htmlFor={id}
                  key={platform}
                >
                  <input
                    checked={draft.defaultPlatforms.includes(platform)}
                    id={id}
                    onChange={(event) =>
                      toggleDefaultPlatform(platform, event.target.checked)
                    }
                    type="checkbox"
                  />
                  {platform}
                </label>
              );
            })}
          </div>
          <FieldError
            fieldErrors={fieldErrors}
            fieldId="planner-default-platforms"
          />
        </fieldset>

        <div className="grid min-w-0 gap-4 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 md:grid-cols-2">
          <div className="min-w-0">
            <label
              className="mb-2 block text-sm font-semibold text-[#463530]"
              htmlFor="planner-default-languages"
            >
              默认语言（每行一项）
            </label>
            <textarea
              {...errorProps("planner-default-languages", fieldErrors)}
              className="min-h-24 w-full resize-y rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
              id="planner-default-languages"
              onChange={(event) =>
                commit({ defaultLanguages: lines(event.target.value) })
              }
              value={draft.defaultLanguages.join("\n")}
            />
            <FieldError
              fieldErrors={fieldErrors}
              fieldId="planner-default-languages"
            />
          </div>
          <div className="min-w-0">
            <label
              className="mb-2 block text-sm font-semibold text-[#463530]"
              htmlFor="planner-default-regions"
            >
              默认地区（每行一项）
            </label>
            <textarea
              {...errorProps("planner-default-regions", fieldErrors)}
              className="min-h-24 w-full resize-y rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
              id="planner-default-regions"
              onChange={(event) =>
                commit({ defaultRegions: lines(event.target.value) })
              }
              value={draft.defaultRegions.join("\n")}
            />
            <FieldError
              fieldErrors={fieldErrors}
              fieldId="planner-default-regions"
            />
          </div>
          <div className="min-w-0">
            <label
              className="mb-2 block text-sm font-semibold text-[#463530]"
              htmlFor="planner-required-fields"
            >
              Required Fields（每行一项）
            </label>
            <textarea
              {...errorProps("planner-required-fields", fieldErrors)}
              className="min-h-24 w-full resize-y rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
              id="planner-required-fields"
              onChange={(event) =>
                commit({ requiredFields: lines(event.target.value) })
              }
              value={draft.requiredFields.join("\n")}
            />
            <FieldError
              fieldErrors={fieldErrors}
              fieldId="planner-required-fields"
            />
          </div>
          <div className="min-w-0">
            <label
              className="mb-2 block text-sm font-semibold text-[#463530]"
              htmlFor="planner-optional-fields"
            >
              Optional Fields（每行一项）
            </label>
            <textarea
              {...errorProps("planner-optional-fields", fieldErrors)}
              className="min-h-24 w-full resize-y rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
              id="planner-optional-fields"
              onChange={(event) =>
                commit({ optionalFields: lines(event.target.value) })
              }
              value={draft.optionalFields.join("\n")}
            />
            <FieldError
              fieldErrors={fieldErrors}
              fieldId="planner-optional-fields"
            />
          </div>
        </div>

        {draft.mode === "periodic_monitoring" ? (
          <div className="grid min-w-0 gap-4 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 md:grid-cols-2">
            <div className="min-w-0">
              <label
                className="mb-2 block text-sm font-semibold text-[#463530]"
                htmlFor="planner-schedule-cadence"
              >
                周期
              </label>
              <select
                {...errorProps("planner-schedule-cadence", fieldErrors)}
                className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
                id="planner-schedule-cadence"
                onChange={(event) => updateScheduleCadence(event.target.value)}
                value={draft.scheduleIntent?.cadence ?? ""}
              >
                <option value="">请选择</option>
                <option value="hourly">每小时</option>
                <option value="daily">每天</option>
                <option value="weekly">每周</option>
              </select>
              <FieldError
                fieldErrors={fieldErrors}
                fieldId="planner-schedule-cadence"
              />
            </div>
            <div className="min-w-0">
              <label
                className="mb-2 block text-sm font-semibold text-[#463530]"
                htmlFor="planner-schedule-timezone"
              >
                时区
              </label>
              <input
                {...errorProps("planner-schedule-timezone", fieldErrors)}
                className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
                id="planner-schedule-timezone"
                onChange={(event) =>
                  commit({
                    scheduleIntent: {
                      cadence: draft.scheduleIntent?.cadence ?? "daily",
                      timezone: event.target.value,
                    },
                  })
                }
                placeholder="Asia/Shanghai"
                type="text"
                value={draft.scheduleIntent?.timezone ?? ""}
              />
              <FieldError
                fieldErrors={fieldErrors}
                fieldId="planner-schedule-timezone"
              />
            </div>
            <fieldset className="min-w-0 md:col-span-2">
              <legend className="text-sm font-semibold text-[#463530]">
                未来交付意图（阶段一不会交付）
              </legend>
              <div className="mt-2 flex flex-wrap gap-3">
                {deliveryOutputs.map((output) => {
                  const id = `planner-delivery-${output}`;
                  return (
                    <label
                      className="flex items-center gap-2 text-sm text-[#5F5757]"
                      htmlFor={id}
                      key={output}
                    >
                      <input
                        checked={
                          draft.deliveryIntent?.outputs.includes(output) ?? false
                        }
                        id={id}
                        onChange={(event) =>
                          updateDelivery(output, event.target.checked)
                        }
                        type="checkbox"
                      />
                      {output}
                    </label>
                  );
                })}
              </div>
            </fieldset>
          </div>
        ) : null}

        <div className="grid min-w-0 gap-4 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="min-w-0">
            <label
              className="mb-2 block text-sm font-semibold text-[#463530]"
              htmlFor="planner-amount"
            >
              预算上限（USD）
            </label>
            <input
              {...errorProps("planner-amount", fieldErrors)}
              className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
              id="planner-amount"
              min="0"
              onChange={(event) =>
                commit({
                  budgetCeiling: event.target.value
                    ? { amount: event.target.value, currency: "USD" }
                    : null,
                })
              }
              step="0.01"
              type="number"
              value={draft.budgetCeiling?.amount ?? ""}
            />
            <FieldError fieldErrors={fieldErrors} fieldId="planner-amount" />
          </div>
          <div className="min-w-0">
            <label
              className="mb-2 block text-sm font-semibold text-[#463530]"
              htmlFor="planner-max-requests"
            >
              最大请求数
            </label>
            <input
              {...errorProps("planner-max-requests", fieldErrors)}
              className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
              id="planner-max-requests"
              min="1"
              onChange={(event) =>
                commit({
                  rateLimitIntent: event.target.value
                    ? {
                        maxRequests: positiveInteger(event.target.value),
                        periodSeconds:
                          draft.rateLimitIntent?.periodSeconds ?? 60,
                      }
                    : null,
                })
              }
              step="1"
              type="number"
              value={draft.rateLimitIntent?.maxRequests || ""}
            />
            <FieldError
              fieldErrors={fieldErrors}
              fieldId="planner-max-requests"
            />
          </div>
          <div className="min-w-0">
            <label
              className="mb-2 block text-sm font-semibold text-[#463530]"
              htmlFor="planner-period-seconds"
            >
              请求周期（秒）
            </label>
            <input
              {...errorProps("planner-period-seconds", fieldErrors)}
              className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
              id="planner-period-seconds"
              min="1"
              onChange={(event) =>
                commit({
                  rateLimitIntent: event.target.value
                    ? {
                        maxRequests:
                          draft.rateLimitIntent?.maxRequests ?? 1,
                        periodSeconds: positiveInteger(event.target.value),
                      }
                    : null,
                })
              }
              step="1"
              type="number"
              value={draft.rateLimitIntent?.periodSeconds || ""}
            />
            <FieldError
              fieldErrors={fieldErrors}
              fieldId="planner-period-seconds"
            />
          </div>
          <div className="min-w-0">
            <label
              className="mb-2 block text-sm font-semibold text-[#463530]"
              htmlFor="planner-days"
            >
              保留天数
            </label>
            <input
              {...errorProps("planner-days", fieldErrors)}
              className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
              id="planner-days"
              max="3650"
              min="1"
              onChange={(event) =>
                commit({
                  retentionIntent: event.target.value
                    ? { days: positiveInteger(event.target.value) }
                    : null,
                })
              }
              step="1"
              type="number"
              value={draft.retentionIntent?.days || ""}
            />
            <FieldError fieldErrors={fieldErrors} fieldId="planner-days" />
          </div>
        </div>

        <label
          className="flex min-w-0 items-start gap-3 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 text-sm text-[#5F5757]"
          htmlFor="planner-allow-partial-degradation"
        >
          <input
            checked={draft.allowPartialDegradation}
            id="planner-allow-partial-degradation"
            onChange={(event) =>
              commit({ allowPartialDegradation: event.target.checked })
            }
            type="checkbox"
          />
          <span>
            允许查看字段降级方案。该意图不等于执行审批，Preview 仍固定
            execution_authorized=false。
          </span>
        </label>
      </div>
    </section>
  );
}
