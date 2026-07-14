import { reactive } from "vue";

export interface SchedulerNotification {
  id: number;
  timestamp: string;
  event: string;
  taskName?: string;
  taskType?: string;
  errors?: string;
  severity?: string;
}

let _dbus: ReturnType<typeof cockpit.dbus> | null = null;
function getHoustonDbus() {
  if (!_dbus) {
    const dbus = cockpit.dbus("org._45drives.Houston", { bus: "system" });
    dbus.addEventListener("close", () => {
      if (_dbus === dbus) {
        _dbus = null;
      }
    });
    _dbus = dbus;
  }
  return _dbus;
}

const SCHEDULER_EVENTS = [
  "scheduler_task_success",
  "scheduler_task_failure",
];

const SCHEDULER_EVENTS_JSON = JSON.stringify(SCHEDULER_EVENTS);

function isSchedulerEvent(event: string | undefined): boolean {
  return !!event && SCHEDULER_EVENTS.includes(event);
}

export const schedulerNotificationStore = reactive<{
  notifications: SchedulerNotification[];
  notificationsCount: number;
  addNotification: (message: string) => void;
  fetchMissedNotifications: (limit: number, offset: number) => Promise<number>;
  markNotificationAsRead: (id: number) => Promise<void>;
  clearAllNotifications: () => Promise<void>;
  countMissedNotifications: () => Promise<void>;
}>({
  notifications: [],
  notificationsCount: 0,

  addNotification(message: string) {
    try {
      const parsed = JSON.parse(message) as SchedulerNotification;
      if (!isSchedulerEvent(parsed.event)) return;

      // Dedupe by id if present; live signals may lack an id
      if (parsed.id != null) {
        const existing = schedulerNotificationStore.notifications.find(n => n.id === parsed.id);
        if (existing) return;
      }

      schedulerNotificationStore.notifications.unshift(parsed);
      this.notificationsCount += 1;
      updateSidebar();
    } catch {
      // ignore malformed messages
    }
  },

  async fetchMissedNotifications(limit = 50, offset = 0) {
    try {
      const dbus = getHoustonDbus();
      const response = await dbus.call(
        "/org/_45drives/Houston",
        "org._45drives.Houston",
        "GetMissedNotificationsByEvents",
        [SCHEDULER_EVENTS_JSON, limit, offset]
      );
      if (!response) {
        // Server returned nothing — count should reflect what we actually have
        schedulerNotificationStore.notificationsCount = schedulerNotificationStore.notifications.length;
        updateSidebar();
        return 0;
      }

      const items: SchedulerNotification[] = JSON.parse(response);
      items.forEach((n) => {
        if (!schedulerNotificationStore.notifications.some(e => e.id === n.id)) {
          schedulerNotificationStore.notifications.push(n);
        }
      });

      // If fewer items returned than limit, we've loaded everything —
      // sync the badge count with reality
      if (items.length < limit) {
        schedulerNotificationStore.notificationsCount = schedulerNotificationStore.notifications.length;
      }

      updateSidebar();
      return items.length;
    } catch (error) {
      console.error("Error fetching scheduler notifications:", error);
      // On error, sync count with what we actually have displayed
      schedulerNotificationStore.notificationsCount = schedulerNotificationStore.notifications.length;
      updateSidebar();
      return 0;
    }
  },

  async markNotificationAsRead(id: number) {
    try {
      const dbus = getHoustonDbus();
      await dbus.call(
        "/org/_45drives/Houston",
        "org._45drives.Houston",
        "MarkNotificationAsRead",
        [id]
      );
    } catch (error) {
      console.error("Error marking notification as read:", error);
    }
    schedulerNotificationStore.notifications = schedulerNotificationStore.notifications.filter(n => n.id !== id);
    schedulerNotificationStore.notificationsCount = Math.max(0, schedulerNotificationStore.notificationsCount - 1);
    updateSidebar();
  },

  async clearAllNotifications() {
    try {
      const dbus = getHoustonDbus();
      // Mark all scheduler-scoped notifications as read in one call
      await dbus.call(
        "/org/_45drives/Houston",
        "org._45drives.Houston",
        "MarkAllNotificationsByEventsAsRead",
        [SCHEDULER_EVENTS_JSON]
      );
    } catch (error) {
      console.error("Error clearing scheduler notifications:", error);
    }
    // Always clear local state (even if D-Bus failed, user intent is clear)
    schedulerNotificationStore.notifications = [];
    schedulerNotificationStore.notificationsCount = 0;
    updateSidebar();
  },

  async countMissedNotifications() {
    try {
      const dbus = getHoustonDbus();
      const result = await dbus.call(
        "/org/_45drives/Houston",
        "org._45drives.Houston",
        "GetNotificationCountByEvents",
        [SCHEDULER_EVENTS_JSON]
      );
      const serverCount = result[0] ?? 0;
      // If we already loaded notifications, trust the array length over the
      // server count to avoid badge/list mismatch
      if (schedulerNotificationStore.notifications.length > 0) {
        schedulerNotificationStore.notificationsCount = schedulerNotificationStore.notifications.length;
      } else {
        schedulerNotificationStore.notificationsCount = serverCount;
      }
    } catch {
      // ignore
    }
  },
});

async function updateSidebar(): Promise<void> {
  const count = schedulerNotificationStore.notificationsCount;
  const dbus = getHoustonDbus();
  try {
    if (count > 0) {
      const [severity] = await dbus.call(
        "/org/_45drives/Houston",
        "org._45drives.Houston",
        "GetHighestMissedSeverityByEvents",
        [SCHEDULER_EVENTS_JSON]
      );
      (cockpit.transport as any).control("notify", {
        page_status: {
          type: severity,
          title: cockpit.gettext(`${count} Notifications available`)
        }
      });
    } else {
      (cockpit.transport as any).control("notify", {
        page_status: null
      });
    }
  } catch {
    // ignore
  }
}
