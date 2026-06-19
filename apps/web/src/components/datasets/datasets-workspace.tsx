"use client";

import {
  AlertTriangle,
  ArrowRight,
  BellRing,
  CheckCircle2,
  Clock3,
  Mail,
  Database,
  Download,
  FileDown,
  FileCode2,
  Layers3,
  Loader2,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  TableProperties,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import {
  createAutomationProductDatasetExport,
  createAutomationProductDriftAlertEvents,
  createAutomationProductDriftAlertRule,
  datasetExportDownloadHref,
  listAutomationProductDatasetExports,
  listAutomationProductDatasetVersions,
  listAutomationProductDatasets,
  listAutomationProductDriftEvents,
  previewAutomationProductDriftAlertRule,
  sendAutomationProductDriftAlertEmails,
  sendAutomationProductDriftAlertNotifications,
} from "@/lib/api/automation";
import { cn } from "@/lib/utils";
import type {
  AutomationDatasetExportFormat,
  AutomationDatasetVersion,
  AutomationProductDatasetExportJob,
  AutomationProductDatasetListItem,
  AutomationProductDriftAlertPreview,
  AutomationProductDriftAlertEventCreate,
  AutomationProductDriftAlertNotificationSend,
  AutomationProductDriftAlertEmailSend,
  AutomationProductDriftAlertRuleCreate,
  AutomationProductDriftEvent,
} from "@/types/automation";

export function DatasetsWorkspace() {
  const [datasets, setDatasets] = useState<AutomationProductDatasetListItem[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [versions, setVersions] = useState<AutomationDatasetVersion[]>([]);
  const [driftEvents, setDriftEvents] = useState<AutomationProductDriftEvent[]>([]);
  const [exportFormat, setExportFormat] = useState<AutomationDatasetExportFormat>("csv");
  const [exportJobs, setExportJobs] = useState<AutomationProductDatasetExportJob[]>([]);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alertMinStatus, setAlertMinStatus] = useState<"critical" | "warning">("critical");
  const [alertChannel, setAlertChannel] = useState<"in_app" | "email" | "both">("in_app");
  const [alertPreview, setAlertPreview] =
    useState<AutomationProductDriftAlertPreview | null>(null);
  const [alertRuleCreate, setAlertRuleCreate] =
    useState<AutomationProductDriftAlertRuleCreate | null>(null);
  const [alertEventCreate, setAlertEventCreate] =
    useState<AutomationProductDriftAlertEventCreate | null>(null);
  const [alertNotificationSend, setAlertNotificationSend] =
    useState<AutomationProductDriftAlertNotificationSend | null>(null);
  const [alertEmailSend, setAlertEmailSend] =
    useState<AutomationProductDriftAlertEmailSend | null>(null);
  const [alertLoading, setAlertLoading] = useState(false);
  const [alertError, setAlertError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    listAutomationProductDatasets({ limit: 50 })
      .then((result) => {
        if (!mounted) {
          return;
        }
        setDatasets(result.items);
        setSelectedDatasetId(result.items[0]?.dataset.id ?? null);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load datasets");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedDatasetId) {
      setVersions([]);
      setDriftEvents([]);
      setExportJobs([]);
      return;
    }
    let mounted = true;
    setDetailLoading(true);
    Promise.all([
      listAutomationProductDatasetVersions({ datasetId: selectedDatasetId, limit: 50 }),
      listAutomationProductDriftEvents({ datasetId: selectedDatasetId, limit: 20 }),
      listAutomationProductDatasetExports({ datasetId: selectedDatasetId, limit: 20 }),
    ])
      .then(([versionResult, driftResult, exportResult]) => {
        if (!mounted) {
          return;
        }
        setVersions(versionResult.versions);
        setDriftEvents(driftResult.items);
        setExportJobs(exportResult.items);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load dataset detail");
        }
      })
      .finally(() => {
        if (mounted) {
          setDetailLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [selectedDatasetId]);

  const selectedDataset = useMemo(
    () => datasets.find((item) => item.dataset.id === selectedDatasetId) ?? datasets[0] ?? null,
    [datasets, selectedDatasetId],
  );
  const activeVersion = versions[0] ?? selectedDataset?.latestVersion ?? null;
  const totalVersions = datasets.reduce((total, item) => total + item.versionCount, 0);
  const totalDriftEvents = datasets.reduce((total, item) => total + item.driftEventCount, 0);
  const criticalDriftEvents = driftEvents.filter((event) => event.status === "critical").length;
  const activeDriftEvent =
    driftEvents.find((event) => event.version.id === activeVersion?.id) ?? driftEvents[0] ?? null;

  useEffect(() => {
    setAlertPreview(null);
    setAlertRuleCreate(null);
    setAlertEventCreate(null);
    setAlertNotificationSend(null);
    setAlertEmailSend(null);
    setAlertError(null);
  }, [selectedDatasetId, activeVersion?.id]);

  useEffect(() => {
    setExportError(null);
    setExportMessage(null);
  }, [selectedDatasetId, activeVersion?.id]);

  async function createDatasetExport() {
    if (!selectedDataset || !activeVersion) {
      setExportError("请选择一个已保存版本的数据集。");
      return;
    }
    setExportLoading(true);
    setExportError(null);
    setExportMessage(null);
    try {
      const result = await createAutomationProductDatasetExport({
        authorized: true,
        confirmCreate: true,
        datasetId: selectedDataset.dataset.id,
        datasetVersionId: activeVersion.id,
        exportFormat,
      });
      setExportJobs((current) => [
        result,
        ...current.filter((item) => item.id !== result.id),
      ]);
      setExportMessage(`已生成导出文件：${result.filename}`);
    } catch (caught) {
      setExportError(caught instanceof Error ? caught.message : "Dataset export failed");
    } finally {
      setExportLoading(false);
    }
  }

  async function previewAlertPolicy() {
    if (!selectedDataset) {
      setAlertError("请选择一个数据集。");
      return;
    }
    setAlertLoading(true);
    setAlertError(null);
    setAlertRuleCreate(null);
    try {
      const result = await previewAutomationProductDriftAlertRule({
        authorized: true,
        datasetId: selectedDataset.dataset.id,
        datasetVersionId: activeVersion?.id ?? null,
        minStatus: alertMinStatus,
        channel: alertChannel,
        enabled: true,
        limit: 20,
      });
      setAlertPreview(result);
    } catch (caught) {
      setAlertError(caught instanceof Error ? caught.message : "Alert policy preview failed");
    } finally {
      setAlertLoading(false);
    }
  }

  async function createAlertPolicy() {
    if (!selectedDataset) {
      setAlertError("请选择一个数据集。");
      return;
    }
    setAlertLoading(true);
    setAlertError(null);
    try {
      const result = await createAutomationProductDriftAlertRule({
        authorized: true,
        confirmCreate: true,
        datasetId: selectedDataset.dataset.id,
        datasetVersionId: activeVersion?.id ?? null,
        minStatus: alertMinStatus,
        channel: alertChannel,
        enabled: true,
        name: alertPreview?.ruleDraft.name ?? null,
        limit: 20,
      });
      setAlertPreview(result);
      setAlertRuleCreate(result);
      setAlertEventCreate(null);
      setAlertNotificationSend(null);
      setAlertEmailSend(null);
    } catch (caught) {
      setAlertError(caught instanceof Error ? caught.message : "Alert policy create failed");
    } finally {
      setAlertLoading(false);
    }
  }

  async function createAlertEvents() {
    if (!selectedDataset || !activeVersion || !activeDriftEvent) {
      setAlertError("当前数据集缺少可桥接的 DriftEvent。");
      return;
    }
    setAlertLoading(true);
    setAlertError(null);
    try {
      const result = await createAutomationProductDriftAlertEvents({
        authorized: true,
        confirmCreate: true,
        datasetId: selectedDataset.dataset.id,
        datasetVersionId: activeVersion.id,
        driftEventId: activeDriftEvent.id,
      });
      setAlertEventCreate(result);
      setAlertNotificationSend(null);
      setAlertEmailSend(null);
    } catch (caught) {
      setAlertError(caught instanceof Error ? caught.message : "Alert event bridge failed");
    } finally {
      setAlertLoading(false);
    }
  }

  async function sendAlertNotifications() {
    if (!selectedDataset || !activeVersion || !activeDriftEvent || !alertEventCreate) {
      setAlertError("请先生成可发送通知的 AlertEvent。");
      return;
    }
    const alertEventIds = alertEventCreate.alertEvents.map((event) => event.id);
    if (alertEventIds.length === 0) {
      setAlertError("当前没有新生成的 AlertEvent 可发送通知。");
      return;
    }
    setAlertLoading(true);
    setAlertError(null);
    try {
      const result = await sendAutomationProductDriftAlertNotifications({
        authorized: true,
        confirmSend: true,
        datasetId: selectedDataset.dataset.id,
        datasetVersionId: activeVersion.id,
        driftEventId: activeDriftEvent.id,
        alertEventIds,
      });
      setAlertNotificationSend(result);
    } catch (caught) {
      setAlertError(caught instanceof Error ? caught.message : "Alert notification send failed");
      setAlertEmailSend(null);
    } finally {
      setAlertLoading(false);
    }
  }

  async function sendAlertEmails() {
    if (!selectedDataset || !activeVersion || !activeDriftEvent || !alertEventCreate) {
      setAlertError("请先生成可发送通知的 AlertEvent。");
      return;
    }
    if (alertChannel === "in_app") {
      setAlertError("当前渠道为站内通知，切换到“邮件”或“站内 + 邮件”后再发送邮件。");
      return;
    }
    const alertEventIds = alertEventCreate.alertEvents.map((event) => event.id);
    if (alertEventIds.length === 0) {
      setAlertError("当前没有可发送邮件的 AlertEvent。");
      return;
    }
    setAlertLoading(true);
    setAlertError(null);
    try {
      const result = await sendAutomationProductDriftAlertEmails({
        authorized: true,
        confirmSend: true,
        datasetId: selectedDataset.dataset.id,
        datasetVersionId: activeVersion.id,
        driftEventId: activeDriftEvent.id,
        alertEventIds,
      });
      setAlertEmailSend(result);
    } catch (caught) {
      setAlertError(caught instanceof Error ? caught.message : "Alert email send failed");
      setAlertEmailSend(null);
    } finally {
      setAlertLoading(false);
    }
  }

  if (loading) {
    return (
      <section className="rounded-2xl border border-[#E8D4CB] bg-white p-6 text-sm text-[#7A625A]">
        <div className="flex items-center gap-2">
          <Loader2 className="animate-spin text-[#C96F5C]" size={16} aria-hidden="true" />
          正在加载数据集资产...
        </div>
      </section>
    );
  }

  return (
    <div className="grid min-w-0 gap-5">
      {error ? (
        <section className="rounded-2xl border border-[#F0C8C0] bg-[#FFF2EF] p-4 text-sm font-medium text-[#B85F4F]">
          {error}
        </section>
      ) : null}

      <section className="rounded-2xl border border-[#EDDCD3] bg-[#FFF8F4] p-5 shadow-[0_18px_60px_rgba(115,70,58,0.08)]">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <Database size={14} aria-hidden="true" />
              Dataset Assets
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C] sm:text-3xl">
              数据集资产池
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[#7A625A]">
              这里管理已经从采集运行沉淀下来的结构化数据集。你可以回看每个版本的字段、清洗规则、行数、完整率和漂移事件，判断它是否适合进入培训、调度或后续导出。
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            <Metric icon={Layers3} label="数据集" value={String(datasets.length)} />
            <Metric icon={TableProperties} label="版本" value={String(totalVersions)} />
            <Metric icon={AlertTriangle} label="漂移事件" value={String(totalDriftEvents)} />
          </div>
        </div>
      </section>

      {datasets.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-[#E8D4CB] bg-white p-6">
          <h2 className="text-lg font-semibold text-[#2E201C]">暂无已保存的数据集</h2>
          <p className="mt-2 text-sm leading-6 text-[#7A625A]">
            先到自动采集工作台完成商品发现、小批量采集、数据集预览和数据集版本保存，保存后会在这里形成可回看的资产。
          </p>
          <Link
            className="mt-4 inline-flex h-10 items-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white hover:bg-[#B85F4F]"
            href="/automation"
          >
            去自动采集
            <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </section>
      ) : (
        <section className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="grid min-w-0 gap-3">
            {datasets.map((item) => (
              <button
                className={cn(
                  "min-w-0 rounded-2xl border bg-white p-4 text-left transition",
                  selectedDataset?.dataset.id === item.dataset.id
                    ? "border-[#C96F5C] shadow-[0_12px_28px_rgba(201,111,92,0.16)]"
                    : "border-[#F0E1D9] hover:border-[#D7B9AB]",
                )}
                key={item.dataset.id}
                onClick={() => setSelectedDatasetId(item.dataset.id)}
                type="button"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-words text-sm font-semibold text-[#2E201C]">
                      {item.dataset.name}
                    </p>
                    <p className="mt-1 text-xs font-semibold uppercase text-[#B47767]">
                      {formatDatasetType(item.dataset.datasetType)}
                    </p>
                  </div>
                  <StatusBadge status={item.latestDriftEvent?.status ?? item.dataset.status} />
                </div>
                <p className="mt-3 line-clamp-2 text-sm leading-5 text-[#7A625A]">
                  {item.dataset.description ?? "暂无数据集说明"}
                </p>
                <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                  <MiniStat label="版本" value={String(item.versionCount)} />
                  <MiniStat
                    label="行数"
                    value={item.latestVersion ? String(item.latestVersion.rowCount) : "0"}
                  />
                  <MiniStat label="漂移" value={String(item.driftEventCount)} />
                </div>
              </button>
            ))}
          </div>

          <div className="grid min-w-0 gap-5">
            <Panel icon={ShieldCheck} title="选中数据集概览">
              {selectedDataset ? (
                <div className="grid gap-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <h3 className="break-words text-xl font-semibold text-[#2E201C]">
                        {selectedDataset.dataset.name}
                      </h3>
                      <p className="mt-2 text-sm leading-6 text-[#7A625A]">
                        {selectedDataset.dataset.description ?? "暂无数据集说明"}
                      </p>
                    </div>
                    <StatusBadge status={selectedDataset.latestDriftEvent?.status ?? selectedDataset.dataset.status} />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-4">
                    <Fact label="当前版本" value={selectedDataset.latestVersion ? `v${selectedDataset.latestVersion.versionNumber}` : "未保存"} />
                    <Fact label="完整率" value={selectedDataset.latestVersion ? `${selectedDataset.latestVersion.averageCompletenessPercent}%` : "-"} />
                    <Fact label="行数" value={selectedDataset.latestVersion ? String(selectedDataset.latestVersion.rowCount) : "0"} />
                    <Fact label="关键漂移" value={String(criticalDriftEvents)} />
                  </div>
                  {detailLoading ? (
                    <div className="flex items-center gap-2 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2 text-sm text-[#7A625A]">
                      <Loader2 className="animate-spin text-[#C96F5C]" size={15} aria-hidden="true" />
                      正在刷新版本和漂移历史...
                    </div>
                  ) : null}
                </div>
              ) : null}
            </Panel>

            <div className="grid gap-5 2xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
              <Panel icon={Clock3} title="版本历史">
                {versions.length > 0 ? (
                  <div className="grid gap-3">
                    {versions.map((version) => (
                      <VersionCard key={version.id} version={version} />
                    ))}
                  </div>
                ) : (
                  <EmptyDetail text="当前数据集还没有保存版本。先在自动采集工作台完成数据集预览并保存数据集版本。" />
                )}
              </Panel>

              <Panel icon={FileCode2} title="版本字段与清洗规则">
                {activeVersion ? (
                  <div className="grid gap-4">
                    <div>
                      <p className="text-sm font-semibold text-[#2E201C]">
                        v{activeVersion.versionNumber} 字段
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {activeVersion.selectedFields.map((field) => (
                          <span
                            className="rounded-full border border-[#E8D4CB] bg-[#FFF8F4] px-2.5 py-1 text-xs font-semibold text-[#7D4F43]"
                            key={field}
                          >
                            {field}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[#2E201C]">清洗脚本</p>
                      <div className="mt-2 grid gap-2">
                        {activeVersion.cleaningScript.map((step) => (
                          <div
                            className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3 text-sm leading-5 text-[#7A625A]"
                            key={step}
                          >
                            {step}
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
                      <p className="text-sm font-semibold text-[#2E201C]">导出预览</p>
                      <p className="mt-2 text-sm leading-6 text-[#7A625A]">
                        主键：{exportPrimaryKey(activeVersion)}；预览行：{exportPreviewRows(activeVersion)}。
                        可在下方生成 CSV、JSON 或 JSONL 导出文件，下载接口会再次校验当前账号的数据集权限。
                      </p>
                    </div>
                    <DatasetRowsPreview version={activeVersion} />
                  </div>
                ) : (
                  <EmptyDetail text="暂无可展示的字段和清洗规则。" />
                )}
              </Panel>
            </div>

            <Panel icon={FileDown} title="数据集导出">
              {activeVersion ? (
                <div className="grid gap-4">
                  <p className="text-sm leading-6 text-[#7A625A]">
                    将当前数据集版本写出为受控导出文件。导出不会启动采集任务，也不会修改数据集版本；历史文件可直接下载用于培训、复盘或下游导入。
                  </p>
                  <div className="grid gap-3 md:grid-cols-[minmax(0,180px)_auto_1fr] md:items-end">
                    <label className="grid gap-1 text-sm font-semibold text-[#2E201C]">
                      导出格式
                      <select
                        className="h-10 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-medium text-[#2E201C] outline-none focus:border-[#C96F5C]"
                        onChange={(event) =>
                          setExportFormat(event.target.value as AutomationDatasetExportFormat)
                        }
                        value={exportFormat}
                      >
                        <option value="csv">CSV 表格</option>
                        <option value="json">JSON 数组</option>
                        <option value="jsonl">JSONL 行式</option>
                      </select>
                    </label>
                    <button
                      className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={exportLoading || !selectedDataset || !activeVersion}
                      onClick={createDatasetExport}
                      type="button"
                    >
                      {exportLoading ? (
                        <Loader2 className="animate-spin" size={15} aria-hidden="true" />
                      ) : (
                        <FileDown size={15} aria-hidden="true" />
                      )}
                      生成导出文件
                    </button>
                    <div className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2 text-xs leading-5 text-[#7A625A]">
                      当前版本 v{activeVersion.versionNumber}，字段{" "}
                      {activeVersion.selectedFields.join(", ")}。
                    </div>
                  </div>

                  {exportError ? (
                    <p className="rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] p-3 text-sm font-semibold text-[#B85F4F]">
                      {exportError}
                    </p>
                  ) : null}
                  {exportMessage ? (
                    <p className="rounded-xl border border-[#BFE6C9] bg-[#EAF7EE] p-3 text-sm font-semibold text-[#287A45]">
                      {exportMessage}
                    </p>
                  ) : null}

                  {exportJobs.length > 0 ? (
                    <div className="grid gap-3">
                      {exportJobs.map((job) => (
                        <article
                          className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3"
                          key={job.id}
                        >
                          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <StatusBadge status={job.status} />
                                <span className="rounded-full border border-[#E8D4CB] bg-white px-2.5 py-1 text-xs font-semibold text-[#7D4F43]">
                                  {formatExportFormat(job.exportFormat)}
                                </span>
                              </div>
                              <p className="mt-2 break-words text-sm font-semibold text-[#2E201C]">
                                {job.filename}
                              </p>
                              <p className="mt-1 text-xs leading-5 text-[#7A625A]">
                                v{job.version.versionNumber} · {job.rowCount} 行 ·{" "}
                                {formatBytes(job.artifactSizeBytes)} · {formatDate(job.createdAt)}
                              </p>
                              <p className="mt-1 break-all text-xs leading-5 text-[#A06D61]">
                                SHA256：{job.checksumSha256}
                              </p>
                            </div>
                            {job.downloadUrl ? (
                              <a
                                className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-4 text-sm font-semibold text-[#7D4F43] hover:border-[#C96F5C]"
                                href={datasetExportDownloadHref(job.downloadUrl)}
                                rel="noreferrer"
                                target="_blank"
                              >
                                <Download size={15} aria-hidden="true" />
                                下载
                              </a>
                            ) : (
                              <span className="text-sm font-semibold text-[#B85F4F]">
                                {job.errorMessage ?? "暂不可下载"}
                              </span>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <EmptyDetail text="当前数据集还没有导出文件。选择格式后生成导出文件，即可在这里下载。" />
                  )}
                </div>
              ) : (
                <EmptyDetail text="暂无可导出的数据集版本。" />
              )}
            </Panel>

            <Panel icon={RefreshCw} title="漂移历史">
              {driftEvents.length > 0 ? (
                <div className="grid gap-3">
                  {driftEvents.map((event) => (
                    <DriftEventCard event={event} key={event.id} />
                  ))}
                </div>
              ) : (
                <EmptyDetail text="尚未保存漂移快照。完成调度审批和漂移检查后，可在自动采集工作台保存快照。" />
              )}
            </Panel>

            <Panel icon={ShieldAlert} title="漂移告警策略">
              <div className="grid gap-4">
                <p className="text-sm leading-6 text-[#7A625A]">
                  基于已保存的 DriftEvent 预览未来告警规则。预览不会创建规则；确认后只创建
                  AlertRule，不回放历史事件、不创建 AlertEvent，也不发送通知。
                </p>

                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto_auto] md:items-end">
                  <label className="grid gap-1 text-sm font-semibold text-[#2E201C]">
                    触发阈值
                    <select
                      className="h-10 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-medium text-[#2E201C] outline-none focus:border-[#C96F5C]"
                      onChange={(event) =>
                        setAlertMinStatus(event.target.value as "critical" | "warning")
                      }
                      value={alertMinStatus}
                    >
                      <option value="critical">只看 critical</option>
                      <option value="warning">warning + critical</option>
                    </select>
                  </label>
                  <label className="grid gap-1 text-sm font-semibold text-[#2E201C]">
                    通知通道
                    <select
                      className="h-10 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-medium text-[#2E201C] outline-none focus:border-[#C96F5C]"
                      onChange={(event) =>
                        setAlertChannel(event.target.value as "in_app" | "email" | "both")
                      }
                      value={alertChannel}
                    >
                      <option value="in_app">站内通知</option>
                      <option value="email">邮件</option>
                      <option value="both">站内 + 邮件</option>
                    </select>
                  </label>
                  <button
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-4 text-sm font-semibold text-[#7D4F43] hover:border-[#C96F5C] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={alertLoading || !selectedDataset}
                    onClick={previewAlertPolicy}
                    type="button"
                  >
                    {alertLoading ? (
                      <Loader2 className="animate-spin" size={15} aria-hidden="true" />
                    ) : null}
                    预览告警策略
                  </button>
                  <button
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={alertLoading || !alertPreview}
                    onClick={createAlertPolicy}
                    type="button"
                  >
                    确认创建策略
                  </button>
                  <button
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#2E201C] px-4 text-sm font-semibold text-white hover:bg-[#4C332B] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={alertLoading || !alertRuleCreate || !activeDriftEvent}
                    onClick={createAlertEvents}
                    type="button"
                  >
                    生成告警事件
                  </button>
                  <button
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#287A45] px-4 text-sm font-semibold text-white hover:bg-[#22683B] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={alertLoading || !alertEventCreate?.alertEvents.length}
                    onClick={sendAlertNotifications}
                    type="button"
                  >
                    <BellRing size={15} aria-hidden="true" />
                    发送站内通知
                  </button>
                  <button
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#7A5A3E] px-4 text-sm font-semibold text-white hover:bg-[#674A35] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={alertLoading || !alertEventCreate?.alertEvents.length}
                    onClick={sendAlertEmails}
                    type="button"
                  >
                    <Mail size={15} aria-hidden="true" />
                    发送邮件告警
                  </button>
                </div>

                {alertError ? (
                  <p className="rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] p-3 text-sm font-semibold text-[#B85F4F]">
                    {alertError}
                  </p>
                ) : null}

                {alertPreview ? (
                  <div className="grid gap-3 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[#2E201C]">
                          {alertPreview.ruleDraft.name}
                        </p>
                        <p className="mt-1 text-sm leading-6 text-[#7A625A]">
                          策略条件：dataset_drift / severity in{" "}
                          {formatAlertConditionValue(alertPreview.ruleDraft.condition)} /{" "}
                          {formatAlertChannel(alertPreview.ruleDraft.channel)}
                        </p>
                      </div>
                      <StatusBadge status={alertPreview.summary.alertRuleCreated ? "saved" : "preview"} />
                    </div>

                    <div className="grid gap-2 sm:grid-cols-3">
                      <MiniStat
                        label="匹配 DriftEvent"
                        value={String(alertPreview.summary.matchedEvents)}
                      />
                      <MiniStat
                        label="critical"
                        value={String(alertPreview.summary.criticalEvents)}
                      />
                      <MiniStat
                        label="warning"
                        value={String(alertPreview.summary.warningEvents)}
                      />
                    </div>

                    <div className="grid gap-2 text-sm leading-6 text-[#7A625A]">
                      <p>预览不会创建 AlertRule、AlertEvent 或通知。</p>
                      {alertRuleCreate ? (
                        <p className="font-semibold text-[#287A45]">
                          已创建 DriftEvent 告警策略：{shortId(alertRuleCreate.alertRule.id)}。
                          未创建 AlertEvent，未发送通知。
                        </p>
                      ) : null}
                      {alertEventCreate ? (
                        <p className="font-semibold text-[#287A45]">
                          已生成 dataset_drift Signal：{shortId(alertEventCreate.signal.id)}。
                          已创建 AlertEvent {alertEventCreate.alertEvents.length} 条，未发送通知。
                        </p>
                      ) : null}
                      {alertNotificationSend ? (
                        <p className="font-semibold text-[#287A45]">
                          已发送站内通知 {alertNotificationSend.notifications.length} 条，
                          AlertEvent 已标记为 sent；未发送邮件。
                        </p>
                      ) : null}
                      {alertEmailSend ? (
                        <div className="rounded-xl border border-[#E8D4CB] bg-[#FFF8F4] p-3 text-[#2E201C]">
                          <p className="font-semibold text-[#7D4F43]">
                            已发送邮件告警 {alertEmailSend.emailDeliveries.filter((item) => item.delivered).length} 条，
                            未送达 {alertEmailSend.emailDeliveries.filter((item) => !item.delivered).length} 条。
                          </p>
                          <div className="mt-2 grid gap-2 text-xs text-[#7A625A]">
                            {alertEmailSend.emailDeliveries.map((delivery) => (
                              <p key={delivery.alertEventId}>
                                {delivery.recipientEmail}：{delivery.delivered ? "送达" : "未送达"}
                                {delivery.reason ? `（${delivery.reason}）` : ""}
                              </p>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {alertNotificationSend?.blockedReasons.length ? (
                        <p>通知边界：{alertNotificationSend.blockedReasons.join("；")}</p>
                      ) : null}
                      {alertEmailSend?.blockedReasons.length ? (
                        <p>邮件边界：{alertEmailSend.blockedReasons.join("；")}</p>
                      ) : null}
                      {!alertRuleCreate && alertPreview.blockedReasons.length > 0 ? (
                        <p>
                          边界说明：{alertPreview.blockedReasons.join("；")}
                        </p>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
            </Panel>
          </div>
        </section>
      )}
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
        <Icon size={15} aria-hidden="true" />
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

function Panel({
  children,
  icon: Icon,
  title,
}: {
  children: ReactNode;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <section className="min-w-0 rounded-2xl border border-[#F0E1D9] bg-white p-4">
      <div className="mb-4 flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#FFF1EC] text-[#C96F5C]">
          <Icon size={17} aria-hidden="true" />
        </span>
        <h2 className="text-base font-semibold text-[#2E201C]">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-2 py-2">
      <p className="text-xs font-semibold text-[#B47767]">{label}</p>
      <p className="mt-1 text-sm font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
      <p className="text-xs font-semibold uppercase text-[#B47767]">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

function VersionCard({ version }: { version: AutomationDatasetVersion }) {
  return (
    <article className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[#2E201C]">Version {version.versionNumber}</h3>
          <p className="mt-1 text-xs text-[#7A625A]">{formatDate(version.createdAt)}</p>
        </div>
        <span className="rounded-full bg-[#EAF7EE] px-2.5 py-1 text-xs font-semibold text-[#287A45]">
          {version.status}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <MiniStat label="行数" value={String(version.rowCount)} />
        <MiniStat label="完整率" value={`${version.averageCompletenessPercent}%`} />
        <MiniStat label="运行数" value={String(version.sourceTaskRunIds.length)} />
      </div>
    </article>
  );
}

function DatasetRowsPreview({ version }: { version: AutomationDatasetVersion }) {
  const rows = exportPreviewRowObjects(version).slice(0, 3);
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[#E8D4CB] bg-[#FFFDFC] p-3">
        <p className="text-sm font-semibold text-[#2E201C]">数据行预览</p>
        <p className="mt-2 text-sm leading-6 text-[#7A625A]">
          当前版本没有可直接展示的行级预览。
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm font-semibold text-[#2E201C]">数据行预览</p>
        <p className="text-xs font-semibold text-[#B47767]">
          显示前 {rows.length} 行 · {version.selectedFields.length} 个字段
        </p>
      </div>
      <div className="mt-3 grid gap-3">
        {rows.map((row, index) => (
          <article
            className="rounded-xl border border-[#F0E1D9] bg-white p-3"
            key={`${version.id}-row-${index}`}
          >
            <p className="text-xs font-semibold uppercase text-[#B47767]">Row {index + 1}</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {version.selectedFields.map((field) => (
                <div className="min-w-0 rounded-lg bg-[#FFF8F4] px-3 py-2" key={field}>
                  <p className="text-[11px] font-semibold uppercase text-[#B47767]">
                    {field}
                  </p>
                  <p className="mt-1 break-words text-sm font-semibold text-[#2E201C]">
                    {formatPreviewValue(row[field])}
                  </p>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function DriftEventCard({ event }: { event: AutomationProductDriftEvent }) {
  return (
    <article className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={event.status} />
            <span className="text-xs font-semibold uppercase text-[#B47767]">
              {event.eventType}
            </span>
          </div>
          <p className="mt-2 text-sm font-semibold text-[#2E201C]">
            v{event.version.versionNumber} · {formatDate(event.createdAt)}
          </p>
          {event.note ? (
            <p className="mt-2 text-sm leading-6 text-[#7A625A]">{event.note}</p>
          ) : null}
        </div>
        <div className="grid grid-cols-3 gap-2 sm:w-72">
          <MiniStat label="检查" value={String(event.summary.checkedTasks)} />
          <MiniStat label="关键" value={String(event.summary.criticalTasks)} />
          <MiniStat label="缺字段" value={String(event.summary.missingFieldTasks)} />
        </div>
      </div>
      <div className="mt-3 grid gap-2">
        {event.items.map((item) => (
          <div
            className="rounded-lg border border-[#F0E1D9] bg-white px-3 py-2 text-sm text-[#7A625A]"
            key={`${event.id}-${item.taskId}`}
          >
            <span className="font-semibold text-[#2E201C]">{item.taskName ?? item.taskId}</span>
            <span className="mx-2 text-[#B47767]">·</span>
            <span>{item.status}</span>
            {item.newMissingFields.length > 0 ? (
              <span> · 缺字段：{item.newMissingFields.join(", ")}</span>
            ) : null}
          </div>
        ))}
      </div>
    </article>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const tone =
    normalized === "critical"
      ? "border-[#F0C8C0] bg-[#FFF2EF] text-[#B85F4F]"
      : normalized === "warning"
        ? "border-[#F3D9A8] bg-[#FFF7E6] text-[#94631B]"
        : normalized === "ok" || normalized === "active" || normalized === "saved"
          ? "border-[#BFE6C9] bg-[#EAF7EE] text-[#287A45]"
          : "border-[#E8D4CB] bg-[#FFF8F4] text-[#7D4F43]";
  const Icon = normalized === "critical" || normalized === "warning" ? AlertTriangle : CheckCircle2;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold", tone)}>
      <Icon size={13} aria-hidden="true" />
      {status}
    </span>
  );
}

function EmptyDetail({ text }: { text: string }) {
  return (
    <p className="rounded-xl border border-dashed border-[#E8D4CB] bg-[#FFFDFC] p-4 text-sm leading-6 text-[#7A625A]">
      {text}
    </p>
  );
}

function exportPrimaryKey(version: AutomationDatasetVersion) {
  const schema = version.exportPreview.schema;
  if (schema && typeof schema === "object" && "primary_key" in schema) {
    const primaryKey = (schema as Record<string, unknown>).primary_key;
    return typeof primaryKey === "string" ? primaryKey : "未声明";
  }
  return "未声明";
}

function exportPreviewRows(version: AutomationDatasetVersion) {
  const rows = version.exportPreview.rows;
  return Array.isArray(rows) ? String(rows.length) : String(version.rowCount);
}

function exportPreviewRowObjects(version: AutomationDatasetVersion): Array<Record<string, unknown>> {
  const rows = version.exportPreview.rows;
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows.filter((row): row is Record<string, unknown> => {
    return typeof row === "object" && row !== null && !Array.isArray(row);
  });
}

function formatPreviewValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "缺失";
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatPreviewValue(item)).join(" / ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function formatDatasetType(value: string) {
  if (value === "ecommerce_product") {
    return "电商商品数据集";
  }
  return value;
}

function formatExportFormat(value: AutomationDatasetExportFormat) {
  if (value === "json") {
    return "JSON";
  }
  if (value === "jsonl") {
    return "JSONL";
  }
  return "CSV";
}

function formatBytes(value: number) {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatAlertChannel(value: string) {
  if (value === "in_app") {
    return "站内通知";
  }
  if (value === "email") {
    return "邮件";
  }
  if (value === "both") {
    return "站内 + 邮件";
  }
  return value;
}

function formatAlertConditionValue(condition: Record<string, unknown>) {
  const value = condition.value;
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return typeof value === "string" ? value : "-";
}

function shortId(value: string) {
  return value.slice(0, 8);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
