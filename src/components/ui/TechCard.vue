<script setup lang="ts">
/**
 * TechCard：设计稿中的基础容器组件
 *
 * 目标：
 * - 统一“白底 + 细边框 + 圆角 + 阴影”的卡片风格；
 * - 可选支持点击态（hover 边框加深、指针变为可点击）。
 */

withDefaults(
  defineProps<{
    clickable?: boolean;
    active?: boolean;
  }>(),
  {
    clickable: false,
    active: false,
  },
);

const emit = defineEmits<{
  (e: "click"): void;
}>();
</script>

<template>
  <div
    :class="[
      'bg-white border transition-all duration-300 relative overflow-hidden rounded-xl',
      clickable ? 'cursor-pointer hover:border-slate-800 hover:shadow-lg' : 'border-gray-200 shadow-sm',
      active ? 'ring-1 ring-slate-900 border-slate-900' : '',
    ]"
    @click="clickable ? emit('click') : undefined"
  >
    <slot />
  </div>
</template>
