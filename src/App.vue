<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, markRaw, shallowRef } from "vue";
import { RouterView } from "vue-router";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import BottomDock from "./components/nav/BottomDock.vue";
import LiveStreamModal from "./components/task/LiveStreamModal.vue";
import SettingsModal from "./components/settings/SettingsModal.vue";
import ForceUpdateModal from "./components/update/ForceUpdateModal.vue";
import LucideIcon from "./components/icons/LucideIcon.vue";
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";

const showSettings = ref(false);
const showDisclaimer = ref(false);
const disclaimerAccepted = ref(false);
const canAgreeDisclaimer = ref(false);
const disclaimerScrollRef = ref<HTMLDivElement | null>(null);
const route = useRoute();
const { t } = useI18n();

const scrollEnabled = computed(() => route.name !== "analysis");

const UPDATE_CHECK_INTERVAL_MS = 30 * 60 * 1000;
let updateCheckTimerId: number | null = null;
let updateChecking = false;
const showForceUpdate = ref(false);
const updateInfo = ref<{
  version: string;
  currentVersion: string;
  date?: string;
  body?: string;
} | null>(null);
const pendingUpdate = shallowRef<any | null>(null);
const updateError = ref<string | null>(null);
const updateInstalling = ref(false);
const updateInstalled = ref(false);
const updateDownloadedBytes = ref(0);
const updateTotalBytes = ref<number | null>(null);

const updateProgressPercent = computed(() => {
  const total = updateTotalBytes.value;
  if (!total || total <= 0) return null;
  return Math.max(0, Math.min(100, Math.floor((updateDownloadedBytes.value / total) * 100)));
});

const DISCLAIMER_STORAGE_KEY = "syntropy_disclaimer_accepted_v1";
let disclaimerReadingUnlockTimerId: number | null = null;

function getDisclaimerAcceptedFromStorage() {
  try {
    return window.localStorage.getItem(DISCLAIMER_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function setDisclaimerAcceptedToStorage() {
  try {
    window.localStorage.setItem(DISCLAIMER_STORAGE_KEY, "1");
  } catch {
  }
}

function acceptDisclaimer() {
  disclaimerAccepted.value = true;
  setDisclaimerAcceptedToStorage();
  showDisclaimer.value = false;
}

function onDisclaimerScroll() {
  const el = disclaimerScrollRef.value;
  if (!el) return;
  const near = el.scrollHeight - (el.scrollTop + el.clientHeight) <= 12;
  canAgreeDisclaimer.value = near;
}

function resetDisclaimerReadingState() {
  canAgreeDisclaimer.value = false;
  const el = disclaimerScrollRef.value;
  if (disclaimerReadingUnlockTimerId != null) {
    window.clearTimeout(disclaimerReadingUnlockTimerId);
    disclaimerReadingUnlockTimerId = null;
  }
  if (!el) {
    disclaimerReadingUnlockTimerId = window.setTimeout(() => {
      canAgreeDisclaimer.value = true;
    }, 3000);
    return;
  }
  const scrollable = el.scrollHeight > el.clientHeight + 8;
  if (!scrollable) {
    disclaimerReadingUnlockTimerId = window.setTimeout(() => {
      canAgreeDisclaimer.value = true;
    }, 3000);
  } else {
    onDisclaimerScroll();
  }
}

async function checkUpdateOnce() {
  if (showForceUpdate.value || pendingUpdate.value || updateInstalling.value) return;
  if (updateChecking) return;
  updateChecking = true;
  try {
    const update = await check({ timeout: 8000 });
    if (!update) return;

    pendingUpdate.value = markRaw(update);
    updateInfo.value = {
      version: String(update.version),
      currentVersion: String(update.currentVersion),
      date: update.date ? String(update.date) : undefined,
      body: update.body ? String(update.body) : undefined,
    };
    showForceUpdate.value = true;
    showSettings.value = false;
    if (updateCheckTimerId != null) {
      window.clearInterval(updateCheckTimerId);
      updateCheckTimerId = null;
    }
  } catch {
  } finally {
    updateChecking = false;
  }
}

async function retryCheckUpdate() {
  if (updateInstalling.value) return;
  updateError.value = null;
  updateInstalled.value = false;
  updateDownloadedBytes.value = 0;
  updateTotalBytes.value = null;

  if (pendingUpdate.value?.close) {
    try {
      await pendingUpdate.value.close();
    } catch {
    }
  }
  pendingUpdate.value = null;
  updateInfo.value = null;

  updateChecking = false;
  await checkUpdateOnce();
}

async function downloadAndInstallForcedUpdate() {
  if (updateInstalling.value) return;
  updateError.value = null;
  updateInstalled.value = false;
  updateDownloadedBytes.value = 0;
  updateTotalBytes.value = null;

  if (!pendingUpdate.value) {
    try {
      const update = await check({ timeout: 15000 });
      if (!update) {
        updateError.value = t("未找到可用更新");
        return;
      }
      pendingUpdate.value = markRaw(update);
      updateInfo.value = {
        version: String(update.version),
        currentVersion: String(update.currentVersion),
        date: update.date ? String(update.date) : undefined,
        body: update.body ? String(update.body) : undefined,
      };
    } catch (e) {
      updateError.value = String((e as any)?.message ?? e);
      return;
    }
  }

  const update = pendingUpdate.value;
  if (!update) return;

  updateInstalling.value = true;
  try {
    await update.downloadAndInstall((event: any) => {
      if (event?.event === "Started") {
        const len = Number(event?.data?.contentLength);
        updateTotalBytes.value = Number.isFinite(len) && len > 0 ? len : null;
        updateDownloadedBytes.value = 0;
      } else if (event?.event === "Progress") {
        const chunk = Number(event?.data?.chunkLength ?? 0);
        if (Number.isFinite(chunk) && chunk > 0) updateDownloadedBytes.value += chunk;
      }
    });
    updateInstalled.value = true;
    try {
      await relaunch();
    } catch {
    }
  } catch (e) {
    updateError.value = String((e as any)?.message ?? e);
  } finally {
    updateInstalling.value = false;
    if (pendingUpdate.value?.close) {
      try {
        await pendingUpdate.value.close();
      } catch {
      }
    }
    pendingUpdate.value = null;
  }
}

/**
 * App：全局应用壳
 *
 * 职责：
 * - 布局：顶部 Header + 中间路由内容 + 底部 Dock；
 * - 全局弹窗：统一挂载 LiveStream（沉浸式分析视图）。
 *
 * 维护建议：
 * - 业务页面请放在 `src/pages/*` 并通过 `src/router/index.ts` 注册路由；
 * - 共享状态目前使用 `src/stores/alphaMindStore.ts`（模块级 ref）。
 */

onMounted(() => {
  disclaimerAccepted.value = getDisclaimerAcceptedFromStorage();
  if (!disclaimerAccepted.value) {
    showDisclaimer.value = true;
    window.setTimeout(() => {
      resetDisclaimerReadingState();
    }, 0);
  }
  void checkUpdateOnce();
  updateCheckTimerId = window.setInterval(() => {
    void checkUpdateOnce();
  }, UPDATE_CHECK_INTERVAL_MS);
});

onBeforeUnmount(() => {
  if (updateCheckTimerId != null) {
    window.clearInterval(updateCheckTimerId);
    updateCheckTimerId = null;
  }
  if (pendingUpdate.value?.close) {
    void pendingUpdate.value.close();
    pendingUpdate.value = null;
  }
  if (disclaimerReadingUnlockTimerId != null) {
    window.clearTimeout(disclaimerReadingUnlockTimerId);
    disclaimerReadingUnlockTimerId = null;
  }
});
</script>

<template>
  <div class="flex h-screen w-screen font-sans relative text-slate-900 bg-[#F4F5F7] selection:bg-slate-900 selection:text-white">
    <div class="fixed inset-x-0 top-0 z-[999] h-6 flex select-none">
      <div data-tauri-drag-region class="h-full flex-1"></div>
      <div class="h-full w-28 pointer-events-none"></div>
    </div>
    <BottomDock />

    <main class="relative z-10 w-full h-full flex flex-col overflow-hidden">
      <header data-tauri-drag-region class="h-18 pt-8 flex items-center justify-between px-8 absolute top-0 w-full z-20 select-none">
        <div class="pointer-events-auto flex items-center gap-2">
          <button
            type="button"
            data-tauri-drag-region="false"
            class="h-8 px-3 rounded-full bg-white flex items-center justify-center gap-2 text-slate-900 shadow-sm hover:bg-slate-900 hover:text-white transition-colors"
            @click="showDisclaimer = true"
          >
            <LucideIcon name="ShieldAlert" :size="14" />
            <span class="text-[11px] font-bold">{{ t("免责声明") }}</span>
          </button>
        </div>

        <div class="flex items-center gap-6 pointer-events-auto">
          <div v-if="false" class="flex gap-4 text-[10px] font-bold tracking-widest text-gray-400">
            <span>USD/CNY <span class="text-slate-900">7.24</span></span>
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              @click="showSettings = true"
              data-tauri-drag-region="false"
              class="w-8 h-8 rounded-full bg-white flex items-center justify-center text-slate-900 shadow-sm hover:bg-slate-900 hover:text-white transition-colors"
            >
              <LucideIcon name="Settings" :size="14" />
            </button>
          </div>
        </div>
      </header>

      <div :class="['flex-1 min-h-0 pt-16 native-page', scrollEnabled ? 'overflow-auto' : 'overflow-hidden']">
        <RouterView />
      </div>
    </main>

    <div v-if="showDisclaimer" class="fixed inset-0 z-[1000] flex items-center justify-center bg-black/60 backdrop-blur-sm select-none">
      <div class="bg-white rounded-xl w-[900px] h-[640px] shadow-2xl flex overflow-hidden">
        <div class="flex-1 flex flex-col bg-white">
          <div class="p-6 border-b border-slate-100 bg-slate-50/50">
            <div class="flex items-start justify-between gap-4">
              <div>
                <h3 class="text-lg font-bold text-slate-900">{{ t("重要声明与用户责任确认书") }}</h3>
              </div>
              <button
                v-if="disclaimerAccepted"
                type="button"
                data-tauri-drag-region="false"
                class="text-slate-400 hover:text-slate-600"
                @click="showDisclaimer = false"
              >
                <LucideIcon name="X" :size="20" />
              </button>
            </div>
          </div>

          <div ref="disclaimerScrollRef" class="flex-1 overflow-y-auto p-6 select-text" @scroll="onDisclaimerScroll">
            <div class="text-xs text-slate-700 leading-6 space-y-4 max-w-[820px]">
              <p>欢迎使用本工具。本工具完全在您的本地设备运行，用于整合公开数据获取流程并对数据进行可视化与基于大模型（LLM）的辅助分析。继续使用即视为您已理解并接受以下条款。</p>

              <p class="font-bold">工具定位与边界：本工具不提供、存储或分发任何金融数据；不构成任何金融服务或建议。</p>
              <p class="font-bold">用户责任：您是数据获取、处理、使用与分析的唯一责任主体；因使用本工具产生的一切后果与法律责任由您自行承担。</p>
              <p class="font-bold">访问边界：您只能获取您依法有权访问与使用的数据，不得访问、处理或尝试获取任何受限/私有数据。</p>

              <p>公开数据来源：本工具仅以自动化方式获取您设备上可公开访问的数据源信息，不提供或分发数据本体，也不具备访问受限/私有数据的能力。</p>
              <p>公开数据抓取合规：请遵守所有适用法律法规及数据源条款（例如服务条款、robots.txt、访问频率限制、反爬策略、知识产权与地域监管、授权/许可等）。不合规的自动化访问/抓取可能导致账号限制、IP 封禁、服务中断、索赔或其他风险。</p>
              <p class="font-bold">禁止规避：您不得使用本工具绕过或规避任何访问控制、登录要求、付费墙、验证码、反爬策略或其他技术保护措施；本工具不提供亦不支持任何规避上述措施的能力或指导。</p>
              <p class="font-bold">授权与停止使用：如数据源要求授权/许可或明确禁止自动化访问，您应在使用前自行取得合法授权；若无法取得或存在不确定性，您应立即停止使用相关功能。</p>

              <p>数据准确性与适用性：我们不对数据的准确性、完整性、实时性或适用性作任何保证；您基于数据或分析结果的决策及后果由您自行承担。</p>
              <p>可用性不保证：任何数据源策略变更、限流、封禁、接口变动或不可抗力导致的不可用，我们不承担恢复义务或任何责任。</p>

              <p>LLM 输出局限：模型可能出现幻觉、过时信息、偏差或逻辑错误；输出仅为自动化信息整理与辅助解读，不应视为事实或专业结论。</p>

              <p class="font-bold">非投资建议：本工具任何报告、图表、摘要或观点均不构成投资建议、交易推荐、财务/税务/法律意见、市场预测或要约邀约。请独立研究并在必要时咨询持牌专业人士。</p>

              <p class="font-bold">责任豁免：在法律允许范围内，因您使用本工具（包括公开数据获取/抓取、对输出的依赖、第三方服务中断、模型错误、系统故障等）导致的任何直接或间接损失、纠纷或损害，开发者及相关方不承担任何责任。</p>
              <p class="font-bold">第三方索赔与追责：如因您的使用行为引发任何第三方投诉、索赔、行政调查或诉讼，您应自行承担全部责任并妥善解决；开发者及相关方不承担任何责任。</p>

              <p>隐私与本地运行：默认不收集、存储或上传您的个人信息、API 密钥或分析内容。若配置第三方模型/服务或访问第三方数据源，其条款与风险由您自行评估与承担。</p>

              <p class="font-bold">使用范围：仅供个人研究学习，不能用于生产交易或商业场景。若计划商业使用、团队部署，需定制化开发/集成服务，请通过设置页的“关注我”获取联系信息。</p>
              <p>权利通知：如您认为本工具的使用方式或相关内容存在侵权，或您的合法权益可能受到影响，请通过设置页的“关注我”与我们联系，我们将尽快核实并处理。</p>
            </div>
          </div>

          <div class="p-6 border-t border-slate-100 bg-slate-50/50 flex items-center justify-end gap-3">
            <button
              v-if="disclaimerAccepted"
              type="button"
              data-tauri-drag-region="false"
              class="px-3 py-1.5 text-xs font-bold bg-white border border-gray-200 rounded text-slate-600 hover:border-slate-900 hover:text-slate-900"
              @click="showDisclaimer = false"
            >
              {{ t("关闭") }}
            </button>
            <button
              v-else
              type="button"
              data-tauri-drag-region="false"
              class="px-3 py-1.5 text-xs font-bold rounded"
              :class="[canAgreeDisclaimer ? 'bg-slate-900 text-white hover:bg-black' : 'bg-slate-300 text-white cursor-not-allowed opacity-70']"
              :disabled="!canAgreeDisclaimer"
              @click="acceptDisclaimer"
            >
              {{ t("我已阅读并同意") }}
            </button>
            <span v-if="!disclaimerAccepted && !canAgreeDisclaimer" class="text-[11px] text-slate-500">
              {{ t("请滚动阅读完整文本后才可同意") }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <LiveStreamModal />
    <SettingsModal :show="showSettings" @close="showSettings = false" />
    <ForceUpdateModal
      :show="showForceUpdate"
      :info="updateInfo"
      :installing="updateInstalling"
      :installed="updateInstalled"
      :error="updateError"
      :progress-percent="updateProgressPercent"
      @update="downloadAndInstallForcedUpdate"
      @retry="retryCheckUpdate"
    />
  </div>
</template>
