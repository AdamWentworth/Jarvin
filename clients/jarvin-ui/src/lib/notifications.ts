import type { ReminderItem } from "./types";

const REMINDER_NOTIFICATIONS_ENABLED_KEY = "jarvin.reminderNotifications.enabled";
const REMINDER_NOTIFICATION_SCHEDULES_KEY = "jarvin.reminderNotifications.schedules";
const DELIVERED_REMINDER_NOTIFICATIONS_KEY = "jarvin.reminderNotifications.delivered";

export const REMINDER_NOTIFICATION_CHANNEL_ID = "jarvin-reminders";
export const REMINDER_NOTIFICATION_SYNC_WINDOW_DAYS = 14;

export type ReminderNotificationPermission =
  | NotificationPermission
  | "prompt-with-rationale"
  | "blocked-in-settings"
  | "unsupported";

export type ScheduledReminderNotification = {
  id: number;
  reminderId: number;
  signature: string;
  dueAt: string;
};

type DeliveredReminderNotifications = Record<string, string>;

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function safeParseJson<T>(raw: string | null, fallback: T): T {
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function getStoredReminderNotificationsEnabled(): boolean {
  if (!canUseStorage()) {
    return false;
  }
  return window.localStorage.getItem(REMINDER_NOTIFICATIONS_ENABLED_KEY) === "true";
}

export function setStoredReminderNotificationsEnabled(value: boolean) {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.setItem(REMINDER_NOTIFICATIONS_ENABLED_KEY, String(value));
}

export function getStoredScheduledReminderNotifications(): Record<string, ScheduledReminderNotification> {
  if (!canUseStorage()) {
    return {};
  }
  const parsed = safeParseJson<Record<string, ScheduledReminderNotification>>(
    window.localStorage.getItem(REMINDER_NOTIFICATION_SCHEDULES_KEY),
    {},
  );

  const cleaned: Record<string, ScheduledReminderNotification> = {};
  for (const [key, value] of Object.entries(parsed)) {
    if (
      value &&
      typeof value.id === "number" &&
      typeof value.reminderId === "number" &&
      typeof value.signature === "string" &&
      typeof value.dueAt === "string"
    ) {
      cleaned[key] = value;
    }
  }
  return cleaned;
}

export function setStoredScheduledReminderNotifications(value: Record<string, ScheduledReminderNotification>) {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.setItem(REMINDER_NOTIFICATION_SCHEDULES_KEY, JSON.stringify(value));
}

export function clearStoredScheduledReminderNotifications() {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.removeItem(REMINDER_NOTIFICATION_SCHEDULES_KEY);
}

export function getStoredDeliveredReminderNotifications(): DeliveredReminderNotifications {
  if (!canUseStorage()) {
    return {};
  }
  const parsed = safeParseJson<DeliveredReminderNotifications>(
    window.localStorage.getItem(DELIVERED_REMINDER_NOTIFICATIONS_KEY),
    {},
  );

  const cleaned: DeliveredReminderNotifications = {};
  for (const [signature, timestamp] of Object.entries(parsed)) {
    if (typeof timestamp === "string") {
      cleaned[signature] = timestamp;
    }
  }
  return pruneDeliveredReminderNotifications(cleaned);
}

export function setStoredDeliveredReminderNotifications(value: DeliveredReminderNotifications) {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.setItem(
    DELIVERED_REMINDER_NOTIFICATIONS_KEY,
    JSON.stringify(pruneDeliveredReminderNotifications(value)),
  );
}

export function reminderNotificationSignature(reminder: ReminderItem): string {
  return [
    reminder.id,
    reminder.title.trim(),
    reminder.notes.trim(),
    reminder.due_at,
    reminder.recurrence,
    reminder.status,
  ].join("|");
}

export function reminderNotificationId(reminderId: number, dueAt: string, kind: "scheduled" | "catchup" | "test" = "scheduled"): number {
  const seed = `${kind}:${reminderId}:${dueAt}`;
  let hash = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  const normalized = Math.abs(hash | 0);
  return normalized === 0 ? 1 : normalized;
}

export function formatReminderNotificationBody(reminder: ReminderItem): string {
  const dueLabel = formatReminderDueLabel(reminder.due_at);
  const note = reminder.notes.trim();
  if (note) {
    return `${dueLabel}\n${note}`;
  }
  return dueLabel;
}

export function formatReminderDueLabel(dueAt: string): string {
  const parsed = new Date(dueAt);
  if (Number.isNaN(parsed.getTime())) {
    return dueAt;
  }
  return parsed.toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function pruneDeliveredReminderNotifications(records: DeliveredReminderNotifications): DeliveredReminderNotifications {
  const cutoff = Date.now() - 1000 * 60 * 60 * 24 * 30;
  const entries = Object.entries(records)
    .filter(([, timestamp]) => {
      const parsed = new Date(timestamp).getTime();
      return Number.isFinite(parsed) && parsed >= cutoff;
    })
    .sort((left, right) => right[1].localeCompare(left[1]))
    .slice(0, 300);

  return Object.fromEntries(entries);
}
