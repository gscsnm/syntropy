<script setup lang="ts">
import { onMounted } from "vue";
import LucideIcon from "../components/icons/LucideIcon.vue";
import { useAlphaMindStore } from "../stores/alphaMindStore";
import { useI18n } from "vue-i18n";

/**
 * HistoryPage：档案数据库（来自设计稿 history Tab）
 */

const store = useAlphaMindStore();
const { t } = useI18n();

onMounted(() => {
  void store.refreshTasks();
});
</script>

<template>
  <div class="max-w-5xl mx-auto p-8 animate-fade-in h-full flex flex-col overflow-hidden">
    <div class="flex items-center justify-between mb-8 shrink-0">
      <h2 class="text-xl font-bold text-slate-900 tracking-tight">{{ t("档案数据库") }}</h2>
      <div class="flex gap-2">
        <button type="button" class="px-3 py-1.5 text-xs font-bold bg-white border border-gray-200 rounded text-slate-600 hover:border-slate-900 hover:text-slate-900">
          {{ t("导出数据") }}
        </button>
      </div>
    </div>

    <div class="bg-white border border-gray-200 rounded-xl shadow-sm flex-1 min-h-0 overflow-hidden">
      <div class="h-full overflow-auto">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-gray-50 border-b border-gray-200 text-xs font-bold text-gray-500 uppercase tracking-wider">
              <th class="px-6 py-4 sticky top-0 z-10 bg-gray-50">{{ t("参考编号") }}</th>
              <th class="px-6 py-4 sticky top-0 z-10 bg-gray-50">{{ t("代码") }}</th>
              <th class="px-6 py-4 sticky top-0 z-10 bg-gray-50">{{ t("市场") }}</th>
              <th class="px-6 py-4 sticky top-0 z-10 bg-gray-50">{{ t("日期") }}</th>
              <th class="px-6 py-4 sticky top-0 z-10 bg-gray-50">{{ t("信号") }}</th>
              <th class="px-6 py-4 text-right sticky top-0 z-10 bg-gray-50"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr
              v-for="task in store.tasks.value"
              :key="task.id"
              class="hover:bg-gray-50 transition-colors group cursor-pointer"
              @click="store.openTask(task.id)"
            >
              <td class="px-6 py-4 text-xs font-mono text-gray-400">#{{ task.id.substring(Math.max(0, task.id.length - 6)) }}</td>
              <td class="px-6 py-4">
                <div class="font-bold text-slate-900">{{ task.stockCode }}</div>
                <div v-if="task.companyName" class="text-xs text-gray-400 font-medium leading-4 mt-1">
                  {{ task.companyName }}
                </div>
              </td>
              <td class="px-6 py-4 text-xs font-bold text-gray-500">{{ task.market }}</td>
              <td class="px-6 py-4 text-xs font-mono text-gray-500">{{ new Date(task.startTime).toLocaleDateString() }}</td>
              <td class="px-6 py-4">
                <span
                  v-if="task.result"
                  :class="[
                    'text-[10px] font-bold px-2 py-0.5 rounded border',
                    task.result.recommendation === 'BUY' ? 'text-slate-900 border-slate-300 bg-white' : 'text-gray-400 border-gray-200 bg-gray-50',
                  ]"
                >
                  {{ task.result.recommendation }}
                </span>
                <span v-else class="text-xs text-gray-400">...</span>
              </td>
              <td class="px-6 py-4 text-right">
                <LucideIcon name="ChevronRight" :size="16" class="text-gray-300 group-hover:text-slate-900 inline-block" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
