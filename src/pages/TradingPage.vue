<script setup lang="ts">
import StatItem from "../components/ui/StatItem.vue";
import TechCard from "../components/ui/TechCard.vue";
import LucideIcon from "../components/icons/LucideIcon.vue";
import { useAlphaMindStore } from "../stores/alphaMindStore";
import { useI18n } from "vue-i18n";

/**
 * TradingPage：交易页（来自设计稿 trading Tab）
 *
 * 说明：
 * - 当前为“纸面交易/演示态”视图，仅用于展示 UI；
 * - 后续可在此接入真实仓位、委托、成交等数据。
 */

const store = useAlphaMindStore();
const { t } = useI18n();
</script>

<template>
  <div class="max-w-5xl mx-auto p-8 animate-fade-in pb-32 relative group min-h-full">
    <div class="mb-8 p-8 bg-slate-900 text-white rounded-2xl shadow-xl flex items-end justify-between relative overflow-hidden">
      <div class="relative z-10">
        <div class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">{{ t("模拟跟踪组合") }}</div>
        <div class="text-6xl font-black font-mono tracking-tighter">¥124,502</div>
      </div>
      <div class="relative z-10 text-right">
        <div class="text-xl font-bold text-emerald-400 font-mono">+2.4%</div>
        <div class="text-xs text-slate-400 font-bold uppercase">{{ t("今日") }}</div>
      </div>
      <div class="absolute right-0 top-0 h-full w-1/2 bg-gradient-to-l from-slate-800 to-transparent opacity-50 skew-x-12 transform translate-x-12"></div>
    </div>

    <div class="grid grid-cols-1 gap-4">
      <div class="flex items-center justify-between px-2">
        <h3 class="text-sm font-bold text-slate-500 uppercase tracking-widest">{{ t("跟踪项目") }}</h3>
      </div>

      <TechCard
        v-for="pos in store.portfolio.value"
        :key="pos.stockCode"
        class="p-6 flex flex-col md:flex-row md:items-center justify-between gap-6 hover:shadow-md"
      >
        <div class="flex items-center gap-4 min-w-[180px]">
          <div class="w-10 h-10 bg-gray-100 border border-gray-200 rounded flex items-center justify-center font-bold text-slate-700">
            {{ pos.stockCode[0] }}
          </div>
          <div>
            <div class="font-bold text-slate-900 text-lg">{{ pos.stockCode }}</div>
            <div class="text-xs text-gray-400 font-bold">{{ pos.market }}</div>
          </div>
        </div>

        <div class="flex-1 grid grid-cols-2 md:grid-cols-4 gap-8">
          <StatItem :label="t('数量')" :value="pos.quantity.toString()" />
          <StatItem :label="t('成本')" :value="pos.avgCost.toString()" />
          <StatItem :label="t('价格')" :value="pos.currentPrice.toString()" />
          <StatItem
            :label="t('盈亏')"
            :value="(((pos.currentPrice - pos.avgCost) * pos.quantity >= 0 ? '+' : '') + ((pos.currentPrice - pos.avgCost) * pos.quantity).toFixed(0))"
            :trend="(((pos.currentPrice - pos.avgCost) / pos.avgCost) * 100 >= 0 ? '+' : '') + (((pos.currentPrice - pos.avgCost) / pos.avgCost) * 100).toFixed(2) + '%'"
          />
        </div>

        <div class="flex gap-2">
          <button
            type="button"
            class="px-4 py-2 border border-slate-200 text-slate-900 text-xs font-bold rounded hover:bg-slate-900 hover:text-white transition-colors"
          >
            {{ t("跟踪") }}
          </button>
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
