"use client";

import { Bell, CheckCheck, MailOpen } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/api/notifications";
import type { NotificationItem } from "@/types/notification";

export function NotificationsWorkspace() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [filter, setFilter] = useState<"unread" | "all">("unread");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    listNotifications(filter === "unread" ? false : undefined)
      .then((items) => {
        if (mounted) {
          setNotifications(items);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load notifications");
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

  async function handleRead(notification: NotificationItem) {
    const updated = await markNotificationRead(notification.id);
    setNotifications((current) =>
      current
        .map((item) => (item.id === updated.id ? updated : item))
        .filter((item) => filter === "all" || !item.isRead),
    );
  }

  async function handleReadAll() {
    await markAllNotificationsRead();
    setNotifications((current) =>
      filter === "all" ? current.map((item) => ({ ...item, isRead: true })) : [],
    );
  }

  return (
    <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-base font-semibold">通知列表</h2>
          <p className="mt-1 text-sm text-[#6b7280]">Report · Alert · Task</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className={`rounded-md px-3 py-2 text-sm font-semibold ${
              filter === "unread" ? "bg-[#0f766e] text-white" : "border border-[#dfe3ea]"
            }`}
            onClick={() => setFilter("unread")}
            type="button"
          >
            Unread
          </button>
          <button
            className={`rounded-md px-3 py-2 text-sm font-semibold ${
              filter === "all" ? "bg-[#0f766e] text-white" : "border border-[#dfe3ea]"
            }`}
            onClick={() => setFilter("all")}
            type="button"
          >
            All
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-md border border-[#dfe3ea] px-3 py-2 text-sm font-semibold"
            onClick={() => void handleReadAll()}
            type="button"
          >
            <CheckCheck size={16} aria-hidden="true" />
            Read All
          </button>
        </div>
      </div>

      {loading ? <p className="text-sm text-[#6b7280]">加载通知中</p> : null}
      {error ? (
        <p className="mb-4 rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
          {error}
        </p>
      ) : null}

      <div className="grid gap-3">
        {notifications.map((notification) => (
          <article
            className={`rounded-md border p-4 ${
              notification.isRead ? "border-[#dfe3ea] bg-white" : "border-[#0f766e] bg-[#ecfdf5]"
            }`}
            key={notification.id}
          >
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  {notification.isRead ? (
                    <MailOpen size={17} className="text-[#6b7280]" aria-hidden="true" />
                  ) : (
                    <Bell size={17} className="text-[#0f766e]" aria-hidden="true" />
                  )}
                  <h3 className="text-sm font-semibold">{notification.title}</h3>
                </div>
                <p className="mt-2 text-sm leading-6 text-[#4b5563]">{notification.body}</p>
                <p className="mt-2 text-xs text-[#6b7280]">
                  {notification.notificationType} · {formatDate(notification.createdAt)}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Link
                  className="rounded-md border border-[#dfe3ea] px-3 py-2 text-sm font-semibold"
                  href={referenceHref(notification)}
                >
                  Open
                </Link>
                {!notification.isRead ? (
                  <button
                    className="rounded-md bg-[#0f766e] px-3 py-2 text-sm font-semibold text-white"
                    onClick={() => void handleRead(notification)}
                    type="button"
                  >
                    Read
                  </button>
                ) : null}
              </div>
            </div>
          </article>
        ))}
        {!loading && notifications.length === 0 ? (
          <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
            暂无通知
          </div>
        ) : null}
      </div>
    </section>
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
