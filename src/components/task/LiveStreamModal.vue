<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import LiveStream from "./LiveStream.vue";
import { useAlphaMindStore } from "../../stores/alphaMindStore";

/**
 * LiveStreamModal：全局沉浸式弹窗容器
 *
 * 责任边界：
 * - 仅负责“遮罩层 + 容器尺寸 + 关闭行为 + 交易跳转”
 * - 具体流式展示逻辑由 `LiveStream` 处理
 */

const router = useRouter();
const store = useAlphaMindStore();

const task = computed(() => store.viewingTask.value);

function close() {
  store.closeTask();
}

function goTrade() {
  // 设计稿逻辑：从弹窗里点击“执行交易”后切到 Trading 页面，并关闭弹窗
  store.closeTask();
  void router.push("/trading");
}
</script>

<template>
  <div
    v-if="task"
    class="fixed inset-0 z-[70] flex items-center justify-center bg-[#0f172a]/80 backdrop-blur-sm animate-fade-in p-0 md:p-6"
  >
    <div class="bg-[#FAFAFA] w-full h-full max-w-7xl md:rounded-2xl overflow-hidden shadow-2xl relative flex flex-col ring-1 ring-white/20">
      <LiveStream :task="task" :immersive="false" :show-close="true" @close="close" @trade="goTrade" />
    </div>
  </div>
</template>
