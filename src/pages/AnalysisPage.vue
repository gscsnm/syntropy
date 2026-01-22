<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import LucideIcon from "../components/icons/LucideIcon.vue";
import logoDarkUrl from "../assets/logo-dark.png";
import UiSelect, { type UiSelectOption } from "../components/ui/UiSelect.vue";
import { MARKETS } from "../constants/alphaMind";
import { useAlphaMindStore } from "../stores/alphaMindStore";
import type { Market } from "../types/alphaMind";

const { t } = useI18n();
/**
 * AnalysisPage：核心分析入口页（来自设计稿 analysis Tab）
 *
 * 维护建议：
 * - 这里的“市场指数/汇率/Trending”均为静态占位；
 * - 后续接入真实数据源时，可以保留 UI 结构，仅替换数据获取逻辑。
 */

const store = useAlphaMindStore();

const market = ref<Market>(MARKETS[0]);
const stockInput = ref("");

onMounted(() => {
  void store.refreshTasks();
});

const marketOptions = computed<UiSelectOption[]>(() =>
  MARKETS.map((m) => ({
    value: m,
    label: m === "CN" ? t("A股 / 沪深京") : m === "HK" ? t("港股 / HK") : t("美股 / US"),
    disabled: m !== "CN",
  })),
);

function start() {
  store.startAnalysis(market.value, stockInput.value);
}

function startWithCode(code: string) {
  store.startAnalysis(market.value, code);
}
</script>

<template>
  <div class="h-full flex flex-col items-center justify-center px-6 -mt-4 animate-fade-in overflow-hidden">
    <div class="mb-8 relative group">
      <div
        class="absolute -inset-8 bg-gradient-to-tr from-gray-200 to-gray-100 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition duration-1000"
      ></div>
      <div
        class="relative w-24 h-24 bg-slate-900 rounded-2xl flex items-center justify-center shadow-2xl rotate-3 transition-transform group-hover:rotate-0"
      >
        <img :src="logoDarkUrl" :alt="t('聚序智投 Logo')" class="w-full h-full object-cover rounded-2xl select-none" draggable="false" />
      </div>
      <!-- <div class="absolute top-0 right-0 -mr-6 -mt-2 bg-white p-2 rounded-lg shadow-sm animate-pulse-slow">
        <LucideIcon name="BrainCircuit" :size="16" class="text-slate-900" />
      </div>
      <div class="absolute bottom-0 left-0 -ml-6 -mb-2 bg-white p-2 rounded-lg shadow-sm" style="animation-delay: 1s">
        <LucideIcon name="Newspaper" :size="16" class="text-slate-900" />
      </div> -->
    </div>

    <div class="text-center mb-10 max-w-2xl cursor-default">
      <h1 class="text-4xl md:text-5xl font-black text-slate-900 tracking-tight mb-4">
        {{ t("聚序智投") }}
      </h1>
      <p class="text-gray-500 font-medium text-lg leading-relaxed">
        {{ t("在非理性市场中的理性优势") }}
        <br />
        <span class="text-sm text-gray-400 mt-2 block">
          {{ t("既然市场趋于无序，你便需要对抗熵增。聚序智投从混乱市场中分析交易秩序。基于 LLM 的深度金融分析与决策系统。") }}
        </span>
      </p>
    </div>

    <div class="w-full max-w-2xl relative z-20 group mb-12">
      <div
        class="bg-white rounded-2xl p-2 flex items-center shadow-2xl shadow-gray-200/50 ring-1 ring-black/5 transition-all focus-within:ring-2 focus-within:ring-slate-900 focus-within:scale-[1.02]"
      >
        <div class="relative border-r border-gray-100 px-2">
          <UiSelect v-model="market" :options="marketOptions" />
        </div>

        <input
          v-model="stockInput"
          type="text"
          :placeholder="t('输入股票代码 (如 600519)...')"
          class="flex-1 bg-transparent px-6 text-xl font-bold text-slate-900 placeholder:text-gray-300 outline-none h-14 tracking-tight"
          autofocus
          @keydown.enter.prevent="start"
        />

        <button
          type="button"
          class="mr-1 bg-slate-900 hover:bg-black text-white w-14 h-14 rounded-xl shadow-md transition-all flex items-center justify-center active:scale-95"
          @click="start"
        >
          <LucideIcon name="ArrowRight" :size="24" />
        </button>
      </div>

      <div class="mt-4 flex items-center justify-center gap-3">
        <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">{{ t("趋势") }}</span>
        <button
          v-for="code in ['600519', '000001', '300750', '601318']"
          :key="code"
          type="button"
          class="px-3 py-1 bg-white border border-gray-200 rounded-full text-xs font-bold text-gray-500 hover:border-slate-900 hover:text-slate-900 transition-colors shadow-sm"
          @click="startWithCode(code)"
        >
          {{ code }}
        </button>
      </div>
    </div>

    <div v-if="false" class="grid grid-cols-1 md:grid-cols-3 gap-4 w-full max-w-3xl mb-12">
      <div class="bg-white rounded-xl p-4 border border-gray-100 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow">
        <div class="text-xs font-bold text-gray-500">{{ t("上证指数") }}</div>
        <div class="text-right">
          <div class="font-bold font-mono text-slate-900">3,052.14</div>
          <div class="text-[10px] font-bold text-rose-600 font-mono">+0.42%</div>
        </div>
      </div>
      <div class="bg-white rounded-xl p-4 border border-gray-100 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow">
        <div class="text-xs font-bold text-gray-500">{{ t("恒生指数") }}</div>
        <div class="text-right">
          <div class="font-bold font-mono text-slate-900">16,420.8</div>
          <div class="text-[10px] font-bold text-emerald-600 font-mono">-1.20%</div>
        </div>
      </div>
      <div class="bg-white rounded-xl p-4 border border-gray-100 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow">
        <div class="text-xs font-bold text-gray-500">{{ t("纳斯达克") }}</div>
        <div class="text-right">
          <div class="font-bold font-mono text-slate-900">16,200.5</div>
          <div class="text-[10px] font-bold text-rose-600 font-mono">+1.50%</div>
        </div>
      </div>
    </div>

    <div class="w-full max-w-2xl">
      <div class="flex items-center gap-4 mb-4">
        <div class="h-px bg-gray-200 flex-1"></div>
        <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">{{ t("最近活动") }}</span>
        <div class="h-px bg-gray-200 flex-1"></div>
      </div>

      <div class="space-y-2">
        <div
          v-for="task in store.tasks.value.slice(0, 3)"
          :key="task.id"
          class="bg-white border border-gray-100 rounded-lg p-3 flex items-center justify-between cursor-pointer hover:border-slate-300 hover:shadow-sm transition-all group"
          @click="store.openTask(task.id)"
        >
          <div class="flex items-center gap-3">
            <div
              class="w-8 h-8 rounded bg-gray-50 flex items-center justify-center text-xs font-bold font-mono text-slate-600 border border-gray-200 group-hover:bg-slate-900 group-hover:text-white group-hover:border-slate-900 transition-colors"
            >
              {{ task.stockCode.substring(0, 2) }}
            </div>
            <div>
              <div class="flex items-center gap-2">
                <span class="font-bold text-slate-900 text-sm">{{ task.stockCode }}</span>
                <span class="text-[10px] text-gray-400 font-mono">{{ new Date(task.startTime).toLocaleTimeString() }}</span>
              </div>
              <div v-if="task.companyName" class="text-[11px] text-gray-400 font-medium leading-4">
                {{ task.companyName }}
              </div>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <div v-if="task.status === 'analyzing'" class="flex items-center gap-1.5 text-[10px] font-bold text-slate-500">
              <LucideIcon name="Loader2" :size="10" class="animate-spin" />
              {{ t("处理中") }}
            </div>
            <span
              v-else
              :class="[
                'text-[10px] font-bold px-2 py-0.5 rounded border',
                task.result?.recommendation === 'BUY' ? 'bg-white border-slate-200 text-slate-800' : 'bg-gray-50 text-gray-400 border-transparent',
              ]"
            >
              {{ task.result?.recommendation }}
            </span>
            <LucideIcon name="ArrowRight" :size="14" class="text-gray-300 group-hover:text-slate-900" />
          </div>
        </div>

        <div v-if="store.tasks.value.length === 0" class="text-center py-4 text-gray-300 text-xs font-medium">{{ t("等待指令输入...") }}</div>
      </div>
    </div>
  </div>
</template>
