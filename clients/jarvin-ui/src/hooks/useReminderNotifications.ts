import { useEffect, useMemo, useRef, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import {
  Importance,
  Schedule,
  Visibility,
  cancel,
  channels,
  createChannel,
  isPermissionGranted,
  requestPermission,
  sendNotification,
} from "@tauri-apps/plugin-notification";

import { getDueReminders, getReminders } from "../lib/api";
import {
  REMINDER_NOTIFICATION_CHANNEL_ID,
  REMINDER_NOTIFICATION_SYNC_WINDOW_DAYS,
  clearStoredScheduledReminderNotifications,
  formatReminderNotificationBody,
  getStoredDeliveredReminderNotifications,
  getStoredReminderNotificationsEnabled,
  getStoredScheduledReminderNotifications,
  reminderNotificationId,
  reminderNotificationSignature,
  setStoredDeliveredReminderNotifications,
  setStoredReminderNotificationsEnabled,
  setStoredScheduledReminderNotifications,
  type ReminderNotificationPermission,
  type ScheduledReminderNotification,
} from "../lib/notifications";
import type { ReminderItem } from "../lib/types";

const REMINDER_SYNC_INTERVAL_MS = 1000 * 60 * 5;

type UseReminderNotificationsArgs = {
  apiBaseUrl: string;
  isClientOnline: boolean;
  describeError: (error: unknown) => string;
};

type UseReminderNotificationsResult = {
  notificationsSupported: boolean;
  notificationsEnabled: boolean;
  notificationPermission: ReminderNotificationPermission;
  notificationStatus: string;
  notificationSyncing: boolean;
  scheduledReminderCount: number;
  lastNotificationSyncAt: string | null;
  setNotificationsEnabled: (value: boolean) => Promise<void>;
  requestNotificationsPermission: () => Promise<void>;
  syncReminderNotifications: () => Promise<void>;
  sendTestNotification: () => Promise<void>;
};

function currentNotificationPermission(granted: boolean): ReminderNotificationPermission {
  if (granted) {
    return "granted";
  }
  if (typeof window !== "undefined" && "Notification" in window && typeof window.Notification?.permission === "string") {
    return window.Notification.permission;
  }
  return "default";
}

function dueTimeMs(reminder: ReminderItem): number {
  return new Date(reminder.due_at).getTime();
}

function notificationTitle(reminder: ReminderItem, kind: "scheduled" | "catchup"): string {
  return kind === "catchup" ? `Reminder due: ${reminder.title}` : `Reminder: ${reminder.title}`;
}

export function useReminderNotifications({
  apiBaseUrl,
  isClientOnline,
  describeError,
}: UseReminderNotificationsArgs): UseReminderNotificationsResult {
  const notificationsSupported = useMemo(
    () => typeof window !== "undefined" && isTauri(),
    [],
  );

  const [notificationsEnabled, setNotificationsEnabledState] = useState(() => getStoredReminderNotificationsEnabled());
  const [notificationPermission, setNotificationPermission] = useState<ReminderNotificationPermission>(
    notificationsSupported ? "default" : "unsupported",
  );
  const [notificationStatus, setNotificationStatus] = useState("");
  const [notificationSyncing, setNotificationSyncing] = useState(false);
  const [scheduledReminderCount, setScheduledReminderCount] = useState(0);
  const [lastNotificationSyncAt, setLastNotificationSyncAt] = useState<string | null>(null);
  const channelReadyRef = useRef(false);
  const syncInFlightRef = useRef(false);

  async function refreshPermissionState(): Promise<ReminderNotificationPermission> {
    if (!notificationsSupported) {
      setNotificationPermission("unsupported");
      return "unsupported";
    }

    const granted = await isPermissionGranted();
    const next = currentNotificationPermission(granted);
    setNotificationPermission(next);
    return next;
  }

  async function ensureReminderChannel() {
    if (!notificationsSupported || channelReadyRef.current) {
      return;
    }

    const existing = await channels();
    if (!existing.some((channel) => channel.id === REMINDER_NOTIFICATION_CHANNEL_ID)) {
      await createChannel({
        id: REMINDER_NOTIFICATION_CHANNEL_ID,
        name: "Jarvin reminders",
        description: "Reminder and brief notifications from your Jarvin host.",
        importance: Importance.High,
        vibration: true,
        visibility: Visibility.Private,
      });
    }
    channelReadyRef.current = true;
  }

  async function disableReminderNotifications() {
    const existing = getStoredScheduledReminderNotifications();
    const ids = Object.values(existing).map((entry) => entry.id);
    if (ids.length > 0) {
      await cancel(ids);
    }
    clearStoredScheduledReminderNotifications();
    setScheduledReminderCount(0);
    setLastNotificationSyncAt(null);
    setNotificationStatus("Reminder notifications are turned off on this device.");
  }

  async function syncReminderNotifications() {
    if (!notificationsSupported) {
      setNotificationStatus("System notifications are available in the installed Jarvin app.");
      return;
    }

    if (syncInFlightRef.current) {
      return;
    }

    syncInFlightRef.current = true;
    setNotificationSyncing(true);

    try {
      if (!notificationsEnabled) {
        await disableReminderNotifications();
        return;
      }

      const permission = await refreshPermissionState();
      if (permission !== "granted") {
        setNotificationStatus("Allow notifications on this device to receive Jarvin reminders.");
        return;
      }

      if (!isClientOnline) {
        setNotificationStatus("Client is offline. Existing scheduled notifications on this device will still fire.");
        return;
      }

      await ensureReminderChannel();

      const [pendingReminders, dueReminders] = await Promise.all([
        getReminders("pending", 100),
        getDueReminders(0, 25),
      ]);

      const now = Date.now();
      const syncWindowMs = REMINDER_NOTIFICATION_SYNC_WINDOW_DAYS * 24 * 60 * 60 * 1000;
      const tracked = getStoredScheduledReminderNotifications();
      const nextTracked: Record<string, ScheduledReminderNotification> = {};
      const idsToCancel: number[] = [];

      const scheduleCandidates = pendingReminders.reminders.filter((reminder) => {
        const dueAt = dueTimeMs(reminder);
        return Number.isFinite(dueAt) && dueAt > now && dueAt <= now + syncWindowMs;
      });

      for (const [key, record] of Object.entries(tracked)) {
        const reminder = scheduleCandidates.find((item) => String(item.id) === key);
        if (!reminder) {
          idsToCancel.push(record.id);
          continue;
        }

        const signature = reminderNotificationSignature(reminder);
        const nextId = reminderNotificationId(reminder.id, reminder.due_at);
        if (record.signature !== signature || record.id !== nextId) {
          idsToCancel.push(record.id);
        }
      }

      if (idsToCancel.length > 0) {
        await cancel(Array.from(new Set(idsToCancel)));
      }

      for (const reminder of scheduleCandidates) {
        const key = String(reminder.id);
        const signature = reminderNotificationSignature(reminder);
        const id = reminderNotificationId(reminder.id, reminder.due_at);
        const existing = tracked[key];
        if (!existing || existing.signature !== signature || existing.id !== id) {
          sendNotification({
            id,
            channelId: REMINDER_NOTIFICATION_CHANNEL_ID,
            title: notificationTitle(reminder, "scheduled"),
            body: formatReminderNotificationBody(reminder),
            largeBody: reminder.notes.trim() || undefined,
            summary: reminder.is_routine ? `Routine • ${reminder.recurrence}` : "Reminder",
            autoCancel: true,
            schedule: Schedule.at(new Date(reminder.due_at), false, true),
            extra: {
              reminderId: reminder.id,
              dueAt: reminder.due_at,
            },
          });
        }

        nextTracked[key] = {
          id,
          reminderId: reminder.id,
          signature,
          dueAt: reminder.due_at,
        };
      }

      setStoredScheduledReminderNotifications(nextTracked);
      setScheduledReminderCount(Object.keys(nextTracked).length);

      const delivered = getStoredDeliveredReminderNotifications();
      let deliveredCount = 0;
      for (const reminder of dueReminders.reminders) {
        const signature = reminderNotificationSignature(reminder);
        if (delivered[signature]) {
          continue;
        }

        const trackedRecord = nextTracked[String(reminder.id)] ?? tracked[String(reminder.id)];
        if (trackedRecord?.signature === signature) {
          continue;
        }

        sendNotification({
          id: reminderNotificationId(reminder.id, reminder.due_at, "catchup"),
          channelId: REMINDER_NOTIFICATION_CHANNEL_ID,
          title: notificationTitle(reminder, "catchup"),
          body: formatReminderNotificationBody(reminder),
          largeBody: reminder.notes.trim() || undefined,
          summary: "Jarvin catch-up reminder",
          autoCancel: true,
          extra: {
            reminderId: reminder.id,
            dueAt: reminder.due_at,
            catchup: true,
          },
        });
        delivered[signature] = new Date().toISOString();
        deliveredCount += 1;
      }

      setStoredDeliveredReminderNotifications(delivered);
      const syncedAt = new Date().toISOString();
      setLastNotificationSyncAt(syncedAt);
      setNotificationStatus(
        deliveredCount > 0
          ? `Reminder notifications synced. ${Object.keys(nextTracked).length} scheduled and ${deliveredCount} sent immediately.`
          : `Reminder notifications synced. ${Object.keys(nextTracked).length} scheduled on this device.`,
      );
    } catch (error) {
      setNotificationStatus(describeError(error));
    } finally {
      syncInFlightRef.current = false;
      setNotificationSyncing(false);
    }
  }

  async function setNotificationsEnabled(value: boolean) {
    setNotificationsEnabledState(value);
    setStoredReminderNotificationsEnabled(value);

    if (!value) {
      try {
        await disableReminderNotifications();
      } catch (error) {
        setNotificationStatus(describeError(error));
      }
      return;
    }

    const permission = await refreshPermissionState();
    if (permission === "granted") {
      await syncReminderNotifications();
    } else {
      setNotificationStatus("Reminder notifications are enabled. Allow notifications on this device to finish setup.");
    }
  }

  async function requestNotificationsPermission() {
    if (!notificationsSupported) {
      setNotificationStatus("System notifications are available in the installed Jarvin app.");
      return;
    }

    try {
      setNotificationStatus("Requesting notification permission...");
      const permission = await requestPermission();
      const nextPermission = permission === "granted" ? "granted" : permission;
      setNotificationPermission(nextPermission);

      if (permission === "granted") {
        setNotificationStatus(
          notificationsEnabled
            ? "Notification permission granted. Syncing reminders..."
            : "Notification permission granted. Turn reminder notifications on when you want Jarvin to use them.",
        );
        if (notificationsEnabled) {
          await syncReminderNotifications();
        }
      } else {
        setNotificationStatus("Notification permission was not granted on this device.");
      }
    } catch (error) {
      setNotificationStatus(describeError(error));
    }
  }

  async function sendTestNotification() {
    if (!notificationsSupported) {
      setNotificationStatus("System notifications are available in the installed Jarvin app.");
      return;
    }

    try {
      const permission = await refreshPermissionState();
      if (permission !== "granted") {
        setNotificationStatus("Allow notifications on this device before sending a test alert.");
        return;
      }

      await ensureReminderChannel();
      sendNotification({
        id: reminderNotificationId(0, new Date().toISOString(), "test"),
        channelId: REMINDER_NOTIFICATION_CHANNEL_ID,
        title: "Jarvin test notification",
        body: "System notifications are working on this device.",
        summary: "Jarvin mobile",
        autoCancel: true,
      });
      setNotificationStatus("Test notification sent to this device.");
    } catch (error) {
      setNotificationStatus(describeError(error));
    }
  }

  useEffect(() => {
    if (!notificationsSupported) {
      return;
    }
    void refreshPermissionState();
  }, [notificationsSupported]);

  useEffect(() => {
    if (!notificationsSupported || !notificationsEnabled) {
      return;
    }
    void syncReminderNotifications();
  }, [apiBaseUrl, isClientOnline, notificationsEnabled, notificationsSupported]);

  useEffect(() => {
    if (!notificationsSupported || !notificationsEnabled) {
      return;
    }

    const interval = window.setInterval(() => {
      void syncReminderNotifications();
    }, REMINDER_SYNC_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [notificationsEnabled, notificationsSupported, apiBaseUrl, isClientOnline]);

  return {
    notificationsSupported,
    notificationsEnabled,
    notificationPermission,
    notificationStatus,
    notificationSyncing,
    scheduledReminderCount,
    lastNotificationSyncAt,
    setNotificationsEnabled,
    requestNotificationsPermission,
    syncReminderNotifications,
    sendTestNotification,
  };
}
