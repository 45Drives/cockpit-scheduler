import { createApp } from 'vue';
import './assets/scheduler.css';
import "./style.css";
import App from './App.vue';
import '@45drives/houston-common-css/src/index.css';
import '../../houston-common/houston-common-ui/dist/style.css';
import { createPinia } from 'pinia';
import { router } from './router';
import { applyThemeFromAliasStyle } from "./composables/theme.js";


async function bootstrapApp() {
  // Try to get the alias from server info (same as your other app)
  try {
    const serverInfoResult = await server.getServerInfo();

    // If getServerInfo() returns a Result-like object with .match(...)
    if (serverInfoResult && typeof serverInfoResult.match === "function") {
      serverInfoResult.match(
        (info) => applyThemeFromAliasStyle(info["Alias Style"]),
        () => applyThemeFromAliasStyle() // default theme
      );
    } else {
      // If it returns a plain object instead:
      const info = serverInfoResult || {};
      applyThemeFromAliasStyle(info["Alias Style"]);
    }
  } catch (e) {
    // Fallbacks if you’re running standalone (no server info available)
    // 1) URL hash:  #aliasStyle=homelab
    const hashParams = new URLSearchParams((location.hash || "").replace(/^#/, ""));
    const aliasFromHash = hashParams.get("aliasStyle");

    // 2) Or read from localStorage:
    const aliasFromStorage = localStorage.getItem("aliasStyle");

    applyThemeFromAliasStyle(aliasFromHash || aliasFromStorage || undefined);
  }

  createApp(App).use(createPinia()).use(router).mount("#app");
}

bootstrapApp();