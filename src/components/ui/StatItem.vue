<script setup lang="ts">
/**
 * StatItem：用于 Trading 页的简洁数据展示
 */

const props = defineProps<{
  label: string;
  value: string;
  trend?: string;
  sub?: string;
}>();
</script>

<template>
  <div>
    <div class="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1 font-sans">
      {{ props.label }}
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-2xl font-bold text-slate-900 tracking-tight font-mono">{{ props.value }}</span>
    </div>
    <div class="flex items-center gap-2 mt-0.5">
      <span
        v-if="props.trend"
        :class="[
          'text-xs font-bold font-mono',
          props.trend.startsWith('+') ? 'text-emerald-600' : 'text-rose-600',
        ]"
      >
        {{ props.trend }}
      </span>
      <span v-if="props.sub" class="text-[10px] text-gray-400">{{ props.sub }}</span>
    </div>
  </div>
</template>

