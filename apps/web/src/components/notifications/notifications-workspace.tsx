"use client";

import {
  Bell,
  BellRing,
  BookOpenCheck,
  CheckCheck,
  CheckSquare,
  ExternalLink,
  FileText,
  Filter,
  Inbox,
  MailOpen,
  Megaphone,
  RotateCcw,
  Save,
  Search,
  Settings2,
  ShieldAlert,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  getEmailChannelStatus,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  markNotificationsRead,
} from "@/lib/api/notifications";
import { isTrainingNotification } from "@/lib/training-data";
import { useTrainingOverview } from "@/lib/use-training-overview";
import { cn } from "@/lib/utils";
import type {
  EmailChannelStatus,
  NotificationItem,
  NotificationPreferenceState,
} from "@/types/notification";

type ReadFilter = "unread" | "all";
type TypeFilter = "all" | string;
type NotificationScope = "all" | "training";

const notificationPreferenceStorageKey =
  "data-achieve-notification-preferences-v1";
const preferenceTypes = ["alert", "report_ready", "task_failed", "alerts_ready", "evidence_ready"];
const defaultPreferences: NotificationPreferenceState = {
  delivery: {
    alert: { inApp: true, email: true },
    report_ready: { inApp: true, email: true },
    task_failed: { inApp: true, email: true },
    alerts_ready: { inApp: true, email: true },
    evidence_ready: { inApp: true, email: true },
  },
  quietHoursEnabled: true,
  digestTime: "09:00",
  updatedAt: null,
};

const notificationTone: Record<
  string,
  {
    label: string;
    icon: typeof Bell;
    accent: string;
    surface: string;
    text: string;
  }
> = {
  alert: {
    label: "预警",
    icon: ShieldAlert,
    accent: "bg-[#C96F5C]",
    surface: "border-[#E8D4CB] bg-[#FFF7F2]",
    text: "text-[#9E4F41]",
  },
  report_ready: {
    label: "报告",
    icon: FileText,
    accent: "bg-[#D5A642]",
    surface: "border-[#E7D8B8] bg-[#FFF9E9]",
    text: "text-[#8C6824]",
  },
  task_failed: {
    label: "任务",
    icon: Megaphone,
    accent: "bg-[#8D75A8]",
    surface: "border-[#DFD5E8] bg-[#FAF6FF]",
    text: "text-[#6B5685]",
  },
  alerts_ready: {
    label: "培训告警",
    icon: BookOpenCheck,
    accent: "bg-[#7D9A68]",
    surface: "border-[#D9E2CC] bg-[#F7FBF1]",
    text: "text-[#536B40]",
  },
  evidence_ready: {
    label: "培训证据",
    icon: BookOpenCheck,
    accent: "bg-[#B88A4B]",
    surface: "border-[#E4D8C8] bg-[#FFF9EF]",
    text: "text-[#7B5A31]",
  },
};

export function NotificationsWorkspace() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [filter, setFilter] = useState<ReadFilter>("unread");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [notificationScope, setNotificationScope] = useState<NotificationScope>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [bulkLoading, setBulkLoading] = useState(false);
  const [emailStatus, setEmailStatus] = useState<EmailChannelStatus | null>(
    null,
  );
  const [preferences, setPreferences] =
    useState<NotificationPreferenceState>(defaultPreferences);
  const [preferenceLoading, setPreferenceLoading] = useState(true);
  const [preferenceError, setPreferenceError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const trainingOverview = useTrainingOverview();

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setMessage(null);
    listNotifications(filter === "unread" ? false : undefined)
      .then((items) => {
        if (mounted) {
          setNotifications(items);
          setSelectedIds(
            (current) =>
              new Set(
                [...current].filter((id) =>
                  items.some((item) => item.id === id),
                ),
              ),
          );
          setSelectedId((current) =>
            current && items.some((item) => item.id === current)
              ? current
              : (items[0]?.id ?? null),
          );
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Failed to load notifications",
          );
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
  }, [filter]);

  useEffect(() => {
    setPreferenceLoading(true);
    try {
      const stored = window.localStorage.getItem(
        notificationPreferenceStorageKey,
      );
      if (stored) {
        setPreferences(mergeNotificationPreferences(JSON.parse(stored)));
      }
    } catch {
      setPreferenceError("通知偏好读取失败，已使用默认配置。");
    } finally {
      setPreferenceLoading(false);
    }

    getEmailChannelStatus()
      .then(setEmailStatus)
      .catch((caught) => {
        setPreferenceError(
          caught instanceof Error ? caught.message : "邮件通道状态读取失败",
        );
      });
  }, []);

  const notificationTypes = useMemo(() => {
    return Array.from(
      new Set(notifications.map((item) => item.notificationType)),
    );
  }, [notifications]);

  const filteredNotifications = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return notifications.filter((notification) => {
      const matchesScope =
        notificationScope === "all" || isTrainingNotification(notification);
      const matchesType =
        typeFilter === "all" || notification.notificationType === typeFilter;
      if (!matchesScope || !matchesType) {
        return false;
      }
      if (!term) {
        return true;
      }
      return [
        notification.title,
        notification.body,
        notification.notificationType,
        notification.referenceType,
        notification.referenceId,
      ]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [notificationScope, notifications, searchTerm, typeFilter]);

  const selectedNotification = useMemo(() => {
    return (
      filteredNotifications.find((item) => item.id === selectedId) ??
      filteredNotifications[0] ??
      null
    );
  }, [filteredNotifications, selectedId]);

  const selectedUnreadCount = useMemo(() => {
    return filteredNotifications.filter(
      (item) => selectedIds.has(item.id) && !item.isRead,
    ).length;
  }, [filteredNotifications, selectedIds]);

  const allVisibleSelected = useMemo(() => {
    return (
      filteredNotifications.length > 0 &&
      filteredNotifications.every((item) => selectedIds.has(item.id))
    );
  }, [filteredNotifications, selectedIds]);

  const stats = useMemo(() => {
    const unreadCount = notifications.filter((item) => !item.isRead).length;
    const alertCount = notifications.filter(
      (item) => item.notificationType === "alert",
    ).length;
    const taskCount = notifications.filter(
      (item) => item.notificationType === "task_failed",
    ).length;
    const trainingCount = notifications.filter((item) => isTrainingNotification(item)).length;
    return {
      total: notifications.length,
      unreadCount,
      alertCount,
      taskCount,
      trainingCount,
    };
  }, [notifications]);

  async function handleRead(notification: NotificationItem) {
    setError(null);
    setMessage(null);
    const updated = await markNotificationRead(notification.id);
    setNotifications((current) =>
      current
        .map((item) => (item.id === updated.id ? updated : item))
        .filter((item) => filter === "all" || !item.isRead),
    );
    setSelectedIds((current) => {
      const next = new Set(current);
      next.delete(notification.id);
      return next;
    });
    setSelectedId((current) => (current === notification.id ? null : current));
    setMessage(`${notification.title}: marked read`);
  }

  async function handleReadAll() {
    setError(null);
    setMessage(null);
    const count = await markAllNotificationsRead();
    setNotifications((current) =>
      filter === "all"
        ? current.map((item) => ({ ...item, isRead: true }))
        : [],
    );
    setSelectedIds(new Set());
    setSelectedId(null);
    setMessage(`${count} notifications marked read`);
  }

  function toggleNotificationSelection(notificationId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(notificationId)) {
        next.delete(notificationId);
      } else {
        next.add(notificationId);
      }
      return next;
    });
  }

  function toggleVisibleSelection() {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (allVisibleSelected) {
        for (const notification of filteredNotifications) {
          next.delete(notification.id);
        }
        return next;
      }
      for (const notification of filteredNotifications) {
        next.add(notification.id);
      }
      return next;
    });
  }

  async function handleReadSelected() {
    const notificationIds = Array.from(selectedIds);
    if (notificationIds.length === 0) {
      return;
    }
    setBulkLoading(true);
    setError(null);
    setMessage(null);
    try {
      const count = await markNotificationsRead(notificationIds);
      const selectedSet = new Set(notificationIds);
      setNotifications((current) =>
        filter === "all"
          ? current.map((item) =>
              selectedSet.has(item.id) ? { ...item, isRead: true } : item,
            )
          : current.filter((item) => !selectedSet.has(item.id)),
      );
      setSelectedIds(new Set());
      setSelectedId((current) =>
        current && selectedSet.has(current) ? null : current,
      );
      setMessage(`${count} selected notifications marked read`);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Failed to mark notifications read",
      );
    } finally {
      setBulkLoading(false);
    }
  }

  function updateDeliveryPreference(
    notificationType: string,
    channel: "inApp" | "email",
    value: boolean,
  ) {
    setPreferences((current) => ({
      ...current,
      delivery: {
        ...current.delivery,
        [notificationType]: {
          ...(current.delivery[notificationType] ?? {
            inApp: true,
            email: false,
          }),
          [channel]: value,
        },
      },
    }));
  }

  function savePreferences() {
    try {
      const next = { ...preferences, updatedAt: new Date().toISOString() };
      window.localStorage.setItem(
        notificationPreferenceStorageKey,
        JSON.stringify(next),
      );
      setPreferences(next);
      setPreferenceError(null);
      setMessage("通知偏好已保存");
    } catch (caught) {
      setPreferenceError(
        caught instanceof Error ? caught.message : "通知偏好保存失败",
      );
    }
  }

  function resetPreferences() {
    try {
      window.localStorage.removeItem(notificationPreferenceStorageKey);
      setPreferences(defaultPreferences);
      setPreferenceError(null);
      setMessage("通知偏好已重置");
    } catch (caught) {
      setPreferenceError(
        caught instanceof Error ? caught.message : "通知偏好重置失败",
      );
    }
  }

  function applyTrainingDeliveryTemplate() {
    setPreferences((current) => ({
      ...current,
      delivery: {
        ...current.delivery,
        report_ready: { inApp: true, email: true },
        alerts_ready: { inApp: true, email: true },
        evidence_ready: { inApp: true, email: true },
      },
      quietHoursEnabled: false,
      digestTime: "09:00",
    }));
    setMessage("已套用培训通知模板：报告、告警和证据链均开启站内与邮件交付。");
  }

  return (
    <div className="grid min-w-0 gap-5">
      <section className="overflow-hidden rounded-2xl border border-[#EDDCD3] bg-[#FFF8F4] shadow-[0_18px_60px_rgba(115,70,58,0.08)]">
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <Inbox size={14} aria-hidden="true" />
              Notification Delivery Layer
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C] sm:text-3xl">
              站内通知收件箱
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#7A625A]">
              汇总预警、日报和任务异常通知，保留关联对象入口，让团队能从消息直接回到证据链。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-5">
              <MetricPill
                icon={Bell}
                label="通知数"
                value={String(stats.total)}
              />
              <MetricPill
                icon={BellRing}
                label="未读"
                value={String(stats.unreadCount)}
              />
              <MetricPill
                icon={ShieldAlert}
                label="预警"
                value={String(stats.alertCount)}
              />
              <MetricPill
                icon={Megaphone}
                label="任务异常"
                value={String(stats.taskCount)}
              />
              <MetricPill
                icon={BookOpenCheck}
                label="培训通知"
                value={String(stats.trainingCount)}
              />
            </div>
          </div>

          <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">
                  Inbox State
                </p>
                <h3 className="mt-1 text-base font-semibold text-[#2E201C]">
                  当前视图
                </h3>
              </div>
              <span className="rounded-full bg-[#C96F5C] px-3 py-1 text-xs font-semibold text-white">
                {filter}
              </span>
            </div>
            <div className="mt-4 grid gap-2">
              <InboxRow
                label="展示通知"
                value={String(filteredNotifications.length)}
              />
              <InboxRow
                label="通知类型"
                value={String(notificationTypes.length)}
              />
              <InboxRow
                label="当前选中"
                value={selectedNotification?.referenceType ?? "—"}
              />
              <InboxRow
                label="培训证据"
                value={String(trainingOverview.overview?.metrics.evidenceCount ?? 0)}
              />
            </div>
          </div>
        </div>
      </section>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_430px]">
        <section className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">
                Inbox
              </p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">
                通知队列
              </h2>
              <p className="mt-1 text-sm text-[#7A625A]">
                筛选未读、类型和关键字，定位需要处理的交付消息。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {(["all", "training"] as const).map((scope) => (
                <button
                  className={cn(
                    "inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-sm font-semibold transition",
                    notificationScope === scope
                      ? "border-[#C96F5C] bg-[#C96F5C] text-white"
                      : "border-[#E8D4CB] bg-[#FFFDFC] text-[#7D4F43] hover:border-[#C96F5C]",
                  )}
                  key={scope}
                  onClick={() => setNotificationScope(scope)}
                  type="button"
                >
                  {scope === "training" ? <BookOpenCheck size={14} aria-hidden="true" /> : null}
                  {scope === "training" ? `培训通知 ${stats.trainingCount}` : "全部通知"}
                </button>
              ))}
              <button
                className={cn(
                  "h-10 rounded-xl px-3 text-sm font-semibold transition",
                  filter === "unread"
                    ? "bg-[#C96F5C] text-white"
                    : "border border-[#E8D4CB] bg-[#FFFDFC] text-[#7D4F43]",
                )}
                onClick={() => setFilter("unread")}
                type="button"
              >
                Unread
              </button>
              <button
                className={cn(
                  "h-10 rounded-xl px-3 text-sm font-semibold transition",
                  filter === "all"
                    ? "bg-[#C96F5C] text-white"
                    : "border border-[#E8D4CB] bg-[#FFFDFC] text-[#7D4F43]",
                )}
                onClick={() => setFilter("all")}
                type="button"
              >
                All
              </button>
              <button
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C]"
                onClick={() => void handleReadAll()}
                type="button"
              >
                <CheckCheck size={16} aria-hidden="true" />
                Read All
              </button>
              <button
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-[#F1D9A8] bg-[#FFF9E9] px-3 text-sm font-semibold text-[#8C6824] transition hover:border-[#C96F5C]"
                onClick={applyTrainingDeliveryTemplate}
                type="button"
              >
                <BookOpenCheck size={16} aria-hidden="true" />
                培训通知模板
              </button>
            </div>
          </div>

          <div className="mb-4 grid gap-2 sm:grid-cols-2">
            <label className="relative block">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                size={16}
                aria-hidden="true"
              />
              <input
                className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="搜索标题、正文、引用"
                value={searchTerm}
              />
            </label>
            <label className="relative block">
              <Filter
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                size={16}
                aria-hidden="true"
              />
              <select
                className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-8 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                onChange={(event) => setTypeFilter(event.target.value)}
                value={typeFilter}
              >
                <option value="all">全部类型</option>
                {notificationTypes.map((type) => (
                  <option key={type} value={type}>
                    {getNotificationTone(type).label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mb-4 flex flex-col gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFF8F4] p-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase text-[#B47767]">
                Bulk Actions
              </p>
              <p className="mt-1 text-sm text-[#5F4A43]">
                已选 {selectedIds.size} 条，其中 {selectedUnreadCount} 条未读
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-3 lg:flex lg:flex-wrap">
              <button
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C] disabled:cursor-not-allowed disabled:opacity-50"
                disabled={filteredNotifications.length === 0}
                onClick={toggleVisibleSelection}
                type="button"
              >
                {allVisibleSelected ? (
                  <CheckSquare size={16} aria-hidden="true" />
                ) : (
                  <Square size={16} aria-hidden="true" />
                )}
                {allVisibleSelected ? "取消当前" : "选择当前"}
              </button>
              <button
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.18)] transition hover:bg-[#B85F4F] disabled:cursor-not-allowed disabled:opacity-50"
                disabled={selectedUnreadCount === 0 || bulkLoading}
                onClick={() => void handleReadSelected()}
                type="button"
              >
                <CheckCheck size={16} aria-hidden="true" />
                批量标记已读
              </button>
              <button
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C] disabled:cursor-not-allowed disabled:opacity-50"
                disabled={selectedIds.size === 0}
                onClick={() => setSelectedIds(new Set())}
                type="button"
              >
                <X size={16} aria-hidden="true" />
                清空选择
              </button>
            </div>
          </div>

          {loading ? (
            <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
              加载通知中
            </div>
          ) : null}
          <StatusNotice error={error} message={message} />

          <div className="grid gap-3">
            {filteredNotifications.map((notification) => (
              <NotificationCard
                key={notification.id}
                notification={notification}
                onRead={() => void handleRead(notification)}
                onSelect={() => setSelectedId(notification.id)}
                onToggleSelected={() =>
                  toggleNotificationSelection(notification.id)
                }
                checked={selectedIds.has(notification.id)}
                selected={notification.id === selectedNotification?.id}
              />
            ))}
            {!loading && filteredNotifications.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
                暂无通知。
              </div>
            ) : null}
          </div>
        </section>

        <aside className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <NotificationPreferencesPanel
            emailStatus={emailStatus}
            error={preferenceError}
            loading={preferenceLoading}
            onDeliveryChange={updateDeliveryPreference}
            onDigestTimeChange={(value) =>
              setPreferences((current) => ({ ...current, digestTime: value }))
            }
            onQuietHoursChange={(value) =>
              setPreferences((current) => ({
                ...current,
                quietHoursEnabled: value,
              }))
            }
            onReset={resetPreferences}
            onSave={savePreferences}
            preferences={preferences}
          />
          <div className="my-5 h-px bg-[#F0E1D9]" />
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">
                Notification Detail
              </p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">
                通知详情
              </h2>
              <p className="mt-1 text-sm text-[#7A625A]">
                关联对象、阅读状态和交付正文。
              </p>
            </div>
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#C96F5C] text-white">
              <Sparkles size={18} aria-hidden="true" />
            </span>
          </div>
          {selectedNotification ? (
            <NotificationDetail notification={selectedNotification} />
          ) : (
            <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
              选择一条通知查看详情。
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function NotificationCard({
  notification,
  checked,
  selected,
  onSelect,
  onToggleSelected,
  onRead,
}: {
  notification: NotificationItem;
  checked: boolean;
  selected: boolean;
  onSelect: () => void;
  onToggleSelected: () => void;
  onRead: () => void;
}) {
  const tone = getNotificationTone(notification.notificationType);
  const Icon = notification.isRead ? MailOpen : tone.icon;
  const training = isTrainingNotification(notification);
  return (
    <article
      className={cn(
        "rounded-2xl border p-4 transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(72,45,38,0.1)]",
        notification.isRead ? "border-[#E8D4CB] bg-[#FFFDFC]" : tone.surface,
        selected ? "ring-2 ring-[#C96F5C] ring-offset-2 ring-offset-white" : "",
      )}
    >
      <div className="flex gap-3">
        <label className="mt-1 inline-flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-xl border border-[#E8D4CB] bg-white/85 text-[#7D4F43] transition hover:border-[#C96F5C]">
          <input
            aria-label={`选择通知 ${notification.title}`}
            checked={checked}
            className="sr-only"
            onChange={onToggleSelected}
            type="checkbox"
          />
          {checked ? (
            <CheckSquare size={17} aria-hidden="true" />
          ) : (
            <Square size={17} aria-hidden="true" />
          )}
        </label>
        <button
          className="min-w-0 flex-1 text-left"
          onClick={onSelect}
          type="button"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-3">
                <span
                  className={cn(
                    "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white",
                    notification.isRead ? "bg-[#B9A19A]" : tone.accent,
                  )}
                >
                  <Icon size={17} aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <h3 className="break-words text-base font-semibold text-[#2E201C]">
                    {notification.title}
                  </h3>
                  <p className="mt-1 text-xs text-[#7A625A]">
                    {tone.label} · {formatDate(notification.createdAt)}
                  </p>
                  {training ? (
                    <span className="mt-2 inline-flex rounded-full bg-[#FFF9E9] px-2.5 py-1 text-xs font-semibold text-[#8C6824]">
                      培训通知
                    </span>
                  ) : null}
                </div>
              </div>
              <p className="mt-3 text-sm leading-6 text-[#5F4A43]">
                {notification.body}
              </p>
            </div>
            <span
              className={cn(
                "w-fit rounded-full px-2.5 py-1 text-xs font-semibold",
                notification.isRead
                  ? "bg-[#F6ECE8] text-[#9E5C4D]"
                  : "bg-[#ECF7EA] text-[#4E7C45]",
              )}
            >
              {notification.isRead ? "read" : "unread"}
            </span>
          </div>
        </button>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          className="inline-flex h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-white/80 px-3 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C]"
          href={referenceHref(notification)}
        >
          <ExternalLink size={16} aria-hidden="true" />
          Open
        </Link>
        {!notification.isRead ? (
          <button
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.18)] transition hover:bg-[#B85F4F]"
            onClick={onRead}
            type="button"
          >
            <CheckCheck size={16} aria-hidden="true" />
            Read
          </button>
        ) : null}
      </div>
    </article>
  );
}

function NotificationPreferencesPanel({
  preferences,
  emailStatus,
  loading,
  error,
  onDeliveryChange,
  onQuietHoursChange,
  onDigestTimeChange,
  onSave,
  onReset,
}: {
  preferences: NotificationPreferenceState;
  emailStatus: EmailChannelStatus | null;
  loading: boolean;
  error: string | null;
  onDeliveryChange: (
    notificationType: string,
    channel: "inApp" | "email",
    value: boolean,
  ) => void;
  onQuietHoursChange: (value: boolean) => void;
  onDigestTimeChange: (value: string) => void;
  onSave: () => void;
  onReset: () => void;
}) {
  const emailState = loading
    ? "checking"
    : emailStatus?.configured
      ? "ready"
      : (emailStatus?.reason ?? "not_configured");

  return (
    <div>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-[#B47767]">
            Preferences
          </p>
          <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">
            通知偏好
          </h2>
          <p className="mt-1 text-sm text-[#7A625A]">
            当前工作台的收件、摘要和邮件通道状态。
          </p>
        </div>
        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#F6ECE8] text-[#9E5C4D]">
          <Settings2 size={18} aria-hidden="true" />
        </span>
      </div>

      <div className="grid gap-3">
        {preferenceTypes.map((type) => {
          const tone = getNotificationTone(type);
          const delivery =
            preferences.delivery[type] ?? defaultPreferences.delivery[type];
          return (
            <div
              className="border-t border-[#F0E1D9] pt-3 first:border-t-0 first:pt-0"
              key={type}
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-[#2E201C]">
                    {tone.label}
                  </p>
                  <p className="mt-1 text-xs text-[#7A625A]">{type}</p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <label className="inline-flex h-9 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm font-semibold text-[#7D4F43]">
                    <input
                      aria-label={`${tone.label} 站内通知`}
                      checked={delivery.inApp}
                      className="h-4 w-4 accent-[#C96F5C]"
                      onChange={(event) =>
                        onDeliveryChange(type, "inApp", event.target.checked)
                      }
                      type="checkbox"
                    />
                    站内
                  </label>
                  <label className="inline-flex h-9 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm font-semibold text-[#7D4F43]">
                    <input
                      aria-label={`${tone.label} 邮件通知`}
                      checked={delivery.email}
                      className="h-4 w-4 accent-[#C96F5C]"
                      onChange={(event) =>
                        onDeliveryChange(type, "email", event.target.checked)
                      }
                      type="checkbox"
                    />
                    邮件
                  </label>
                </div>
              </div>
            </div>
          );
        })}

        <div className="grid gap-3 border-t border-[#F0E1D9] pt-3 sm:grid-cols-2">
          <label className="inline-flex h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm font-semibold text-[#7D4F43]">
            <input
              aria-label="免打扰时段"
              checked={preferences.quietHoursEnabled}
              className="h-4 w-4 accent-[#C96F5C]"
              onChange={(event) => onQuietHoursChange(event.target.checked)}
              type="checkbox"
            />
            免打扰
          </label>
          <label className="grid gap-1">
            <span className="text-xs font-semibold uppercase text-[#B47767]">
              Digest Time
            </span>
            <input
              aria-label="摘要时间"
              className="h-10 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm font-semibold text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
              onChange={(event) => onDigestTimeChange(event.target.value)}
              type="time"
              value={preferences.digestTime}
            />
          </label>
        </div>

        <div className="rounded-xl border border-[#F0E1D9] bg-[#FFF8F4] px-3 py-2 text-sm text-[#5F4A43]">
          <p>
            邮件通道：<span className="font-semibold">{emailState}</span>
          </p>
          {preferences.updatedAt ? (
            <p className="mt-1 text-xs text-[#7A625A]">
              保存于 {formatDate(preferences.updatedAt)}
            </p>
          ) : null}
          {error ? (
            <p className="mt-1 text-xs font-semibold text-[#B85F4F]">{error}</p>
          ) : null}
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.18)] transition hover:bg-[#B85F4F]"
            onClick={onSave}
            type="button"
          >
            <Save size={16} aria-hidden="true" />
            保存偏好
          </button>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm font-semibold text-[#7D4F43] transition hover:border-[#C96F5C]"
            onClick={onReset}
            type="button"
          >
            <RotateCcw size={16} aria-hidden="true" />
            重置
          </button>
        </div>
      </div>
    </div>
  );
}

function NotificationDetail({
  notification,
}: {
  notification: NotificationItem;
}) {
  const tone = getNotificationTone(notification.notificationType);
  const Icon = notification.isRead ? MailOpen : tone.icon;
  const training = isTrainingNotification(notification);
  return (
    <div className="grid gap-4">
      {training ? (
        <div className="rounded-2xl border border-[#F1D9A8] bg-[#FFF9E9] p-4">
          <p className="text-xs font-semibold uppercase text-[#8C6824]">Training Notification</p>
          <p className="mt-1 text-sm leading-6 text-[#87611B]">
            该通知用于演示培训交付链路：报告、告警和证据准备状态会进入站内收件箱，并可进一步连接邮件通道。
          </p>
        </div>
      ) : null}
      <div className={cn("rounded-2xl border p-4", tone.surface)}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={cn("text-xs font-semibold uppercase", tone.text)}>
              {tone.label}
            </p>
            <h3 className="mt-1 break-words text-lg font-semibold text-[#2E201C]">
              {notification.title}
            </h3>
            <p className="mt-1 text-sm text-[#7A625A]">
              {formatDate(notification.createdAt)}
            </p>
          </div>
          <span
            className={cn(
              "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white",
              notification.isRead ? "bg-[#B9A19A]" : tone.accent,
            )}
          >
            <Icon size={18} aria-hidden="true" />
          </span>
        </div>
        <p className="mt-4 text-sm leading-6 text-[#5F4A43]">
          {notification.body}
        </p>
      </div>

      <div className="grid gap-2">
        <DetailRow label="Notification ID" value={notification.id} />
        <DetailRow label="Reference Type" value={notification.referenceType} />
        <DetailRow label="Reference ID" value={notification.referenceId} />
        <DetailRow
          label="Read State"
          value={notification.isRead ? "read" : "unread"}
        />
      </div>

      <Link
        className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(201,111,92,0.22)] transition hover:bg-[#B85F4F]"
        href={referenceHref(notification)}
      >
        <ExternalLink size={16} aria-hidden="true" />
        打开关联对象
      </Link>
    </div>
  );
}

function MetricPill({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Bell;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 px-4 py-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
        <Icon size={14} aria-hidden="true" />
        {label}
      </div>
      <p className="mt-2 break-words text-xl font-semibold text-[#2E201C]">
        {value}
      </p>
    </div>
  );
}

function InboxRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2">
      <span className="text-sm font-medium text-[#7A625A]">{label}</span>
      <span className="text-sm font-semibold text-[#3B2924]">{value}</span>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 py-2 text-sm">
      <span className="text-xs font-semibold uppercase text-[#B47767]">
        {label}
      </span>
      <p className="mt-1 break-all font-semibold text-[#3B2924]">{value}</p>
    </div>
  );
}

function StatusNotice({
  message,
  error,
}: {
  message: string | null;
  error: string | null;
}) {
  if (!message && !error) {
    return null;
  }
  return (
    <div className="mb-4 grid gap-2">
      {message ? (
        <p className="rounded-xl border border-[#CDE6C4] bg-[#F3FAEF] px-3 py-2 text-sm font-medium text-[#4E7C45]">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function getNotificationTone(type: string) {
  return (
    notificationTone[type] ?? {
      label: type,
      icon: Bell,
      accent: "bg-[#B47767]",
      surface: "border-[#E8D4CB] bg-[#FFF8F4]",
      text: "text-[#9E5C4D]",
    }
  );
}

function referenceHref(notification: NotificationItem) {
  if (notification.referenceType === "report") {
    return "/reports";
  }
  if (notification.referenceType === "alert_event") {
    return "/alerts";
  }
  if (notification.referenceType === "task_run") {
    return "/tasks";
  }
  return "/dashboard";
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function mergeNotificationPreferences(
  value: unknown,
): NotificationPreferenceState {
  if (!value || typeof value !== "object") {
    return defaultPreferences;
  }
  const candidate = value as {
    delivery?: Record<string, Partial<{ inApp: boolean; email: boolean }>>;
    quietHoursEnabled?: unknown;
    digestTime?: unknown;
    updatedAt?: unknown;
  };
  const delivery = { ...defaultPreferences.delivery };
  for (const type of preferenceTypes) {
    const current = candidate.delivery?.[type];
    if (!current) {
      continue;
    }
    delivery[type] = {
      inApp:
        typeof current.inApp === "boolean"
          ? current.inApp
          : defaultPreferences.delivery[type].inApp,
      email:
        typeof current.email === "boolean"
          ? current.email
          : defaultPreferences.delivery[type].email,
    };
  }
  return {
    delivery,
    quietHoursEnabled:
      typeof candidate.quietHoursEnabled === "boolean"
        ? candidate.quietHoursEnabled
        : defaultPreferences.quietHoursEnabled,
    digestTime:
      typeof candidate.digestTime === "string" &&
      /^\d{2}:\d{2}$/.test(candidate.digestTime)
        ? candidate.digestTime
        : defaultPreferences.digestTime,
    updatedAt:
      typeof candidate.updatedAt === "string" ? candidate.updatedAt : null,
  };
}
