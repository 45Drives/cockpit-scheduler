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

    if (to.name === 'SimpleAddTask' && !comingBackFromRemotes) store.clear?.();

    if (to.name === 'SimpleEditTask') {
        if (!store.draft && !comingBackFromRemotes) return { name: 'SimpleTasks' };
    }
    return true;
});