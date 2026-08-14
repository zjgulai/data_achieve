"use client";

import {
  addScopeDraft,
  plannerFieldErrorId,
  removeScopeDraft,
  type PlannerFieldErrors,
  type WorkflowPlannerDraft,
} from "@/lib/workflow-planner";
import type { CapabilityPlatform } from "@/types/capability";
import type {
  MonitoringScopeDraft,
  MonitoringScopeType,
  WorkflowPlannerMatchMode,
} from "@/types/workflow-planner";

export type PlannerScopeStepProps = {
  draft: WorkflowPlannerDraft;
  fieldErrors: PlannerFieldErrors;
  onDraftChange: (draft: WorkflowPlannerDraft) => void;
};

const scopeTypes: Array<{ value: MonitoringScopeType; label: string }> = [
  { value: "brand", label: "品牌" },
  { value: "category", label: "品类" },
  { value: "competitor", label: "竞品" },
  { value: "topic", label: "话题" },
  { value: "campaign", label: "Campaign" },
];

const matchModes: Array<{
  value: WorkflowPlannerMatchMode;
  label: string;
}> = [
  { value: "exact", label: "Exact" },
  { value: "phrase", label: "Phrase" },
  { value: "semantic", label: "Semantic intent" },
  { value: "hybrid", label: "Hybrid" },
];

const platforms: CapabilityPlatform[] = [
  "youtube",
  "reddit",
  "x",
  "instagram",
  "threads",
  "tiktok",
  "linkedin",
];

function lines(value: string): string[] {
  return value.split(/\r?\n/);
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

export function PlannerScopeStep({
  draft,
  fieldErrors,
  onDraftChange,
}: PlannerScopeStepProps) {
  function updateScope(
    index: number,
    update: Partial<MonitoringScopeDraft>,
  ) {
    onDraftChange({
      ...draft,
      scopes: draft.scopes.map((scope, scopeIndex) =>
        scopeIndex === index ? { ...scope, ...update } : scope,
      ),
      revision: draft.revision + 1,
    });
  }

  function togglePlatform(
    index: number,
    platform: CapabilityPlatform,
    checked: boolean,
  ) {
    const current = draft.scopes[index];
    if (!current) {
      return;
    }
    updateScope(index, {
      platforms: checked
        ? [...new Set([...current.platforms, platform])]
        : current.platforms.filter((value) => value !== platform),
    });
  }

  function updateSeedUrl(index: number, urlIndex: number, value: string) {
    const current = draft.scopes[index];
    if (!current) {
      return;
    }
    const seedUrls = current.seedUrls.length ? [...current.seedUrls] : [""];
    seedUrls[urlIndex] = value;
    updateScope(index, { seedUrls });
  }

  function addSeedUrl(index: number) {
    const current = draft.scopes[index];
    if (!current || current.seedUrls.length >= 100) {
      return;
    }
    updateScope(index, {
      seedUrls: current.seedUrls.length ? [...current.seedUrls, ""] : ["", ""],
    });
  }

  function removeSeedUrl(index: number, urlIndex: number) {
    const current = draft.scopes[index];
    if (!current) {
      return;
    }
    const seedUrls = current.seedUrls.filter(
      (_value, candidateIndex) => candidateIndex !== urlIndex,
    );
    updateScope(index, { seedUrls });
  }

  return (
    <section aria-labelledby="planner-scopes-heading" className="min-w-0">
      <div className="mb-6 flex min-w-0 flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9A7467]">
            Step 2
          </p>
          <h2
            className="mt-2 text-xl font-semibold text-[#2E201C]"
            id="planner-scopes-heading"
          >
            配置 Scope 与输入
          </h2>
          <p className="mt-2 text-sm leading-6 text-[#716562]">
            Seed URL 只做语法检查并交由后端分类；页面不会访问 URL。
          </p>
        </div>
        <button
          aria-label="添加 Scope"
          className="shrink-0 rounded-xl border border-[#C97865] bg-[#FFF6F1] px-4 py-2 text-sm font-semibold text-[#8A4436] disabled:cursor-not-allowed disabled:opacity-50"
          disabled={draft.scopes.length >= 20}
          onClick={() => onDraftChange(addScopeDraft(draft))}
          type="button"
        >
          添加 Scope
        </button>
      </div>

      <div
        {...errorProps("planner-scopes", fieldErrors)}
        className="min-w-0"
        id="planner-scopes"
        tabIndex={-1}
      >
        <FieldError fieldErrors={fieldErrors} fieldId="planner-scopes" />

        <div className="grid min-w-0 gap-5">
          {draft.scopes.map((scope, index) => {
          const typeId = `planner-scope-${index}-type`;
          const canonicalId = `planner-scope-${index}-canonical-term`;
          const aliasesId = `planner-scope-${index}-aliases`;
          const includeId = `planner-scope-${index}-include-terms`;
          const excludeId = `planner-scope-${index}-exclude-terms`;
          const accountsId = `planner-scope-${index}-official-accounts`;
          const languagesId = `planner-scope-${index}-languages`;
          const regionsId = `planner-scope-${index}-regions`;
          const matchModeId = `planner-scope-${index}-match-mode`;
          const scopePlatformsId = `planner-scope-${index}-platforms`;
          const seedUrlsId = `planner-scope-${index}-seed-urls`;
          const seedValues = scope.seedUrls.length ? scope.seedUrls : [""];

          return (
            <article
              className="min-w-0 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 sm:p-5"
              key={scope.scopeRef}
            >
              <div className="mb-5 flex min-w-0 items-center justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-semibold text-[#392823]">
                    Scope {index + 1}
                  </h3>
                  <p className="break-all text-xs text-[#8B7770]">
                    {scope.scopeRef}
                  </p>
                </div>
                <button
                  className="rounded-lg border border-[#E1D5CF] px-3 py-1.5 text-sm text-[#765B54] disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={draft.scopes.length === 1}
                  onClick={() =>
                    onDraftChange(removeScopeDraft(draft, scope.scopeRef))
                  }
                  type="button"
                >
                  删除 Scope
                </button>
              </div>

              <div className="grid min-w-0 gap-4 md:grid-cols-2">
                <div className="min-w-0">
                  <label
                    className="mb-2 block text-sm font-semibold text-[#463530]"
                    htmlFor={typeId}
                  >
                    Scope 类型
                  </label>
                  <select
                    {...errorProps(typeId, fieldErrors)}
                    className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
                    id={typeId}
                    onChange={(event) =>
                      updateScope(index, {
                        scopeType: event.target.value as MonitoringScopeType,
                      })
                    }
                    value={scope.scopeType}
                  >
                    {scopeTypes.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                  <FieldError fieldErrors={fieldErrors} fieldId={typeId} />
                </div>

                <div className="min-w-0">
                  <label
                    className="mb-2 block text-sm font-semibold text-[#463530]"
                    htmlFor={canonicalId}
                  >
                    核心词
                  </label>
                  <input
                    {...errorProps(canonicalId, fieldErrors)}
                    className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
                    id={canonicalId}
                    onChange={(event) =>
                      updateScope(index, { canonicalTerm: event.target.value })
                    }
                    placeholder="例如 Acme 或 running shoes"
                    type="text"
                    value={scope.canonicalTerm ?? ""}
                  />
                  <FieldError fieldErrors={fieldErrors} fieldId={canonicalId} />
                </div>

                {[
                  {
                    id: aliasesId,
                    label: "别名（每行一项）",
                    values: scope.aliases,
                    key: "aliases" as const,
                  },
                  {
                    id: includeId,
                    label: "包含词（每行一项）",
                    values: scope.includeTerms,
                    key: "includeTerms" as const,
                  },
                  {
                    id: excludeId,
                    label: "排除词（每行一项）",
                    values: scope.excludeTerms,
                    key: "excludeTerms" as const,
                  },
                  {
                    id: accountsId,
                    label: "官方账号（每行一项）",
                    values: scope.officialAccounts,
                    key: "officialAccounts" as const,
                  },
                ].map((field) => (
                  <div className="min-w-0" key={field.id}>
                    <label
                      className="mb-2 block text-sm font-semibold text-[#463530]"
                      htmlFor={field.id}
                    >
                      {field.label}
                    </label>
                    <textarea
                      {...errorProps(field.id, fieldErrors)}
                      className="min-h-24 w-full resize-y rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
                      id={field.id}
                      onChange={(event) =>
                        updateScope(index, {
                          [field.key]: lines(event.target.value),
                        })
                      }
                      value={field.values.join("\n")}
                    />
                    <FieldError
                      fieldErrors={fieldErrors}
                      fieldId={field.id}
                    />
                  </div>
                ))}

                <div className="min-w-0">
                  <label
                    className="mb-2 block text-sm font-semibold text-[#463530]"
                    htmlFor={languagesId}
                  >
                    Scope 语言（每行一项，留空继承默认值）
                  </label>
                  <textarea
                    {...errorProps(languagesId, fieldErrors)}
                    className="min-h-20 w-full resize-y rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
                    id={languagesId}
                    onChange={(event) =>
                      updateScope(index, {
                        languages: lines(event.target.value),
                      })
                    }
                    value={scope.languages.join("\n")}
                  />
                  <FieldError fieldErrors={fieldErrors} fieldId={languagesId} />
                </div>

                <div className="min-w-0">
                  <label
                    className="mb-2 block text-sm font-semibold text-[#463530]"
                    htmlFor={regionsId}
                  >
                    Scope 地区（每行一项，留空继承默认值）
                  </label>
                  <textarea
                    {...errorProps(regionsId, fieldErrors)}
                    className="min-h-20 w-full resize-y rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
                    id={regionsId}
                    onChange={(event) =>
                      updateScope(index, { regions: lines(event.target.value) })
                    }
                    value={scope.regions.join("\n")}
                  />
                  <FieldError fieldErrors={fieldErrors} fieldId={regionsId} />
                </div>

                <div className="min-w-0">
                  <label
                    className="mb-2 block text-sm font-semibold text-[#463530]"
                    htmlFor={matchModeId}
                  >
                    Match mode
                  </label>
                  <select
                    {...errorProps(matchModeId, fieldErrors)}
                    className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
                    id={matchModeId}
                    onChange={(event) =>
                      updateScope(index, {
                        matchMode:
                          (event.target.value as WorkflowPlannerMatchMode) ||
                          null,
                      })
                    }
                    value={scope.matchMode ?? ""}
                  >
                    <option value="">按 Scope 类型使用默认值</option>
                    {matchModes.map((mode) => (
                      <option key={mode.value} value={mode.value}>
                        {mode.label}
                      </option>
                    ))}
                  </select>
                  <FieldError fieldErrors={fieldErrors} fieldId={matchModeId} />
                </div>
              </div>

              <fieldset
                {...errorProps(scopePlatformsId, fieldErrors)}
                className="mt-5 min-w-0 rounded-xl border border-[#E6DCD6] p-3"
                id={scopePlatformsId}
                tabIndex={-1}
              >
                <legend className="px-1 text-sm font-semibold text-[#463530]">
                  Scope 平台（留空继承默认平台）
                </legend>
                <div className="mt-2 flex min-w-0 flex-wrap gap-3">
                  {platforms.map((platform) => {
                    const id = `planner-scope-${index}-platform-${platform}`;
                    return (
                      <label
                        className="flex items-center gap-2 text-sm text-[#5F5757]"
                        htmlFor={id}
                        key={platform}
                      >
                        <input
                          checked={scope.platforms.includes(platform)}
                          id={id}
                          onChange={(event) =>
                            togglePlatform(index, platform, event.target.checked)
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
                  fieldId={scopePlatformsId}
                />
              </fieldset>

              <fieldset
                {...errorProps(seedUrlsId, fieldErrors)}
                className="mt-5 min-w-0"
                id={seedUrlsId}
                tabIndex={-1}
              >
                <legend className="text-sm font-semibold text-[#463530]">
                  Seed URL
                </legend>
                <div className="mt-2 grid min-w-0 gap-2">
                  {seedValues.map((seedUrl, urlIndex) => {
                    const id = `planner-scope-${index}-seed-url-${urlIndex}`;
                    return (
                      <div className="min-w-0" key={`${scope.scopeRef}-${urlIndex}`}>
                        <div className="flex min-w-0 gap-2">
                          <label className="sr-only" htmlFor={id}>
                            Seed URL {urlIndex + 1}
                          </label>
                          <input
                            {...errorProps(id, fieldErrors)}
                            className="min-w-0 flex-1 rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm"
                            id={id}
                            onChange={(event) =>
                              updateSeedUrl(index, urlIndex, event.target.value)
                            }
                            placeholder="https://..."
                            type="url"
                            value={seedUrl}
                          />
                          <button
                            aria-label={`删除 Seed URL ${urlIndex + 1}`}
                            className="rounded-lg border border-[#E1D5CF] px-3 py-2 text-sm text-[#765B54]"
                            onClick={() => removeSeedUrl(index, urlIndex)}
                            type="button"
                          >
                            删除
                          </button>
                        </div>
                        <FieldError fieldErrors={fieldErrors} fieldId={id} />
                      </div>
                    );
                  })}
                </div>
                <FieldError fieldErrors={fieldErrors} fieldId={seedUrlsId} />
                <button
                  className="mt-3 rounded-lg border border-[#E1D5CF] px-3 py-2 text-sm font-medium text-[#765B54] disabled:opacity-50"
                  disabled={scope.seedUrls.length >= 100}
                  onClick={() => addSeedUrl(index)}
                  type="button"
                >
                  添加 Seed URL
                </button>
              </fieldset>
            </article>
          );
          })}
        </div>
      </div>
    </section>
  );
}
