<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import LucideIcon from "../icons/LucideIcon.vue";
import FollowMeCard from "../ui/FollowMeCard.vue";

const props = defineProps<{
  show: boolean;
  info: {
    version: string;
    currentVersion: string;
    date?: string;
    body?: string;
  } | null;
  installing: boolean;
  installed: boolean;
  error: string | null;
  progressPercent: number | null;
}>();

defineEmits<{
  (e: "update"): void;
  (e: "retry"): void;
}>();

const { t } = useI18n();

const headerText = computed(() => {
  if (props.installed) return t("更新已安装，请重启应用");
  if (props.installing) return t("正在更新…");
  return t("检查到有新版本，请先完成版本更新");
});
</script>

<template>
  <div v-if="show" class="fixed inset-0 z-[1100] flex items-center justify-center bg-black/70 backdrop-blur-sm select-none">
    <div class="bg-white rounded-xl w-[820px] h-[560px] shadow-2xl flex overflow-hidden">
      <div class="flex-1 flex flex-col bg-white">
        <div class="p-6 border-b border-slate-100 bg-slate-50/50">
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0">
              <h3 class="text-lg font-bold text-slate-900">{{ t("强制更新") }}</h3>
              <p class="text-xs text-slate-600 mt-1">{{ headerText }}</p>
              <p v-if="info" class="text-[11px] text-slate-500 mt-2">
                {{ t("新版本") }} {{ info.version }} · {{ t("当前版本") }} {{ info.currentVersion }}
              </p>
            </div>
            <div class="flex items-center gap-2">
              <span
                v-if="installed"
                class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-800 text-xs font-bold"
              >
                <LucideIcon name="Check" :size="16" />
                {{ t("已安装") }}
              </span>
              <span
                v-else-if="installing"
                class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 text-white text-xs font-bold"
              >
                <LucideIcon name="LoaderCircle" :size="16" class="animate-spin" />
                {{ t("更新中") }}
              </span>
            </div>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-6 space-y-4 select-text">
          <div v-if="error" class="rounded-lg border border-rose-200 bg-rose-50 p-4">
            <div class="text-xs font-bold text-rose-700">{{ t("更新失败") }}</div>
            <div class="mt-2 text-xs text-rose-700 break-words">{{ error }}</div>
          </div>

          <div v-if="info?.body" class="rounded-lg border border-slate-200 bg-white p-4">
            <div class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{{ t("更新说明") }}</div>
            <div class="mt-2 text-xs text-slate-700 whitespace-pre-wrap max-h-72 overflow-auto rounded border border-slate-100 bg-slate-50 p-3">
              {{ info.body }}
            </div>
          </div>

          <div v-if="installing" class="rounded-lg border border-slate-200 bg-white p-4">
            <div class="w-full h-2 bg-slate-100 rounded overflow-hidden">
              <div class="h-2 bg-slate-900" :style="{ width: `${progressPercent ?? 20}%` }" />
            </div>
            <div class="mt-2 text-[11px] font-semibold text-slate-500">
              <span v-if="progressPercent != null">{{ progressPercent }}%</span>
              <span v-else>{{ t("下载中…") }}</span>
            </div>
          </div>

          <div v-if="installed" class="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <div class="text-xs font-bold text-emerald-800">{{ t("更新已安装") }}</div>
            <div class="mt-2 text-xs text-emerald-800">{{ t("请关闭并重新打开应用以完成更新") }}</div>
          </div>

          <FollowMeCard />
        </div>

        <div class="p-6 border-t border-slate-100 bg-slate-50/50 flex items-center justify-end gap-3">
          <button
            v-if="error && !installing && !installed"
            type="button"
            class="px-3 py-1.5 text-xs font-bold bg-white border border-gray-200 rounded text-slate-600 hover:border-slate-900 hover:text-slate-900 disabled:opacity-50 flex items-center gap-2"
            @click="$emit('retry')"
          >
            <LucideIcon name="RefreshCw" :size="16" />
            {{ t("重试") }}
          </button>
          <button
            type="button"
            class="px-3 py-1.5 text-xs font-bold rounded bg-slate-900 text-white hover:bg-black disabled:opacity-50 flex items-center gap-2"
            :disabled="installing || installed"
            @click="$emit('update')"
          >
            <LucideIcon v-if="installing" name="LoaderCircle" :size="16" class="animate-spin" />
            <LucideIcon v-else name="ArrowDownToLine" :size="16" />
            {{ installed ? t("已安装") : (installing ? t("更新中…") : t("立即更新")) }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
