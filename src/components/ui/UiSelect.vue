<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import LucideIcon from "../icons/LucideIcon.vue";

export interface UiSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

/**
 * UiSelect：统一风格的下拉选择组件
 *
 * 为什么不用原生 select：
 * - 原生下拉菜单的弹层样式强依赖系统，容易与当前“单色、锋利、可控”的 UI 语言冲突；
 * - 本组件使用自定义弹层，以便统一圆角、阴影、hover 与选中态表现。
 *
 * 交互说明：
 * - 鼠标：点击展开/收起，点击选项选择并关闭；
 * - 键盘：Enter/Space 展开，↑/↓ 移动高亮，Enter 选择，Esc 关闭；
 * - 点击组件外部会自动关闭弹层。
 */

const props = withDefaults(
  defineProps<{
    modelValue: string;
    options: UiSelectOption[];
    disabled?: boolean;
    placeholder?: string;
  }>(),
  {
    disabled: false,
    placeholder: "请选择",
  },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const rootRef = ref<HTMLElement | null>(null);
const open = ref(false);
const activeIndex = ref(-1);

const selected = computed(() => props.options.find((o) => o.value === props.modelValue) ?? null);

const selectedLabel = computed(() => selected.value?.label ?? props.placeholder);

function close() {
  open.value = false;
  activeIndex.value = -1;
}

function toggle() {
  if (props.disabled) return;
  open.value = !open.value;
}

function selectValue(value: string) {
  emit("update:modelValue", value);
  close();
}

function moveActive(delta: number) {
  if (!open.value) return;
  const enabledOptions = props.options.filter((o) => !o.disabled);
  if (enabledOptions.length === 0) return;

  const currentValue = props.options[activeIndex.value]?.value;
  const currentEnabledIndex = enabledOptions.findIndex((o) => o.value === currentValue);
  const nextEnabledIndex = currentEnabledIndex === -1 ? 0 : (currentEnabledIndex + delta + enabledOptions.length) % enabledOptions.length;
  const nextValue = enabledOptions[nextEnabledIndex]?.value;
  const nextIndex = props.options.findIndex((o) => o.value === nextValue);
  activeIndex.value = nextIndex;
}

function onTriggerKeydown(e: KeyboardEvent) {
  if (props.disabled) return;

  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    toggle();
    return;
  }

  if (!open.value) return;

  if (e.key === "Escape") {
    e.preventDefault();
    close();
    return;
  }

  if (e.key === "ArrowDown") {
    e.preventDefault();
    moveActive(1);
    return;
  }

  if (e.key === "ArrowUp") {
    e.preventDefault();
    moveActive(-1);
    return;
  }

  if (e.key === "Enter") {
    e.preventDefault();
    const opt = props.options[activeIndex.value];
    if (opt && !opt.disabled) selectValue(opt.value);
  }
}

function onOptionMouseEnter(index: number) {
  activeIndex.value = index;
}

function onClickOutside(e: MouseEvent) {
  if (!open.value) return;
  const root = rootRef.value;
  if (!root) return;
  if (root.contains(e.target as Node)) return;
  close();
}

watch(
  () => open.value,
  async (isOpen) => {
    if (!isOpen) return;
    await nextTick();
    const selectedIndex = props.options.findIndex((o) => o.value === props.modelValue && !o.disabled);
    activeIndex.value = selectedIndex >= 0 ? selectedIndex : props.options.findIndex((o) => !o.disabled);
  },
);

onMounted(() => {
  document.addEventListener("mousedown", onClickOutside);
});

onBeforeUnmount(() => {
  document.removeEventListener("mousedown", onClickOutside);
});
</script>

<template>
  <div ref="rootRef" class="relative">
    <button
      type="button"
      class="h-14 pl-4 pr-4 flex items-center gap-2 font-bold text-slate-900 text-sm outline-none select-none rounded-xl transition-colors"
      :class="[
        props.disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:bg-gray-50',
        open ? 'bg-gray-50' : '',
      ]"
      :aria-expanded="open"
      :aria-disabled="props.disabled"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      <span class="whitespace-nowrap">{{ selectedLabel }}</span>
      <LucideIcon
        name="ChevronRight"
        :size="12"
        class="ml-auto text-gray-400 transition-transform"
        :class="open ? '-rotate-90' : 'rotate-90'"
      />
    </button>

    <div
      v-if="open"
      class="absolute left-0 top-full mt-2 w-full min-w-[12rem] bg-white border border-gray-200 rounded-xl shadow-2xl overflow-hidden z-30"
      role="listbox"
    >
      <div class="p-1">
        <button
          v-for="(opt, idx) in props.options"
          :key="opt.value"
          type="button"
          class="relative w-full px-3 py-2 rounded-lg flex items-center justify-between text-left text-sm font-bold transition-colors overflow-hidden"
          :class="[
            opt.disabled ? 'cursor-not-allowed text-slate-400' : 'cursor-pointer',
            idx === activeIndex
              ? opt.disabled
                ? 'bg-white'
                : 'bg-gray-50 text-slate-900'
              : opt.disabled
                ? 'bg-white'
                : 'text-slate-700 hover:bg-gray-50 hover:text-slate-900',
          ]"
          role="option"
          :aria-selected="opt.value === props.modelValue"
          :aria-disabled="opt.disabled"
          @mouseenter="onOptionMouseEnter(idx)"
          @click="opt.disabled ? undefined : selectValue(opt.value)"
        >
          <span class="truncate">{{ opt.label }}</span>
          <LucideIcon v-if="opt.value === props.modelValue" name="Check" :size="16" class="text-slate-900" />
          <div
            v-if="opt.disabled && idx === activeIndex"
            class="absolute inset-0 bg-white/60 backdrop-blur-sm flex items-center justify-center gap-2 text-slate-700"
          >
            <LucideIcon name="Lock" :size="14" class="text-slate-700" />
            <span class="text-[11px] font-bold">{{ "暂不可用" }}</span>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>
