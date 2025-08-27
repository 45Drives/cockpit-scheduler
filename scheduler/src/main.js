import { createApp } from 'vue';
import './assets/scheduler.css';
import "./style.css";
import App from './App.vue';
import '@45drives/houston-common-css/src/index.css';
import '@45drives/houston-common-ui/style.css';
import { createPinia } from 'pinia';
import { router } from './router';
import { applyThemeFromAliasStyle } from "./composables/theme.js";

// ⬅️ add this
import { useClientContextStore } from './stores/clientContext';

async function bootstrapApp() {
  // theme stuff (unchanged)
  try {
    const serverInfoResult = await server.getServerInfo();
    if (serverInfoResult && typeof serverInfoResult.match === "function") {
      serverInfoResult.match(
        (info) => applyThemeFromAliasStyle(info["Alias Style"]),
        () => applyThemeFromAliasStyle()
      );
    } else {
      const info = serverInfoResult || {};
      applyThemeFromAliasStyle(info["Alias Style"]);
    }
  } catch {
    const hashParams = new URLSearchParams((location.hash || "").replace(/^#/, ""));
    const aliasFromHash = hashParams.get("aliasStyle");
    const aliasFromStorage = localStorage.getItem("aliasStyle");
    applyThemeFromAliasStyle(aliasFromHash || aliasFromStorage || undefined);
  }

  // ⬇️ create app/pinia first
  const app = createApp(App);
  const pinia = createPinia();
  app.use(pinia);

  // ⬇️ HYDRATE THE ID *BEFORE* installing the router / mounting
  const clientCtx = useClientContextStore(pinia);
  clientCtx.hydrateFromUrl();
  // optional: debug
  // console.log('[clientCtx] hydrated installId =', clientCtx.clientId);

  // ⬇️ keep it sticky across navigations (so pushes don’t drop it)
  router.beforeEach((to, _from, next) => {
    // ensure store has it (first load already did, but cheap to re-check)
    if (!clientCtx.clientId) clientCtx.hydrateFromUrl();

    const id = clientCtx.clientId;
    if (id) {
      const q = to.query.client_id;
      const current = Array.isArray(q) ? q[0] : q;
      if (current !== id) {
        next({ ...to, query: { ...to.query, client_id: id } });
        return;
      }
    }
    next();
  });

  app.use(router);
  await router.isReady();
  app.mount("#app");
}

bootstrapApp();
