<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import LucideIcon from "../icons/LucideIcon.vue";

/**
 * BottomDock：底部“胶囊”导航栏
 *
 * 设计点：
 * - 对齐 React 设计稿：固定在底部居中，带 Logo 圆块；
 * - 使用路由做页面切换，避免单文件 Tab 耦合。
 */

type DockItemId = "analysis" | "history" | "watchlist" | "trading";

const route = useRoute();
const router = useRouter();

const navItems: Array<{ id: DockItemId; icon: string; to: string }> = [
  { id: "analysis", icon: "Sparkles", to: "/analysis" },
  { id: "history", icon: "Layers", to: "/history" },
  { id: "watchlist", icon: "Activity", to: "/watchlist" },
  { id: "trading", icon: "Wallet", to: "/trading" },
];

const activeId = computed<DockItemId>(() => {
  const name = route.name;
  if (name === "analysis" || name === "history" || name === "watchlist" || name === "trading") return name;
  return "analysis";
});

function go(to: string) {
  void router.push(to);
}
</script>

<template>
  <div class="fixed left-6 top-1/2 -translate-y-1/2 z-[60] animate-slide-up">
    <div class="bg-slate-900 text-gray-400 rounded-full px-2 py-2 flex flex-col items-center gap-2 shadow-2xl ring-1 ring-white/20 transition-all duration-300 hover:shadow-slate-900/50 hover:ring-white/40 hover:scale-105">
      <button
        v-for="item in navItems"
        :key="item.id"
        type="button"
        :class="[
          'relative w-12 h-12 rounded-full flex flex-col items-center justify-center transition-all duration-300 group',
          activeId === item.id ? 'bg-gray-700 text-white shadow-inner' : 'hover:bg-gray-800 hover:text-gray-200',
        ]"
        @click="go(item.to)"
      >
        <LucideIcon :name="item.icon" :size="20" />
        <div v-if="activeId === item.id" class="absolute -bottom-1 w-1 h-1 bg-white rounded-full"></div>
      </button>
    </div>
  </div>
</template>
