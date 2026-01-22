<script setup lang="ts">
import { useRouter } from "vue-router";

/**
 * NotFoundPage：兜底页面
 *
 * 说明：
 * - 设计稿没有 404，这里只提供一个简单返回入口，避免误入空白页。
 */

const router = useRouter();
</script>

<template>
  <div class="h-full flex items-center justify-center p-10">
    <div class="bg-white border border-gray-200 rounded-xl p-8 text-center shadow-sm">
      <div class="text-xl font-bold text-slate-900">页面不存在</div>
      <div class="text-sm text-gray-400 mt-2">该路径未匹配到任何页面路由。</div>
      <button
        type="button"
        class="mt-6 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-bold hover:bg-black transition-colors"
        @click="router.replace('/analysis')"
      >
        返回首页
      </button>
    </div>
  </div>
</template>

