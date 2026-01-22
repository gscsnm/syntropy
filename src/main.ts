import { createApp } from "vue";
import App from "./App.vue";
import { router } from "./router";
import "./styles/main.css";
import "markstream-vue/index.css";
import i18n from "./i18n";
import { pyInvoke } from "tauri-plugin-pytauri-api";
import { trackEvent } from "@aptabase/tauri";

const app = createApp(App);
app.use(router);
app.use(i18n);
app.mount("#app");

const canTrackAnalytics = typeof (window as any).__TAURI_IPC__ === "function";
router.afterEach((to) => {
  if (!canTrackAnalytics) return;
  trackEvent("screen_view", { name: String(to.name ?? to.path) });
});

pyInvoke("get_app_language")
  .then((resp: any) => {
    i18n.global.locale.value = resp.language;
  })
  .catch(() => {
    // ignore
  });
