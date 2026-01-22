<script setup lang="ts">
import LucideIcon from "../components/icons/LucideIcon.vue";
import TechCard from "../components/ui/TechCard.vue";
import { MARKETS } from "../constants/alphaMind";
import { useAlphaMindStore } from "../stores/alphaMindStore";
import type { Market } from "../types/alphaMind";
import { useI18n } from "vue-i18n";

/**
 * WatchlistPage：市场监控（来自设计稿 watchlist Tab）
 */

const store = useAlphaMindStore();
const { t } = useI18n();

function addMockItem() {
  const pool = ["TSLA", "AMD", "9988.HK", "601398"];
  const code = pool[Math.floor(Math.random() * pool.length)];
  const market: Market = MARKETS[Math.floor(Math.random() * MARKETS.length)];
  store.addWatchlistItem({ stockCode: code, market, periodicAnalysis: Math.random() > 0.5 });
}
</script>

<template>
  <div class="max-w-4xl mx-auto p-8 animate-fade-in relative group min-h-full pb-32">
    <div class="flex justify-between items-center mb-8">
      <h2 class="text-xl font-bold text-slate-900 tracking-tight">{{ t("市场监控") }}</h2>
      <button
        type="button"
        class="flex items-center gap-2 bg-slate-900 hover:bg-black text-white px-4 py-2 rounded-lg shadow-sm text-xs font-bold transition-colors"
        @click="addMockItem"
      >
        <LucideIcon name="Plus" :size="14" />
        {{ t("新增") }}
      </button>
    </div>

    <div class="grid grid-cols-1 gap-4">
      <TechCard v-for="item in store.watchlist.value" :key="item.id" class="p-5 flex items-center justify-between group hover:border-slate-400">
        <div class="flex items-center gap-5">
          <div class="w-12 h-12 bg-slate-900 text-white rounded-lg flex items-center justify-center font-bold font-mono text-lg shadow-md">
            {{ item.stockCode[0] }}
          </div>
          <div>
            <div class="flex items-center gap-3">
              <h3 class="text-lg font-bold text-slate-900">{{ item.stockCode }}</h3>
              <span v-if="item.periodicAnalysis" class="flex h-2 w-2 relative" :title="t('监控中')">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-slate-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-slate-900"></span>
              </span>
            </div>
            <span class="text-xs font-bold text-gray-400">{{ item.market }}</span>
          </div>
        </div>

        <div class="flex items-center gap-10">
          <div class="text-right hidden sm:block">
            <div class="text-lg font-bold font-mono text-slate-900">142.50</div>
            <div class="text-xs font-bold font-mono text-emerald-600">+1.24%</div>
          </div>

          <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              type="button"
              class="p-2 text-gray-400 hover:text-slate-900 hover:bg-gray-100 rounded transition-colors"
              @click="store.startAnalysis(item.market, item.stockCode)"
            >
              <LucideIcon name="Play" :size="18" class="fill-current" />
            </button>
            <button
              type="button"
              class="p-2 text-gray-400 hover:text-rose-600 hover:bg-gray-100 rounded transition-colors"
              @click="store.removeWatchlistItem(item.id)"
            >
              <LucideIcon name="Trash2" :size="18" />
            </button>
          </div>
        </div>
      </TechCard>
    </div>

    <div
      class="absolute inset-0 z-30 opacity-0 group-hover:opacity-100 transition-opacity bg-white/35 backdrop-blur-md flex items-center justify-center pointer-events-auto cursor-not-allowed"
    >
      <div class="bg-white/70 border border-white/60 rounded-2xl shadow-xl px-8 py-6 text-center ring-1 ring-slate-900/10">
        <div class="mx-auto w-12 h-12 rounded-full bg-slate-900 text-white flex items-center justify-center shadow-sm">
          <LucideIcon name="Lock" :size="18" />
        </div>
        <div class="mt-4 text-base font-black text-slate-900">{{ t("模块开发中") }}</div>
        <div class="mt-1 text-xs font-bold text-slate-500">{{ t("当前页面仅供预览，功能尚未开放") }}</div>
      </div>
    </div>
  </div>
</template>
