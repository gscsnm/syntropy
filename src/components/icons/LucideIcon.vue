<script setup lang="ts">
import { computed } from "vue";
import {
  Activity,
  ArrowRight,
  BrainCircuit,
  Check,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  CornerUpLeft,
  Cpu,
  FileText,
  Layers,
  LineChart,
  Loader2,
  Lock,
  Newspaper,
  Play,
  Plus,
  Sparkles,
  Settings,
  ShieldAlert,
  Terminal,
  Trash2,
  Wallet,
  X,
  Zap,
  ArrowDownToLine,
  LoaderCircle,
  RefreshCw,
  Download
} from "lucide-vue-next";

/**
 * LucideIcon：统一的图标入口
 *
 * 背景：
 * - 设计稿中（React）通过字符串来选择不同的图标组件；
 * - Vue 下同样支持动态组件，但需要一层“字符串 -> 组件”的映射。
 */

const props = withDefaults(
  defineProps<{
    name: string;
    size?: number;
    strokeWidth?: number;
    class?: string;
  }>(),
  {
    size: 16,
    strokeWidth: 2,
    class: "",
  },
);

const ICONS: Record<string, any> = {
  Activity,
  ArrowRight,
  BrainCircuit,
  Check,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  CornerUpLeft,
  Cpu,
  FileText,
  Layers,
  LineChart,
  Loader2,
  Lock,
  Newspaper,
  Play,
  Plus,
  Sparkles,
  Settings,
  ShieldAlert,
  Terminal,
  Trash2,
  Wallet,
  X,
  Zap,
  ArrowDownToLine,
  LoaderCircle,
  RefreshCw,
  Download
};

const component = computed(() => ICONS[props.name] ?? BrainCircuit);
</script>

<template>
  <component :is="component" :size="props.size" :stroke-width="props.strokeWidth" :class="props.class" />
</template>
