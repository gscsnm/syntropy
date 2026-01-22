<script setup lang="ts">
import { ref, onMounted, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { pyInvoke } from "tauri-plugin-pytauri-api";
import { getLlmConfig, saveLlmConfig } from "../../client/apiClient";
import LucideIcon from "../icons/LucideIcon.vue";
import type { LLMConfig } from "../../client/_apiTypes.d.ts";
import UiSelect, { type UiSelectOption } from "../ui/UiSelect.vue";
import FollowMeCard from "../ui/FollowMeCard.vue";

const props = defineProps<{
  show: boolean;
}>();

const emit = defineEmits(["close"]);

const { t, locale } = useI18n();

const loading = ref(false);
const applying = ref(false);
const applied = ref(false);

const providerBaseUrl = {
  bailian: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  volcengine: "https://ark.cn-beijing.volces.com/api/v3",
  deepseek: "https://api.deepseek.com/v1",
} as const;

type ProviderKey = keyof typeof providerBaseUrl;

function isProviderKey(v: unknown): v is ProviderKey {
  return typeof v === "string" && v in providerBaseUrl;
}

function ensureProviderBaseUrl(config: LLMConfig) {
  const provider = config.provider;
  if (!isProviderKey(provider)) {
    config.provider = "bailian";
    config.api_base = providerBaseUrl.bailian;
    return;
  }
  config.api_base = providerBaseUrl[provider];
}

const fastConfig = ref<LLMConfig>({
  name: t("快速模型配置"),
  provider: "bailian",
  api_key: "",
  api_base: providerBaseUrl.bailian,
  model_name: "gpt-4o-mini",
  temperature: 0.3,
  role: "fast",
});

const slowConfig = ref<LLMConfig>({
  name: t("慢速模型配置"),
  provider: "bailian",
  api_key: "",
  api_base: providerBaseUrl.bailian,
  model_name: "gpt-4o",
  temperature: 0.3,
  role: "slow",
});

const selectedLanguage = ref<string>("en-US");


const providerOptions = computed<UiSelectOption[]>(() => [
  { label: t("阿里百炼"), value: "bailian" },
  { label: t("豆包（火山引擎）"), value: "volcengine" },
  { label: t("DeepSeek"), value: "deepseek" },
]);

const languageOptions = computed<UiSelectOption[]>(() => [
  { label: t("中文"), value: "zh-CN" },
  { label: t("English"), value: "en-US" },
]);

const fetchSettings = async () => {
  loading.value = true;
  try {
    const data = await getLlmConfig();
    if (data.fast) fastConfig.value = { ...data.fast, role: "fast" };
    if (data.slow) slowConfig.value = { ...data.slow, role: "slow" };
    ensureProviderBaseUrl(fastConfig.value);
    ensureProviderBaseUrl(slowConfig.value);
    const langResp = await pyInvoke("get_app_language");
    if (langResp && (langResp as any).language) {
      selectedLanguage.value = (langResp as any).language;
      locale.value = selectedLanguage.value;
    }
  } finally {
    loading.value = false;
  }
};

async function applySettings() {
  applying.value = true;
  applied.value = false;
  try {
    ensureProviderBaseUrl(fastConfig.value);
    ensureProviderBaseUrl(slowConfig.value);
    await saveLlmConfig(fastConfig.value);
    await saveLlmConfig(slowConfig.value);
    await pyInvoke("set_app_language", { language: selectedLanguage.value });
    locale.value = selectedLanguage.value;
    await fetchSettings();
    applied.value = true;
  } finally {
    applying.value = false;
    setTimeout(() => {
      applied.value = false;
    }, 1200);
  }
}

onMounted(() => {
  if (props.show) {
    void fetchSettings();
  }
});

watch(() => props.show, (v) => {
  if (v) {
    void fetchSettings();
  }
});

watch(selectedLanguage, (v) => {
  locale.value = v;
});

watch(() => fastConfig.value.provider, () => {
  ensureProviderBaseUrl(fastConfig.value);
});

watch(() => slowConfig.value.provider, () => {
  ensureProviderBaseUrl(slowConfig.value);
});
</script>

<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm select-none">
    <div class="bg-white rounded-xl w-[900px] h-[600px] shadow-2xl flex overflow-hidden">
      <div class="flex-1 flex flex-col bg-white">
        <div class="p-6 border-b border-slate-100 bg-slate-50/50">
          <div class="flex justify-between items-start">
            <div>
              <h3 class="text-lg font-bold text-slate-900">{{ t("设置") }}</h3>
              <p class="text-xs text-slate-500">{{ t("仅需配置两个模型：快速与慢速") }}</p>
              <p class="text-xs text-slate-500 mt-1">{{ t("需要使用支持思考模式切换、能进行工具调用的模型，快速模型需要支持结构化输出。") }}</p>
            </div>
            <div class="flex items-center gap-3">
              <UiSelect
                v-model="selectedLanguage"
                :options="languageOptions"
                :placeholder="t('请选择')"
              />
              <button
                @click="applySettings"
                :disabled="applying"
                class="px-3 py-1.5 bg-slate-900 text-white text-xs rounded hover:bg-black disabled:opacity-50 flex items-center gap-2"
              >
                <LucideIcon
                  v-if="applying"
                  name="LoaderCircle"
                  :size="16"
                  class="animate-spin"
                />
                <LucideIcon
                  v-else-if="applied"
                  name="Check"
                  :size="16"
                />
                <span>
                  {{ applying ? t("应用中…") : (applied ? t("已应用") : t("应用设置")) }}
                </span>
              </button>
              <button @click="$emit('close')" class="text-slate-400 hover:text-slate-600">
                <LucideIcon name="X" :size="20" />
              </button>
            </div>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-6 space-y-6">
          <FollowMeCard />

          <div class="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <LucideIcon name="Zap" :size="16" />
                <div class="font-bold text-slate-800">{{ t("快速模型配置") }}</div>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("服务商") }}</label>
                <UiSelect v-model="fastConfig.provider" :options="providerOptions" :placeholder="t('请选择')" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("模型名称") }}</label>
                <input v-model="fastConfig.model_name" type="text" placeholder="qwen-plus" class="w-full p-2 text-sm border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none font-mono select-text" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("温度") }}</label>
                <input v-model.number="fastConfig.temperature" type="number" step="0.1" min="0" max="2" class="w-full p-2 text-sm border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none select-text" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("API Key") }}</label>
                <input v-model="fastConfig.api_key" type="password" class="w-full p-2 text-sm border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none font-mono select-text" />
              </div>
            </div>
          </div>

          <div class="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <LucideIcon name="BrainCircuit" :size="16" />
                <div class="font-bold text-slate-800">{{ t("慢速模型配置") }}</div>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("服务商") }}</label>
                <UiSelect v-model="slowConfig.provider" :options="providerOptions" :placeholder="t('请选择')" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("模型名称") }}</label>
                <input v-model="slowConfig.model_name" type="text" placeholder="qwen-plus" class="w-full p-2 text-sm border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none font-mono select-text" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("温度") }}</label>
                <input v-model.number="slowConfig.temperature" type="number" step="0.1" min="0" max="2" class="w-full p-2 text-sm border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none select-text" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("API Key") }}</label>
                <input v-model="slowConfig.api_key" type="password" class="w-full p-2 text-sm border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none font-mono select-text" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
