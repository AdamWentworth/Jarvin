import { useEffect, useMemo, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import {
  Importance,
  Schedule,
  Visibility,
  cancel,
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
const NOTIFICATION_PERMISSION_TIMEOUT_MS = 10000;

type UseReminderNotificationsArgs = {
  apiBaseUrl: string;
  isClientOnline: boolean;
  describeError: (error: unknown) => string;
};

type UseReminderNotificationsResult = {
  notificationsSupported: boolean;
  notificationsEnabled: boolean;
  notificationPermission: ReminderNotificationPermission;
  notificationNeedsSystemSettings: boolean;
  notificationStatus: string;
  notificationSyncing: boolean;
  scheduledReminderCount: number;
  lastNotificationSyncAt: string | null;
  setNotificationsEnabled: (value: boolean) => Promise<void>;
  requestNotificationsPermission: () => Promise<void>;
  syncReminderNotifications: () => Promise<void>;
  sendTestNotification: () => Promise<void>;
};

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, message: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => {
      reject(new Error(message));
    }, timeoutMs);

    promise
      .then((value) => {
        window.clearTimeout(timer);
        resolve(value);
      })
      .catch((error) => {
        window.clearTimeout(timer);
        reject(error);
      });
  });
}

function windowNotificationPermission(): ReminderNotificationPermission {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return "default";
  }

  const permission = window.Notification.permission;
  if (permission === "granted" || permission === "denied" || permission === "default") {
    return permission;
  }
  return "default";
}

async function getNotificationPermissionState(): Promise<ReminderNotificationPermission> {
  const granted = (await isPermissionGranted()) as boolean | null;
  if (granted === true) {
    return "granted";
  }
  if (granted === false) {
    return windowNotificationPermission() === "default" ? "denied" : windowNotificationPermission();
  }

  return windowNotificationPermission();
}

function permissionBlockedMessage(permission: ReminderNotificationPermission): string {
  if (permission === "granted") {
    return "Android notification permission is granted. If you still do not see Jarvin notifications, open the Jarvin app settings on your phone and make sure Notifications are enabled there.";
  }
  if (permission === "denied" || permission === "blocked-in-settings") {
    return "Notification permission is disabled for Jarvin on this device. Open the Jarvin app settings on your phone and enable Notifications there.";
  }
  if (permission === "prompt-with-rationale") {
    return "Android wants another confirmation before Jarvin can post notifications. Tap Allow notifications again and accept the system prompt on the device.";
  }
  return "Allow notifications on this device to receive Jarvin reminders.";
}

function dueTimeMs(reminder: ReminderItem): number {
  return new Date(reminder.due_at).getTime();
}

function notificationTitle(reminder: ReminderItem, kind: "scheduled" | "catchup"): string {
  return kind === "catchup" ? `Reminder due: ${reminder.title}` : `Reminder: ${reminder.title}`;
}

type NotificationChannel = {
  id: string;
  name: string;
};

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
  const [notificationNeedsSystemSettings, setNotificationNeedsSystemSettings] = useState(false);
  const [notificationStatus, setNotificationStatus] = useState("");
  const [notificationSyncing, setNotificationSyncing] = useState(false);
  const [scheduledReminderCount, setScheduledReminderCount] = useState(0);
  const [lastNotificationSyncAt, setLastNotificationSyncAt] = useState<string | null>(null);
  const channelReadyRef = useRef(false);
  const syncInFlightRef = useRef(false);

  async function refreshPermissionState(): Promise<ReminderNotificationPermission> {
    if (!notificationsSupported) {
      setNotificationPermission("unsupported");
      setNotificationNeedsSystemSettings(false);
      return "unsupported";
    }

    const next = await getNotificationPermissionState();
    setNotificationNeedsSystemSettings(next === "denied" || next === "blocked-in-settings");
    setNotificationPermission(next);
    return next;
  }

  async function ensureReminderChannel() {
    if (!notificationsSupported || channelReadyRef.current) {
      return;
    }

    const existing = await invoke<NotificationChannel[]>("plugin:notification|list_channels");
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
        setNotificationStatus(permissionBlockedMessage(permission));
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
      setNotificationNeedsSystemSettings(permission === "denied" || permission === "blocked-in-settings");
      setNotificationStatus(permissionBlockedMessage(permission));
    }
  }

  async function requestNotificationsPermission() {
    if (!notificationsSupported) {
      setNotificationStatus("System notifications are available in the installed Jarvin app.");
      return;
    }

    try {
      const currentPermission = await refreshPermissionState();
      if (currentPermission === "granted") {
        setNotificationStatus(
          notificationsEnabled
            ? "Notification permission is already granted. Syncing reminders..."
            : "Notification permission is already granted on this device.",
        );
        if (notificationsEnabled) {
          await syncReminderNotifications();
        }
        return;
      }

      setNotificationStatus("Requesting notification permission...");
      const permission = await withTimeout(
        requestPermission() as Promise<ReminderNotificationPermission>,
        NOTIFICATION_PERMISSION_TIMEOUT_MS,
        "Notification permission request did not finish. If Android did not show a prompt, open the Jarvin app settings on your phone and enable Notifications there.",
      );
      const nextPermission = await refreshPermissionState();
      setNotificationPermission(nextPermission);

      if (nextPermission === "granted") {
        setNotificationStatus(
          notificationsEnabled
            ? "Notification permission granted. Syncing reminders..."
            : "Notification permission granted. Turn reminder notifications on when you want Jarvin to use them.",
        );
        if (notificationsEnabled) {
          await syncReminderNotifications();
        }
      } else {
        setNotificationNeedsSystemSettings(permission === "denied");
        setNotificationStatus(permissionBlockedMessage(permission));
      }
    } catch (error) {
      setNotificationNeedsSystemSettings(true);
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
        setNotificationStatus(permissionBlockedMessage(permission));
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
    notificationNeedsSystemSettings,
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
