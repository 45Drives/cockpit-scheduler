import { createRouter, createWebHashHistory, RouteRecordRaw } from 'vue-router';
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

// keep the guard; also clear the draft when going to "new" so the form is fresh
router.beforeEach((to) => {
    const store = useTaskDraftStore();
    if (to.name === 'SimpleAddTask') store.clear?.();
    if (to.name === 'SimpleEditTask' && (!store.draft)) return { name: 'SimpleTasks' };
    return true;
});
