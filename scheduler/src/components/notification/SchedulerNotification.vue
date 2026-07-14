<template>
  <div class="relative">
    <Menu>
      <MenuButton
        class="relative rounded-full p-1 text-gray-400 hover:text-gray-200 transition-colors"
        title="Notifications"
      >
        <BellIcon class="w-5 h-5" />
        <span
          v-if="store.notificationsCount > 0"
          class="absolute -top-1 -right-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-600 text-white text-[10px] font-bold px-0.5"
        >
          {{ store.notificationsCount }}
        </span>
      </MenuButton>

      <MenuItems
        class="absolute right-0 z-50 w-[24rem] max-h-[28rem] overflow-y-auto origin-top-right rounded-md bg-well shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"
      >
        <div class="flex items-center justify-between p-3 border-b border-default text-sm font-semibold">
          <span>Task Notifications</span>
          <button
            v-if="store.notifications.length > 0"
            @click.stop="store.clearAllNotifications()"
            class="text-xs text-gray-400 hover:text-white hover:underline"
          >
            Dismiss all
          </button>
        </div>

        <div v-if="store.notifications.length === 0" class="p-6 text-center text-sm text-muted">
          No task notifications
        </div>

        <MenuItem
          v-for="n in store.notifications"
          :key="n.id"
          as="div"
          v-slot="{ active }"
        >
          <div
            class="flex items-start gap-2 px-3 py-2 border-b border-default last:border-0"
            :class="active ? 'bg-accent' : ''"
          >
            <!-- Icon -->
            <CheckCircleIcon
              v-if="n.event === 'scheduler_task_success'"
              class="w-5 h-5 mt-0.5 shrink-0 text-green-500"
            />
            <XCircleIcon
              v-else
              class="w-5 h-5 mt-0.5 shrink-0 text-red-500"
            />

            <!-- Content -->
            <div class="flex-1 min-w-0">
              <p
                class="text-sm font-medium"
                :class="n.event === 'scheduler_task_success' ? 'text-green-500' : 'text-red-500'"
              >
                {{ n.event === 'scheduler_task_success' ? 'Task Succeeded' : 'Task Failed' }}
              </p>
              <p class="text-xs text-muted truncate" v-if="n.taskName">
                {{ n.taskName }}
                <span v-if="n.taskType" class="text-gray-500"> ({{ n.taskType }})</span>
              </p>
              <p class="text-xs text-muted" v-if="n.errors && n.errors !== '0'">
                Error: {{ n.errors }}
              </p>
              <p class="text-xs text-gray-500">{{ n.timestamp }}</p>
            </div>

            <!-- Dismiss -->
            <button
              class="shrink-0 p-0.5 text-gray-500 hover:text-red-500"
              :aria-label="n.taskName ? `Dismiss notification for ${n.taskName}` : `Dismiss ${n.event === 'scheduler_task_success' ? 'task succeeded' : 'task failed'} notification`"
              @click.stop="store.markNotificationAsRead(n.id)"
            >
              <XMarkIcon class="w-4 h-4" />
            </button>
          </div>
        </MenuItem>

        <div ref="loadMoreTrigger" class="h-4 w-full" />
      </MenuItems>
    </Menu>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, onActivated, onDeactivated } from "vue";
import { Menu, MenuButton, MenuItem, MenuItems } from "@headlessui/vue";
import { BellIcon, XMarkIcon } from "@heroicons/vue/24/outline";
import { CheckCircleIcon, XCircleIcon } from "@heroicons/vue/24/outline";
import { schedulerNotificationStore as store } from "../../store/notification";

// D-Bus listener for real-time notifications
let dbusClient: ReturnType<typeof cockpit.dbus> | null = null;
let subscription: { remove(): void } | null = null;

const loadMoreTrigger = ref<HTMLElement | null>(null);
const offset = ref(0);
const limit = 50;
const loading = ref(false);
let active = true;

// Reset pagination when all notifications are cleared
watch(() => store.notifications.length, (len) => {
  if (len === 0) offset.value = 0;
});

async function loadMore() {
  if (loading.value) return;
  loading.value = true;
  const count = await store.fetchMissedNotifications(limit, offset.value);
  if (count > 0) offset.value += limit;
  loading.value = false;
}

let observer: IntersectionObserver | null = null;

function attachObserver(el: HTMLElement | null) {
  if (!el || observer) return;
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting) loadMore();
    },
    { threshold: 1.0 }
  );
  observer.observe(el);
}

function detachObserver() {
  if (observer) {
    observer.disconnect();
    observer = null;
  }
}

// Watch for the sentinel element to appear (MenuItems only renders when menu is open)
watch(loadMoreTrigger, (el) => {
  if (el) attachObserver(el);
  else detachObserver();
});

function startDbusListener() {
  if (dbusClient) return; // already running
  try {
    dbusClient = cockpit.dbus("org._45drives.Houston", { bus: "system" });
    subscription = dbusClient.subscribe(
      { interface: "org._45drives.Houston", member: "Message" },
      (_path: string, _iface: string, _signal: string, args: any[]) => {
        if (typeof args[0] === "string") store.addNotification(args[0]);
      }
    );
  } catch (error) {
    console.error("Error setting up scheduler notification listener:", error);
  }
}

function stopDbusListener() {
  if (subscription) {
    try { subscription.remove(); } catch {}
    subscription = null;
  }
  if (dbusClient) {
    try { dbusClient.close(); } catch {}
    dbusClient = null;
  }
}

onMounted(async () => {
  await store.countMissedNotifications();
  await loadMore();
  if (active) startDbusListener();
});

onBeforeUnmount(() => {
  stopDbusListener();
  detachObserver();
});

// KeepAlive support — pause/resume D-Bus listener
onActivated(async () => {
  active = true;
  await store.countMissedNotifications();
  await loadMore();
  startDbusListener();
});

onDeactivated(() => {
  active = false;
  stopDbusListener();
  detachObserver();
});
</script>
