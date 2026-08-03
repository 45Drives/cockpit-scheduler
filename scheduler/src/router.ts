import { createRouter, createWebHashHistory, RouteRecordRaw, RouteLocationNormalized } from 'vue-router';
import { useTaskDraftStore } from './stores/taskDraft';

const SimplifiedView = () => import('./views/SimplifiedView.vue');
const AddTaskView = () => import('./components/simple/SimpleAddTask.vue');
const ManageRemotesView = () => import('./components/simple/SimpleManageRemotes.vue');

const routes: RouteRecordRaw[] = [
    { path: '/simple', name: 'SimpleTasks', component: SimplifiedView },

    { path: '/simple/new', name: 'SimpleAddTask', component: AddTaskView, props: { mode: 'create' } },

    {
        path: '/simple/edit',
        name: 'SimpleEditTask',
        component: AddTaskView,
        props: () => {
            const store = useTaskDraftStore();
            return { mode: 'edit', existingTask: store.draft };
        },
    },

    { path: '/simple/accounts', name: 'SimpleManageRemotes', component: ManageRemotesView },
];

export const router = createRouter({
    history: createWebHashHistory(),
    routes,
});


router.beforeEach((to, from) => {
    const store = useTaskDraftStore();
    const comingBackFromRemotes = from.name === 'SimpleManageRemotes';

    // Redirect to task form if returning from Wire Wizard with a saved draft or vpnHost
    // Only redirect if the draft is recent (within 1 hour) to prevent stale drafts from persisting
    if (to.name === 'SimpleTasks') {
        const draftStr = localStorage.getItem('scheduler-task-draft');
        const vpnHost = localStorage.getItem('scheduler-vpn-host');
        
        if (draftStr || vpnHost) {
            let shouldRedirect = false;
            
            if (draftStr) {
                try {
                    const draft = JSON.parse(draftStr);
                    const savedTime = draft._savedAt || 0;
                    const oneHourAgo = Date.now() - (60 * 60 * 1000);
                    
                    if (savedTime > oneHourAgo) {
                        shouldRedirect = true;
                    } else {
                        // Draft is stale, remove it
                        localStorage.removeItem('scheduler-task-draft');
                    }
                } catch {
                    // Invalid draft, remove it
                    localStorage.removeItem('scheduler-task-draft');
                }
            }
            
            if (vpnHost) {
                shouldRedirect = true;
            }
            
            if (shouldRedirect) {
                return { name: 'SimpleAddTask' };
            }
        }
    }

    if (to.name === 'SimpleAddTask' && !comingBackFromRemotes) store.clear?.();

    if (to.name === 'SimpleEditTask') {
        if (!store.draft && !comingBackFromRemotes) return { name: 'SimpleTasks' };
    }
    return true;
});