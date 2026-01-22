<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import LucideIcon from "../icons/LucideIcon.vue";
import saibogongjiangAvatar from "../../assets/saibogongjiang.png";

const { t } = useI18n();

const douyinName = "赛博工匠";
const douyinId = "49498926981";
const copyingFollowInfo = ref(false);
const copiedFollowInfo = ref(false);

async function copyText(text: string) {
  const clipboard = (navigator as any)?.clipboard;
  if (clipboard?.writeText) {
    await clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "0";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

async function copyDouyinId() {
  if (copyingFollowInfo.value) return;
  copyingFollowInfo.value = true;
  copiedFollowInfo.value = false;
  try {
    await copyText(douyinId);
    copiedFollowInfo.value = true;
  } finally {
    copyingFollowInfo.value = false;
    window.setTimeout(() => {
      copiedFollowInfo.value = false;
    }, 1200);
  }
}
</script>

<template>
  <div class="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <LucideIcon name="Sparkles" :size="16" />
        <div class="font-bold text-slate-800">{{ t("关注我") }}</div>
      </div>
      <div class="flex items-center gap-2 select-text">
        <button
          type="button"
          class="px-3 py-1.5 text-xs font-bold bg-white border border-gray-200 rounded text-slate-600 hover:border-slate-900 hover:text-slate-900 disabled:opacity-50 flex items-center gap-2"
          :disabled="copyingFollowInfo"
          @click="copyDouyinId"
        >
          <LucideIcon v-if="copiedFollowInfo" name="Check" :size="16" />
          <LucideIcon v-else name="FileText" :size="16" />
          {{ copiedFollowInfo ? t("已复制") : t("复制抖音号") }}
        </button>
      </div>
    </div>

    <div class="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4 select-text">
      <div class="flex items-start justify-between gap-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl overflow-hidden bg-slate-900 ring-1 ring-slate-900/10 select-none">
            <img :src="saibogongjiangAvatar" :alt="douyinName" class="w-full h-full object-cover" />
          </div>
          <div class="min-w-0">
            <div class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{{ t("抖音") }}</div>
            <div class="mt-1 text-sm font-black text-slate-900 truncate">{{ douyinName }}</div>
            <div class="mt-1 text-xs text-slate-600">
              {{ t("抖音号") }}：
              <span class="inline-flex items-center font-mono font-bold text-slate-900 px-2 py-0.5 rounded bg-white border border-slate-200">
                {{ douyinId }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="mt-3 text-[11px] font-semibold text-slate-500">
        {{ t("在抖音搜索抖音号即可找到我") }}
      </div>
      <div class="mt-2 text-[11px] font-semibold text-slate-500">
        {{ t("如需商用/团队部署/接入商用数据源或私有数据源/定制开发，请联系（微信：xxg-2077），微信请备注来意") }}
      </div>
    </div>
  </div>
</template>
