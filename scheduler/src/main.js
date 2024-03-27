import { createApp, reactive} from 'vue';
import './assets/scheduler.css';
import App from './App.vue';
import { FIFO } from '@45drives/cockpit-helpers';
import '@45drives/cockpit-css/src/index.css';

const notificationFIFO = reactive(new FIFO());

const app = createApp(App, { notificationFIFO });

app.mount('#app');