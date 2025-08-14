import { createApp } from 'vue';
import './assets/scheduler.css';
import App from './App.vue';
import '@45drives/houston-common-css/src/index.css';
import '../../houston-common/houston-common-ui/dist/style.css';
import { router } from './router';

const app = createApp(App);
app.use(router);
app.mount('#app');
