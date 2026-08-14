"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useProjectSelection } from "@/components/layout/project-selection-provider";
import { PlannerConstraintsStep } from "@/components/workflow-planner/planner-constraints-step";
import { PlannerModeStep } from "@/components/workflow-planner/planner-mode-step";
import { PlannerScopeStep } from "@/components/workflow-planner/planner-scope-step";
import { useUnsavedWorkflowPlannerGuard } from "@/components/workflow-planner/use-unsaved-workflow-planner-guard";
import { WorkflowPlanSavePanel } from "@/components/workflow-planner/workflow-plan-save-panel";
import { WorkflowPlanPreview } from "@/components/workflow-planner/workflow-plan-preview";
import { WorkflowPlannerStepper } from "@/components/workflow-planner/workflow-planner-stepper";
import { ApiRequestError } from "@/lib/api/client";
import {
  createWorkflowPlan,
  createWorkflowVersion,
  getWorkflowPlan,
  getWorkflowVersion,
} from "@/lib/api/workflow-plan-persistence";
import { previewWorkflowPlan } from "@/lib/api/workflow-plans";
import {
  buildPlanningInput,
  clonePlanningInput,
  createPreviewErrorState,
  createWorkflowPlannerDraft,
  invalidatePreviewRequest,
  plannerIssuesToFieldErrors,
  plannerStepForFieldId,
  shouldAcceptPreviewResponse,
  validatePlannerStep,
  workflowPlannerDraftFromEditableInput,
  workflowPlannerDraftSemanticKey,
  type PlannerFieldErrors,
  type PlannerStep,
  type PreviewRequestState,
  type PreviewSemanticContext,
  type PreviewSnapshot,
  type WorkflowPlannerDraft,
} from "@/lib/workflow-planner";
import type {
  WorkflowPlanDetail,
  WorkflowVersionDetail,
} from "@/types/workflow-plan-persistence";
import type { ProjectStatus } from "@/types/project";
import type { WorkflowPlannerMode } from "@/types/workflow-planner";

const steps: PlannerStep[] = ["mode", "scopes", "constraints", "preview"];

function previousSnapshot(
  state: PreviewRequestState,
): PreviewSnapshot | undefined {
  if (state.status === "success") {
    return state.snapshot;
  }
  return state.status === "loading" ? state.previous : undefined;
}

type PersistedPlanContext = {
  planId: string;
  projectId: string;
  name: string;
  mode: WorkflowPlannerMode;
  currentVersionId: string;
  currentVersionNumber: number;
  sourceVersionId: string | null;
  projectStatus: ProjectStatus;
};

type PlanLoadState =
  | { status: "ready" }
  | { status: "loading" }
  | { status: "error"; message: string };

type SaveRequestState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; message: string }
  | { status: "error"; message: string; retryable: boolean };

type LogicalSaveAttempt = {
  signature: string;
  idempotencyKey: string;
};

function persistenceSemanticKey(
  draft: WorkflowPlannerDraft,
  planName: string,
): string {
  return `${workflowPlannerDraftSemanticKey(draft)}\n${planName.trim()}`;
}

function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  );
}

function readableError(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function assertPlanDetailChain(
  detail: WorkflowPlanDetail,
  projectId: string,
  planId: string,
  mode: WorkflowPlannerMode,
): void {
  if (
    detail.plan.projectId !== projectId ||
    detail.plan.id !== planId ||
    detail.plan.flowMode !== mode ||
    detail.currentVersion.projectId !== projectId ||
    detail.currentVersion.workflowPlanId !== planId ||
    detail.currentVersion.id !== detail.plan.currentVersionId ||
    detail.currentVersion.versionNumber !== detail.plan.currentVersionNumber ||
    detail.currentVersion.editableInput.flowMode !== mode
  ) {
    throw new Error("WorkflowPlan route context mismatch");
  }
}

function assertSourceVersionChain(
  detail: WorkflowVersionDetail,
  projectId: string,
  planId: string,
  sourceVersionId: string,
  mode: WorkflowPlannerMode,
): void {
  if (
    detail.plan.projectId !== projectId ||
    detail.plan.id !== planId ||
    detail.plan.flowMode !== mode ||
    detail.version.projectId !== projectId ||
    detail.version.workflowPlanId !== planId ||
    detail.version.id !== sourceVersionId ||
    detail.version.editableInput.flowMode !== mode
  ) {
    throw new Error("WorkflowVersion route context mismatch");
  }
}

export function WorkflowPlannerWorkspace({
  initialMode,
  initialProjectId = null,
  initialPlanId = null,
  initialSourceVersionId = null,
  routeError = null,
}: {
  initialMode: WorkflowPlannerMode;
  initialProjectId?: string | null;
  initialPlanId?: string | null;
  initialSourceVersionId?: string | null;
  routeError?: string | null;
}) {
  const {
    projects,
    selectedProject,
    loading,
    projectListError,
    selectProject,
    markProjectFilterApplied,
    clearProjectFilterApplied,
  } = useProjectSelection();
  const [draft, setDraft] = useState<WorkflowPlannerDraft>(() =>
    createWorkflowPlannerDraft(initialMode),
  );
  const [stepIndex, setStepIndex] = useState(0);
  const [fieldErrors, setFieldErrors] = useState<PlannerFieldErrors>({});
  const [previewState, setPreviewState] = useState<PreviewRequestState>({
    status: "idle",
  });
  const [planName, setPlanName] = useState("");
  const [planContext, setPlanContext] = useState<PersistedPlanContext | null>(
    null,
  );
  const [planLoadState, setPlanLoadState] = useState<PlanLoadState>(() =>
    routeError
      ? { status: "error", message: routeError }
      : initialPlanId
        ? { status: "loading" }
        : { status: "ready" },
  );
  const [saveState, setSaveState] = useState<SaveRequestState>({
    status: "idle",
  });
  const [semanticBaseline, setSemanticBaseline] = useState(() =>
    persistenceSemanticKey(createWorkflowPlannerDraft(initialMode), ""),
  );
  const workspaceRef = useRef<HTMLDivElement>(null);
  const requestSequenceRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const previousProjectIdRef = useRef(selectedProject?.id ?? null);
  const planLoadControllerRef = useRef<AbortController | null>(null);
  const saveControllerRef = useRef<AbortController | null>(null);
  const saveSequenceRef = useRef(0);
  const logicalSaveAttemptRef = useRef<LogicalSaveAttempt | null>(null);
  const previewStateRef = useRef(previewState);
  const currentContextRef = useRef<PreviewSemanticContext>({
    projectId: selectedProject?.id ?? null,
    mode: draft.mode,
    formRevision: draft.revision,
  });
  const currentStep = steps[stepIndex] ?? "mode";
  const dirty = persistenceSemanticKey(draft, planName) !== semanticBaseline;

  useUnsavedWorkflowPlannerGuard(dirty);

  previewStateRef.current = previewState;
  currentContextRef.current = {
    projectId: selectedProject?.id ?? null,
    mode: draft.mode,
    formRevision: draft.revision,
  };

  useEffect(() => {
    if (routeError) {
      setPlanLoadState({ status: "error", message: routeError });
      return;
    }
    if (initialPlanId && !initialProjectId) {
      setPlanLoadState({
        status: "error",
        message: "plan_id requires project_id",
      });
      return;
    }
    if (initialProjectId && loading) {
      return;
    }
    if (initialProjectId && projectListError && !initialPlanId) {
      setPlanLoadState({ status: "error", message: projectListError });
      return;
    }
    if (initialProjectId && selectedProject?.id !== initialProjectId) {
      if (projects.some((project) => project.id === initialProjectId)) {
        selectProject(initialProjectId);
        setPlanLoadState({ status: "loading" });
        return;
      }
      if (!initialPlanId) {
        setPlanLoadState({
          status: "error",
          message: "WorkflowPlan Project context mismatch",
        });
        return;
      }
    }
    if (!initialPlanId) {
      setPlanLoadState({ status: "ready" });
      return;
    }
    if (!initialProjectId) {
      return;
    }

    planLoadControllerRef.current?.abort();
    const controller = new AbortController();
    planLoadControllerRef.current = controller;
    setPlanLoadState({ status: "loading" });
    const options = { signal: controller.signal };
    const planRequest = getWorkflowPlan(
      initialProjectId,
      initialPlanId,
      options,
    );
    const sourceRequest = initialSourceVersionId
      ? getWorkflowVersion(
          initialProjectId,
          initialPlanId,
          initialSourceVersionId,
          options,
        )
      : Promise.resolve(null);

    void Promise.all([planRequest, sourceRequest])
      .then(([detail, sourceDetail]) => {
        if (controller.signal.aborted) {
          return;
        }
        assertPlanDetailChain(
          detail,
          initialProjectId,
          initialPlanId,
          initialMode,
        );
        if (sourceDetail && initialSourceVersionId) {
          assertSourceVersionChain(
            sourceDetail,
            initialProjectId,
            initialPlanId,
            initialSourceVersionId,
            initialMode,
          );
          if (sourceDetail.projectStatus !== detail.projectStatus) {
            throw new Error("WorkflowVersion Project status mismatch");
          }
        }
        const sourceVersion = sourceDetail?.version ?? detail.currentVersion;
        const hydrated = workflowPlannerDraftFromEditableInput(
          sourceVersion.editableInput,
        );
        setDraft(hydrated);
        setPlanName(detail.plan.name);
        setPlanContext({
          planId: detail.plan.id,
          projectId: detail.plan.projectId,
          name: detail.plan.name,
          mode: detail.plan.flowMode,
          currentVersionId: detail.plan.currentVersionId,
          currentVersionNumber: detail.plan.currentVersionNumber,
          sourceVersionId: initialSourceVersionId,
          projectStatus: detail.projectStatus,
        });
        setSemanticBaseline(persistenceSemanticKey(hydrated, detail.plan.name));
        setStepIndex(0);
        setFieldErrors({});
        setPreviewState({ status: "idle" });
        setSaveState({ status: "idle" });
        logicalSaveAttemptRef.current = null;
        setPlanLoadState({ status: "ready" });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || isAbortError(error)) {
          return;
        }
        setPlanLoadState({
          status: "error",
          message: readableError(
            error,
            "WorkflowPlan persistence context unavailable",
          ),
        });
      })
      .finally(() => {
        if (planLoadControllerRef.current === controller) {
          planLoadControllerRef.current = null;
        }
      });

    return () => {
      controller.abort();
      if (planLoadControllerRef.current === controller) {
        planLoadControllerRef.current = null;
      }
    };
  }, [
    initialMode,
    initialPlanId,
    initialProjectId,
    initialSourceVersionId,
    loading,
    projectListError,
    projects,
    routeError,
    selectProject,
    selectedProject?.id,
  ]);

  const invalidateActiveSave = useCallback(() => {
    saveControllerRef.current?.abort();
    saveControllerRef.current = null;
    saveSequenceRef.current += 1;
    logicalSaveAttemptRef.current = null;
    setSaveState({ status: "idle" });
  }, []);

  const invalidateActivePreview = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    requestSequenceRef.current += 1;
    invalidateActiveSave();
    setPreviewState((current) => invalidatePreviewRequest(current));
    clearProjectFilterApplied();
  }, [clearProjectFilterApplied, invalidateActiveSave]);

  const updateDraft = useCallback(
    (nextDraft: WorkflowPlannerDraft) => {
      invalidateActivePreview();
      setDraft(nextDraft);
      setFieldErrors({});
    },
    [invalidateActivePreview],
  );

  const updatePlanName = useCallback(
    (name: string) => {
      invalidateActiveSave();
      setPlanName(name);
    },
    [invalidateActiveSave],
  );

  useEffect(() => {
    clearProjectFilterApplied();
    return () => {
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      planLoadControllerRef.current?.abort();
      planLoadControllerRef.current = null;
      saveControllerRef.current?.abort();
      saveControllerRef.current = null;
      saveSequenceRef.current += 1;
      requestSequenceRef.current += 1;
      clearProjectFilterApplied();
    };
  }, [clearProjectFilterApplied]);

  useEffect(() => {
    const projectId = selectedProject?.id ?? null;
    if (previousProjectIdRef.current !== projectId) {
      previousProjectIdRef.current = projectId;
      invalidateActivePreview();
      setFieldErrors({});
    }
  }, [invalidateActivePreview, selectedProject?.id]);

  function focusFirstInvalidField() {
    window.requestAnimationFrame(() => {
      workspaceRef.current
        ?.querySelector<HTMLElement>('[aria-invalid="true"]')
        ?.focus();
    });
  }

  function showFieldErrors(errors: PlannerFieldErrors) {
    const firstFieldId = Object.keys(errors)[0];
    setFieldErrors(errors);
    if (firstFieldId) {
      const targetStep = plannerStepForFieldId(firstFieldId);
      setStepIndex(steps.indexOf(targetStep));
      focusFirstInvalidField();
    }
  }

  function goNext() {
    if (currentStep === "preview") {
      return;
    }
    const issues = validatePlannerStep(draft, currentStep);
    if (issues.length > 0) {
      showFieldErrors(plannerIssuesToFieldErrors(issues));
      return;
    }
    setFieldErrors({});
    setStepIndex((current) => Math.min(current + 1, steps.length - 1));
  }

  function goBack() {
    setFieldErrors({});
    setStepIndex((current) => Math.max(current - 1, 0));
  }

  async function generatePreview() {
    const projectId = selectedProject?.id;
    if (
      !projectId ||
      loading ||
      projectListError ||
      planLoadState.status !== "ready" ||
      (initialProjectId !== null && initialProjectId !== projectId) ||
      (planContext !== null && planContext.projectId !== projectId) ||
      (planContext !== null && planContext.projectStatus !== "active") ||
      (planContext !== null && planContext.mode !== draft.mode)
    ) {
      return;
    }

    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    const sequence = requestSequenceRef.current + 1;
    requestSequenceRef.current = sequence;
    invalidateActiveSave();
    clearProjectFilterApplied();

    const allIssues = (["mode", "scopes", "constraints"] as const).flatMap(
      (step) => validatePlannerStep(draft, step),
    );
    if (allIssues.length > 0) {
      setPreviewState((current) => invalidatePreviewRequest(current));
      showFieldErrors(plannerIssuesToFieldErrors(allIssues));
      return;
    }

    const input = clonePlanningInput(buildPlanningInput(draft));
    const responseContext: PreviewSemanticContext = {
      projectId,
      mode: draft.mode,
      formRevision: draft.revision,
    };
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const previous = previousSnapshot(previewStateRef.current);
    setFieldErrors({});
    setPreviewState({
      status: "loading",
      sequence,
      ...(previous ? { previous } : {}),
    });

    try {
      const preview = await previewWorkflowPlan(projectId, input, {
        signal: controller.signal,
      });
      if (
        !shouldAcceptPreviewResponse({
          responseSequence: sequence,
          currentSequence: requestSequenceRef.current,
          responseContext,
          currentContext: currentContextRef.current,
        })
      ) {
        return;
      }
      const snapshot: PreviewSnapshot = {
        projectId,
        mode: responseContext.mode,
        formRevision: responseContext.formRevision,
        previewInput: input,
        preview,
      };
      setPreviewState({ status: "success", snapshot, stale: false });
      markProjectFilterApplied(projectId);
    } catch (error) {
      if (
        !shouldAcceptPreviewResponse({
          responseSequence: sequence,
          currentSequence: requestSequenceRef.current,
          responseContext,
          currentContext: currentContextRef.current,
        })
      ) {
        return;
      }
      const errorState = createPreviewErrorState(error);
      if (!errorState) {
        setPreviewState(
          previous
            ? { status: "success", snapshot: previous, stale: true }
            : { status: "idle" },
        );
        return;
      }
      setPreviewState(errorState);
      if (Object.keys(errorState.fieldErrors).length > 0) {
        showFieldErrors(errorState.fieldErrors);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
    }
  }

  async function savePreview() {
    if (
      previewState.status !== "success" ||
      previewState.stale ||
      planLoadState.status !== "ready" ||
      saveState.status === "loading"
    ) {
      return;
    }
    const snapshot = previewState.snapshot;
    const projectId = selectedProject?.id;
    const trimmedName = planName.trim();
    if (
      !projectId ||
      snapshot.projectId !== projectId ||
      snapshot.mode !== draft.mode ||
      (initialProjectId !== null && initialProjectId !== projectId) ||
      (planContext !== null && planContext.projectId !== projectId) ||
      (planContext !== null && planContext.projectStatus !== "active") ||
      (!planContext && (trimmedName.length < 1 || trimmedName.length > 200)) ||
      (planContext !== null &&
        (planContext.mode !== draft.mode || planContext.name !== planName))
    ) {
      return;
    }

    const signature = JSON.stringify({
      projectId,
      planId: planContext?.planId ?? null,
      planName: planContext?.name ?? trimmedName,
      currentVersionId: planContext?.currentVersionId ?? null,
      previewSequence: requestSequenceRef.current,
      previewFingerprint: snapshot.preview.previewFingerprint,
      previewInput: snapshot.previewInput,
    });
    if (logicalSaveAttemptRef.current?.signature !== signature) {
      logicalSaveAttemptRef.current = {
        signature,
        idempotencyKey: crypto.randomUUID(),
      };
    }
    const idempotencyKey = logicalSaveAttemptRef.current.idempotencyKey;
    const savedSemanticBaseline = persistenceSemanticKey(
      draft,
      planContext?.name ?? trimmedName,
    );
    const saveSequence = saveSequenceRef.current + 1;
    saveSequenceRef.current = saveSequence;
    const controller = new AbortController();
    saveControllerRef.current?.abort();
    saveControllerRef.current = controller;
    setSaveState({ status: "loading" });

    try {
      const result = planContext
        ? await createWorkflowVersion(
            projectId,
            planContext.planId,
            {
              previewInput: snapshot.previewInput,
              expectedPreviewFingerprint: snapshot.preview.previewFingerprint,
              expectedCurrentVersionId: planContext.currentVersionId,
              idempotencyKey,
            },
            { signal: controller.signal },
          )
        : await createWorkflowPlan(
            projectId,
            {
              name: trimmedName,
              previewInput: snapshot.previewInput,
              expectedPreviewFingerprint: snapshot.preview.previewFingerprint,
              idempotencyKey,
            },
            { signal: controller.signal },
          );
      if (
        saveSequence !== saveSequenceRef.current ||
        controller.signal.aborted ||
        result.plan.projectId !== projectId ||
        result.plan.flowMode !== snapshot.mode ||
        result.version.projectId !== projectId ||
        result.version.workflowPlanId !== result.plan.id ||
        result.version.id !== result.plan.currentVersionId ||
        result.version.versionNumber !== result.plan.currentVersionNumber ||
        result.version.previewFingerprint !==
          snapshot.preview.previewFingerprint ||
        (planContext !== null && result.plan.id !== planContext.planId)
      ) {
        if (!controller.signal.aborted) {
          throw new Error("WorkflowPlan save response context mismatch");
        }
        return;
      }

      const creatingPlan = planContext === null;
      setPlanContext({
        planId: result.plan.id,
        projectId: result.plan.projectId,
        name: result.plan.name,
        mode: result.plan.flowMode,
        currentVersionId: result.plan.currentVersionId,
        currentVersionNumber: result.plan.currentVersionNumber,
        sourceVersionId: planContext?.sourceVersionId ?? null,
        projectStatus: "active",
      });
      setPlanName(result.plan.name);
      setSemanticBaseline(savedSemanticBaseline);
      logicalSaveAttemptRef.current = null;
      const saveMessage =
        result.outcome === "semantic_no_op"
          ? "语义未变化，未创建新 Version。"
          : creatingPlan
            ? `已创建 Plan 与 Version v${result.version.versionNumber}。`
            : `已创建 Version v${result.version.versionNumber}。`;
      setSaveState({
        status: "success",
        message: result.idempotentReplay
          ? result.outcome === "semantic_no_op"
            ? "已确认先前保存结果（idempotent replay）；语义未变化，未创建新 Version，本次未重复写入。"
            : `已确认先前保存结果（idempotent replay）；Plan 当前 Version 为 v${result.version.versionNumber}，本次未重复写入。`
          : saveMessage,
      });
    } catch (error) {
      if (
        saveSequence !== saveSequenceRef.current ||
        controller.signal.aborted ||
        isAbortError(error)
      ) {
        return;
      }
      if (error instanceof ApiRequestError && error.code === "preview_stale") {
        logicalSaveAttemptRef.current = null;
        setPreviewState((current) => invalidatePreviewRequest(current));
        setSaveState({
          status: "error",
          message: "Preview 已过期；已保留草稿，请重新生成 Preview 后再保存。",
          retryable: false,
        });
        return;
      }
      if (
        error instanceof ApiRequestError &&
        error.code === "version_conflict" &&
        planContext
      ) {
        logicalSaveAttemptRef.current = null;
        setPreviewState((current) => invalidatePreviewRequest(current));
        try {
          const refreshed = await getWorkflowPlan(
            projectId,
            planContext.planId,
            { signal: controller.signal },
          );
          assertPlanDetailChain(
            refreshed,
            projectId,
            planContext.planId,
            planContext.mode,
          );
          if (saveSequence !== saveSequenceRef.current) {
            return;
          }
          const refreshedBaselineDraft = workflowPlannerDraftFromEditableInput(
            refreshed.currentVersion.editableInput,
          );
          setSemanticBaseline(
            persistenceSemanticKey(refreshedBaselineDraft, refreshed.plan.name),
          );
          setPlanContext((current) =>
            current
              ? {
                  ...current,
                  name: refreshed.plan.name,
                  currentVersionId: refreshed.plan.currentVersionId,
                  currentVersionNumber: refreshed.plan.currentVersionNumber,
                  projectStatus: refreshed.projectStatus,
                }
              : current,
          );
          setPlanName(refreshed.plan.name);
          setSaveState({
            status: "error",
            message:
              "当前 Version 已推进；已刷新并发基线，保留本地草稿，未自动合并或重提。请重新生成 Preview。",
            retryable: false,
          });
        } catch (refreshError) {
          if (
            saveSequence !== saveSequenceRef.current ||
            controller.signal.aborted ||
            isAbortError(refreshError)
          ) {
            return;
          }
          setSaveState({
            status: "error",
            message: `Version 冲突且最新基线读取失败：${readableError(
              refreshError,
              "persistence unavailable",
            )}`,
            retryable: false,
          });
        }
        return;
      }
      const retryable =
        !(error instanceof ApiRequestError) || error.status >= 500;
      if (!retryable) {
        logicalSaveAttemptRef.current = null;
      }
      setSaveState({
        status: "error",
        message: readableError(error, "WorkflowPlan 保存失败"),
        retryable,
      });
    } finally {
      if (saveControllerRef.current === controller) {
        saveControllerRef.current = null;
      }
    }
  }

  function renderPreviewStep() {
    return (
      <section aria-labelledby="planner-preview-heading" className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9A7467]">
          Step 4
        </p>
        <h2
          className="mt-2 text-xl font-semibold text-[#2E201C]"
          id="planner-preview-heading"
        >
          WorkflowPlan Preview
        </h2>

        <div className="mt-5 min-w-0 space-y-4">
          {previewState.status === "idle" ? (
            <div className="min-w-0 rounded-2xl border border-dashed border-[#DCCDC5] bg-[#FBF8F5] p-5">
              <p className="font-semibold text-[#463530]">尚未生成 Preview</p>
              <p className="mt-2 text-sm leading-6 text-[#716562]">
                生成只会请求 write-free Preview，不会保存、激活或调用 Provider。
              </p>
            </div>
          ) : null}

          {previewState.status === "loading" ? (
            <div className="min-w-0 space-y-4" aria-busy="true">
              <p
                className="rounded-xl border border-[#DDD2CB] bg-[#FBF8F5] px-4 py-3 text-sm font-semibold text-[#6D514A]"
                role="status"
              >
                正在生成 Preview…
              </p>
              {previewState.previous ? (
                <WorkflowPlanPreview
                  preview={previewState.previous.preview}
                  stale
                />
              ) : null}
            </div>
          ) : null}

          {previewState.status === "success" ? (
            <>
              <WorkflowPlanPreview
                preview={previewState.snapshot.preview}
                stale={previewState.stale}
              />
              {!previewState.stale ? (
                <WorkflowPlanSavePanel
                  canSave={
                    planLoadState.status === "ready" &&
                    !loading &&
                    !projectListError &&
                    selectedProject?.id === previewState.snapshot.projectId &&
                    previewState.snapshot.mode === draft.mode &&
                    (initialProjectId === null ||
                      initialProjectId === selectedProject.id) &&
                    (planContext === null ||
                      (planContext.projectStatus === "active" &&
                        planContext.projectId === selectedProject.id &&
                        planContext.mode === draft.mode &&
                        planContext.name === planName)) &&
                    (saveState.status === "idle" ||
                      (saveState.status === "error" && saveState.retryable)) &&
                    (planContext !== null ||
                      (planName.trim().length >= 1 &&
                        planName.trim().length <= 200))
                  }
                  currentVersionNumber={
                    planContext?.currentVersionNumber ?? null
                  }
                  error={
                    saveState.status === "error" ? saveState.message : null
                  }
                  message={
                    saveState.status === "success" ? saveState.message : null
                  }
                  mode={draft.mode}
                  onPlanNameChange={updatePlanName}
                  onSave={() => void savePreview()}
                  planName={planName}
                  planNameLocked={planContext !== null}
                  planningStatus={previewState.snapshot.preview.planningStatus}
                  retryable={
                    saveState.status === "error" && saveState.retryable
                  }
                  saving={saveState.status === "loading"}
                  sourceVersionId={planContext?.sourceVersionId ?? null}
                />
              ) : null}
            </>
          ) : null}

          {previewState.status === "success" &&
          previewState.stale &&
          saveState.status === "error" ? (
            <p
              className="rounded-xl border border-[#E4B9A7] bg-[#FFF5EF] px-4 py-3 text-sm font-semibold text-[#803F32]"
              role="alert"
            >
              {saveState.message}
            </p>
          ) : null}

          {previewState.status === "error" ? (
            <div
              className="min-w-0 rounded-2xl border border-[#E4B9A7] bg-[#FFF5EF] p-5"
              role="alert"
            >
              <p className="font-semibold text-[#803F32]">
                {previewState.message}
              </p>
              {previewState.httpStatus !== null ? (
                <p className="mt-2 text-sm text-[#765B54]">
                  HTTP {previewState.httpStatus}
                </p>
              ) : null}
              {previewState.requestId ? (
                <p className="mt-1 break-all font-mono text-xs text-[#765B54]">
                  request_id={previewState.requestId}
                </p>
              ) : null}
              {previewState.retryable ? (
                <button
                  className="mt-4 rounded-xl border border-[#C97865] bg-white px-4 py-2 text-sm font-semibold text-[#803F32]"
                  onClick={() => void generatePreview()}
                  type="button"
                >
                  重试
                </button>
              ) : null}
            </div>
          ) : null}

          {!loading && !selectedProject ? (
            <p className="text-sm font-semibold text-[#B85F4F]" role="alert">
              请先选择一个 active Project
            </p>
          ) : null}
          {projectListError ? (
            <p className="text-sm font-semibold text-[#B85F4F]" role="alert">
              {projectListError}
            </p>
          ) : null}
          <button
            aria-busy={previewState.status === "loading"}
            className="rounded-xl bg-[#9F4E3D] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-[#CDBEB9]"
            data-testid="workflow-planner-generate-preview"
            disabled={
              loading ||
              !selectedProject ||
              Boolean(projectListError) ||
              planLoadState.status !== "ready" ||
              (planContext !== null &&
                planContext.projectStatus !== "active") ||
              (planContext !== null &&
                planContext.projectId !== selectedProject.id) ||
              (initialProjectId !== null &&
                initialProjectId !== selectedProject.id)
            }
            onClick={() => void generatePreview()}
            type="button"
          >
            生成 Preview
          </button>
        </div>
      </section>
    );
  }

  return (
    <div
      className="min-w-0 space-y-5"
      data-testid="workflow-planner-workspace"
      ref={workspaceRef}
    >
      <WorkflowPlannerStepper currentStep={currentStep} />

      {planLoadState.status === "loading" ? (
        <p
          className="rounded-xl border border-[#DDD2CB] bg-[#FBF8F5] px-4 py-3 text-sm font-semibold text-[#6D514A]"
          role="status"
        >
          正在读取 WorkflowPlan 与 Version…
        </p>
      ) : null}
      {planLoadState.status === "error" ? (
        <p
          className="rounded-xl border border-[#E4B9A7] bg-[#FFF5EF] px-4 py-3 text-sm font-semibold text-[#803F32]"
          role="alert"
        >
          {planLoadState.message}
        </p>
      ) : null}

      <section className="min-w-0 rounded-2xl border border-[#E9E5E2] bg-white p-4 shadow-sm sm:p-6">
        <div className="mb-6 flex min-w-0 flex-col gap-2 border-b border-[#EFE8E3] pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9A7467]">
              Active Project
            </p>
            <p className="mt-1 break-words text-sm font-semibold text-[#392823]">
              {loading
                ? "正在读取 Project…"
                : (selectedProject?.name ?? "尚未选择")}
            </p>
          </div>
          <p className="text-sm text-[#716562]">
            {draft.mode === "periodic_monitoring" ? "周期监测" : "批量研究"}
            {planContext
              ? ` · ${planContext.name} · 当前基线 v${planContext.currentVersionNumber}`
              : " · 新 Plan"}
          </p>
        </div>

        {planContext?.projectStatus === "archived" ? (
          <p className="mb-5 rounded-xl border border-[#DDD2CB] bg-[#FBF8F5] px-4 py-3 text-sm font-semibold text-[#6D514A]">
            Archived Project 仅允许读取历史草稿；Preview 与 Save 已禁用。
          </p>
        ) : null}

        {currentStep === "mode" ? (
          <PlannerModeStep
            draft={draft}
            fieldErrors={fieldErrors}
            modeLocked={Boolean(initialPlanId || planContext)}
            onDraftChange={updateDraft}
          />
        ) : null}
        {currentStep === "scopes" ? (
          <PlannerScopeStep
            draft={draft}
            fieldErrors={fieldErrors}
            onDraftChange={updateDraft}
          />
        ) : null}
        {currentStep === "constraints" ? (
          <PlannerConstraintsStep
            draft={draft}
            fieldErrors={fieldErrors}
            onDraftChange={updateDraft}
          />
        ) : null}
        {currentStep === "preview" ? renderPreviewStep() : null}

        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-[#EFE8E3] pt-5">
          <button
            className="rounded-xl border border-[#DCCFC8] bg-white px-4 py-2 text-sm font-semibold text-[#6D514A] disabled:cursor-not-allowed disabled:opacity-40"
            disabled={stepIndex === 0 || planLoadState.status !== "ready"}
            onClick={goBack}
            type="button"
          >
            上一步
          </button>
          {currentStep !== "preview" ? (
            <button
              className="rounded-xl bg-[#9F4E3D] px-4 py-2 text-sm font-semibold text-white"
              disabled={planLoadState.status !== "ready"}
              onClick={goNext}
              type="button"
            >
              下一步
            </button>
          ) : null}
        </div>
      </section>
    </div>
  );
}
