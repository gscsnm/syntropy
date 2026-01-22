import { createRouter, createWebHashHistory } from "vue-router";

/**
 * 路由说明：
 * - Tauri 环境下推荐使用 Hash 路由，避免刷新后路径解析问题；
 * - 页面结构来自 `/src/design/App.tsx` 的四个 Tab。
 */
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/analysis" },
    {
      path: "/analysis",
      name: "analysis",
      component: () => import("../pages/AnalysisPage.vue"),
    },
    {
      path: "/history",
      name: "history",
      component: () => import("../pages/HistoryPage.vue"),
    },
    {
      path: "/watchlist",
      name: "watchlist",
      component: () => import("../pages/WatchlistPage.vue"),
    },
    {
      path: "/trading",
      name: "trading",
      component: () => import("../pages/TradingPage.vue"),
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("../pages/NotFoundPage.vue"),
    },
  ],
});
