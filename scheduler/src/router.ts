import { createRouter, createWebHashHistory, RouteRecordRaw } from 'vue-router';

const SimplifiedView = () => import('./views/SimplifiedView.vue');
const AddTaskView = () => import('./components/simple/SimpleAddTask.vue');
const ManageRemotesView = () => import('./components/simple/SimpleManageRemotes.vue');

const routes: RouteRecordRaw[] = [
    { path: '/simple', name: 'SimpleTasks', component: SimplifiedView },
    { path: '/simple/new', name: 'SimpleAddTask', component: AddTaskView },
    { path: '/simple/accounts', name: 'SimpleManageRemotes', component: ManageRemotesView },
];


export const router = createRouter({
    history: createWebHashHistory(),
    routes,
});