<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import LucideIcon from "../icons/LucideIcon.vue";
import AgentRunItem from "./AgentRunItem.vue";
import type { AgentContentItem, AgentRun, AnalysisTask } from "../../types/alphaMind";
import MarkdownRender from "markstream-vue";

const { t } = useI18n();

const AGENT_NAME_DISPLAY_KEY = "amAgentNameDisplay";
const AGENT_NAME_TO_I18N_KEY: Record<string, string> = {
  MarketAnalyst: "市场分析师",
  NewsAnalyst: "新闻分析师",
  FundamentalsAnalyst: "基本面分析师",
  BullResearcher: "多头研究员",
  BearResearcher: "空头研究员",
  ResearchManager: "研究经理",
  EvidenceAuditor: "证据审计员",
  RiskyDebator: "激进风控辩手",
  SafeDebator: "保守风控辩手",
  NeutralDebator: "中性风控辩手",
  RiskManager: "风控经理",
  TraderAgent: "交易员",
};

const agentNameDisplay = (rawName: string): string => {
  const normalized = (rawName || "").split(".").pop() || "";
  const key = AGENT_NAME_TO_I18N_KEY[normalized];
  if (!key) return rawName;
  return t(key);
};

provide(AGENT_NAME_DISPLAY_KEY, agentNameDisplay);

const TOOL_NAME_DISPLAY_KEY = "amToolNameDisplay";
const TOOL_NAME_TO_I18N_KEY: Record<string, string> = {
  get_fundamentals: "查看公司概况",
  get_balance_sheet: "查看资产负债表",
  get_cashflow: "查看现金流量表",
  get_income_statement: "查看利润表",
  get_insider_transactions: "查看内幕交易",
  get_market_data: "查看市场数据",
  get_indicator_timeseries: "查看技术指标",
  get_company_news: "查看公司新闻",
  get_global_news: "查看全球新闻",
  crawl_url_content: "阅读网页",
  search_baidu_news: "查找近期资讯",
};

const toolNameDisplay = (rawName: string): string => {
  const normalized = (rawName || "").split(".").pop() || "";
  const key = TOOL_NAME_TO_I18N_KEY[normalized];
  if (!key) return rawName;
  return t(key);
};

provide(TOOL_NAME_DISPLAY_KEY, toolNameDisplay);
/**
 * LiveStream：任务分析的“流式输出”视图
 *
 * 设计态说明：
 * - `task.rootRuns` 是结构化的代理运行树，组件会自动滚动到最底部；
 * - `task.status` 从 analyzing -> completed 时也会触发滚动与头部状态更新。
 */

const props = withDefaults(
  defineProps<{
    task: AnalysisTask;
    immersive?: boolean;
    showClose?: boolean;
  }>(),
  {
    immersive: true,
    showClose: undefined,
  },
);

const emit = defineEmits<{
  (e: "close"): void;
  (e: "trade", task: AnalysisTask): void;
}>();

const scrollRef = ref<HTMLDivElement | null>(null);
const atBottom = ref(true);
const manualIntervening = ref(false);
const returnReadingScrollTop = ref<number | null>(null);

type QuoteMatchStatus = "pending" | "matched" | "low_confidence" | "not_found";

type QuoteMatchResult = {
  key: string;
  status: QuoteMatchStatus;
  score: number;
  quoteFull: string;
  anchorRunId: string;
  anchorItemId: string;
  sourceRunId: string | null;
  sourceItemId: string | null;
  sourceAgentName: string | null;
};

type QuoteRunController = {
  expand: () => void;
  openThinking: (itemId: string) => void;
};

type QuoteContext = {
  scrollContainerRef: { value: HTMLDivElement | null };
  version: { value: number };
  getMatch: (key: string) => QuoteMatchResult | undefined;
  getOrComputeMatch: (params: { key: string; quoteFull: string; anchorRunId: string; anchorItemId: string }) => Promise<QuoteMatchResult>;
  getRun: (runId: string) => AgentRun | null;
  registerBlock: (runId: string, itemId: string, el: HTMLElement | null) => void;
  registerRunController: (runId: string, controller: QuoteRunController | null) => void;
  expandRun: (runId: string) => void;
  openThinking: (runId: string, itemId: string) => void;
  getBlockEl: (runId: string, itemId: string) => HTMLElement | null;
  setReturnReading: (scrollTop: number) => void;
  clearReturnReading: () => void;
};

const QUOTE_CTX_KEY = "amQuoteContext";
const KEY_SEP = "\u0000";

const quoteCache = new Map<string, QuoteMatchResult>();
const quotePromises = new Map<string, Promise<QuoteMatchResult>>();
const quoteKnownKeys = new Set<string>();
const quoteVersion = ref(0);

const runMap = new Map<string, AgentRun>();
const runIndex = new Map<string, number>();
const blockEls = new Map<string, HTMLElement>();
const runControllers = new Map<string, QuoteRunController>();

const flattenRuns = (runs: AgentRun[]): AgentRun[] => {
  const out: AgentRun[] = [];
  const visit = (r: AgentRun) => {
    out.push(r);
    (r.children || []).forEach(visit);
  };
  runs.forEach(visit);
  return out;
};

type ContentItem = { id: string; type: "content"; text: string; timestamp: number };
const isContentItem = (it: AgentContentItem): it is ContentItem => (it as any)?.type === "content" && typeof (it as any)?.text === "string";

const normalizeForMatch = (input: string): string => {
  const s = (input || "").toLowerCase().normalize("NFKC");
  try {
    return s.replace(/[^\p{L}\p{N}]+/gu, "");
  } catch {
    return s.replace(/[\s"“”'‘’`.,，。:：;；!?！？()（）【】\[\]{}<>*_~#>|\\/-]/g, "").replace(/[—–\-]/g, "");
  }
};

const buildBigrams = (input: string): Set<string> => {
  const s = normalizeForMatch(input);
  const set = new Set<string>();
  if (s.length <= 2) {
    if (s) set.add(s);
    return set;
  }
  for (let i = 0; i < s.length - 1; i++) set.add(s.slice(i, i + 2));
  return set;
};

const jaccard = (a: Set<string>, b: Set<string>): number => {
  if (a.size === 0 || b.size === 0) return 0;
  let inter = 0;
  const [small, big] = a.size <= b.size ? [a, b] : [b, a];
  for (const x of small) if (big.has(x)) inter++;
  const union = a.size + b.size - inter;
  return union === 0 ? 0 : inter / union;
};

const recall = (needle: Set<string>, haystack: Set<string>): number => {
  if (needle.size === 0 || haystack.size === 0) return 0;
  let inter = 0;
  for (const x of needle) if (haystack.has(x)) inter++;
  return inter / needle.size;
};

const needleScoreWithin = (qNorm: string, tNorm: string): number => {
  const needleSize = Math.min(24, qNorm.length);
  const needles = [
    qNorm.slice(0, needleSize),
    qNorm.slice(
      Math.max(0, Math.floor(qNorm.length / 2) - Math.floor(needleSize / 2)),
      Math.min(qNorm.length, Math.floor(qNorm.length / 2) + Math.floor(needleSize / 2)),
    ),
    qNorm.slice(Math.max(0, qNorm.length - needleSize)),
  ].filter(Boolean);
  if (!needles.length) return 0;
  let hits = 0;
  for (const n of needles) if (n && tNorm.includes(n)) hits++;
  return hits / needles.length;
};

const splitQuoteSegments = (quoteFull: string): string[] => {
  const raw = quoteFull.trim();
  if (!raw) return [];
  const parts = raw
    .split(/…|\.{3,}/g)
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length <= 1) return [];
  return parts;
};

type TextScore = { score: number; exact: boolean; strong: boolean };

type BestCandidate = {
  score: number;
  strong: boolean;
  runId: string;
  itemId: string;
  agentName: string | null;
  pos: number;
};

const scoreTextApprox = (quoteFull: string, text: string): TextScore => {
  const qNorm = normalizeForMatch(quoteFull);
  const tNorm = normalizeForMatch(text);
  if (!qNorm || !tNorm) return { score: 0, exact: false, strong: false };

  if (tNorm.includes(qNorm)) return { score: 1, exact: true, strong: true };

  const segs = splitQuoteSegments(quoteFull);
  if (segs.length >= 2) {
    const segNorms = segs.map(normalizeForMatch).filter(Boolean);
    const usable = segNorms.filter((s) => s.length >= 4);
    if (usable.length >= 2) {
      let hitCount = 0;
      let bestSeg = 0;
      for (const sNorm of usable) {
        const exactHit = tNorm.includes(sNorm);
        if (exactHit) hitCount++;
        const approx = Math.max(
          exactHit ? 1 : 0,
          jaccard(buildBigrams(sNorm), buildBigrams(text)),
          needleScoreWithin(sNorm, tNorm) * 0.9,
        );
        if (approx > bestSeg) bestSeg = approx;
      }
      const ratio = hitCount / usable.length;
      const strong = ratio >= 0.67;
      const score = Math.max(bestSeg, ratio * 0.98);
      return { score, exact: false, strong };
    }
  }

  const qB = buildBigrams(quoteFull);
  const tB = buildBigrams(text);
  const score = Math.max(recall(qB, tB), jaccard(qB, tB) * 0.92, needleScoreWithin(qNorm, tNorm) * 0.88);
  return { score, exact: false, strong: false };
};

const extractQuotes = (text: string): string[] => {
  if (!text) return [];
  const out: string[] = [];
  const re = /\[\[quote:([\s\S]*?)\]\]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const raw = (m[1] ?? "").trim();
    if (raw) out.push(raw);
  }
  return out;
};

const stripQuoteMarkers = (text: string) => text.replace(/\s*\[\[quote:[\s\S]*?\]\]/g, "");

const updateRunIndexes = () => {
  runMap.clear();
  runIndex.clear();
  const all = flattenRuns(props.task.rootRuns || []);
  all.forEach((r, idx) => {
    runMap.set(r.id, r);
    runIndex.set(r.id, idx);
  });
};

const computeMatch = (params: { key: string; quoteFull: string; anchorRunId: string; anchorItemId: string }): QuoteMatchResult => {
  const roots = props.task.rootRuns || [];
  const allRuns = flattenRuns(roots);
  const ordered = allRuns.map((r, idx) => ({ r, idx }));

  const anchorRunIdx = ordered.find((x) => x.r.id === params.anchorRunId)?.idx ?? ordered.length;
  const HIT_THRESHOLD = 0.72;
  const LOW_THRESHOLD = 0.56;

  let best: BestCandidate | null = null;
  let bestLow: BestCandidate | null = null;
  let pos = 0;

  const consider = (candidate: TextScore, runId: string, itemId: string, agentName: string | null): QuoteMatchResult | null => {
    if (candidate.exact) {
      const out: QuoteMatchResult = {
        key: params.key,
        status: "matched",
        score: candidate.score,
        quoteFull: params.quoteFull,
        anchorRunId: params.anchorRunId,
        anchorItemId: params.anchorItemId,
        sourceRunId: runId,
        sourceItemId: itemId,
        sourceAgentName: agentName,
      };
      return out;
    }

    if (candidate.score >= HIT_THRESHOLD) {
      if (!best || candidate.score > best.score + 0.02) {
        best = { score: candidate.score, strong: candidate.strong, runId, itemId, agentName, pos };
      }
    } else if (candidate.score >= LOW_THRESHOLD) {
      if (!bestLow || candidate.score > bestLow.score + 0.02) {
        bestLow = { score: candidate.score, strong: candidate.strong, runId, itemId, agentName, pos };
      }
    }
    return null;
  };

  for (const { r, idx } of ordered) {
    if (idx > anchorRunIdx) break;
    const contentItems = (r.contents || []).filter(isContentItem);
    if (contentItems.length === 0) continue;

    const anchorItemCutoff = r.id === params.anchorRunId ? contentItems.findIndex((it) => it.id === params.anchorItemId) : -1;
    const limit = r.id === params.anchorRunId ? (anchorItemCutoff >= 0 ? anchorItemCutoff : 0) : contentItems.length;
    if (limit <= 0) continue;
    const items = contentItems.slice(0, limit);

    const cleaned = items.map((it) => ({ id: it.id, text: stripQuoteMarkers(it.text || "") })).filter((x) => x.text.trim().length > 0);
    if (cleaned.length === 0) continue;

    for (let i = 0; i < cleaned.length; i++) {
      pos++;
      const single = scoreTextApprox(params.quoteFull, cleaned[i].text);
      const exactRes = consider(single, r.id, cleaned[i].id, r.agentName);
      if (exactRes) return exactRes;

      for (let win = 2; win <= 3; win++) {
        if (i + win > cleaned.length) break;
        pos++;
        const combo = cleaned.slice(i, i + win).map((x) => x.text).join("\n\n");
        const comboScore = scoreTextApprox(params.quoteFull, combo);
        const res = consider(comboScore, r.id, cleaned[i].id, r.agentName);
        if (res) return res;
      }
    }
  }

  const bestHit = best as unknown as BestCandidate | null;
  if (bestHit) {
    return {
      key: params.key,
      status: bestHit.strong ? "matched" : "low_confidence",
      score: bestHit.score,
      quoteFull: params.quoteFull,
      anchorRunId: params.anchorRunId,
      anchorItemId: params.anchorItemId,
      sourceRunId: bestHit.runId,
      sourceItemId: bestHit.itemId,
      sourceAgentName: bestHit.agentName,
    };
  }

  const bestLowHit = bestLow as unknown as BestCandidate | null;
  if (bestLowHit) {
    return {
      key: params.key,
      status: "low_confidence",
      score: bestLowHit.score,
      quoteFull: params.quoteFull,
      anchorRunId: params.anchorRunId,
      anchorItemId: params.anchorItemId,
      sourceRunId: bestLowHit.runId,
      sourceItemId: bestLowHit.itemId,
      sourceAgentName: bestLowHit.agentName,
    };
  }

  return {
    key: params.key,
    status: "not_found",
    score: 0,
    quoteFull: params.quoteFull,
    anchorRunId: params.anchorRunId,
    anchorItemId: params.anchorItemId,
    sourceRunId: null,
    sourceItemId: null,
    sourceAgentName: null,
  };
};

const setMatch = (key: string, result: QuoteMatchResult) => {
  quoteCache.set(key, result);
  quoteVersion.value++;
};

const getOrComputeMatch = (params: { key: string; quoteFull: string; anchorRunId: string; anchorItemId: string }) => {
  const existing = quoteCache.get(params.key);
  if (existing && existing.status !== "pending") return Promise.resolve(existing);
  const pending = quotePromises.get(params.key);
  if (pending) return pending;

  const p = new Promise<QuoteMatchResult>((resolve) => {
    const run = () => {
      const res = computeMatch(params);
      setMatch(params.key, res);
      quotePromises.delete(params.key);
      resolve(res);
    };

    const ric = (window as any).requestIdleCallback as ((cb: () => void, opts?: any) => any) | undefined;
    if (ric) ric(run, { timeout: 600 });
    else setTimeout(run, 0);
  });
  quotePromises.set(params.key, p);
  if (!existing) setMatch(params.key, { ...params, status: "pending", score: 0, sourceRunId: null, sourceItemId: null, sourceAgentName: null });
  return p;
};

const registerBlock = (runId: string, itemId: string, el: HTMLElement | null) => {
  const key = `${runId}:${itemId}`;
  if (el) blockEls.set(key, el);
  else blockEls.delete(key);
};

const registerRunController = (runId: string, controller: QuoteRunController | null) => {
  if (controller) runControllers.set(runId, controller);
  else runControllers.delete(runId);
};

const setReturnReading = (scrollTop: number) => {
  returnReadingScrollTop.value = scrollTop;
};

const clearReturnReading = () => {
  returnReadingScrollTop.value = null;
};

const returnToReading = () => {
  const el = scrollRef.value;
  const top = returnReadingScrollTop.value;
  if (!el || top === null) return;
  scrollScheduleToken++;
  autoScrollUntil = 0;
  manualIntervening.value = true;
  el.scrollTo({ top, behavior: "smooth" });
  window.setTimeout(() => {
    if (returnReadingScrollTop.value === top) returnReadingScrollTop.value = null;
  }, 450);
};

const expandRun = (runId: string) => {
  runControllers.get(runId)?.expand();
};

const openThinking = (runId: string, itemId: string) => {
  runControllers.get(runId)?.openThinking(itemId);
};

const getBlockEl = (runId: string, itemId: string) => {
  return blockEls.get(`${runId}:${itemId}`) || null;
};

const quoteCtx: QuoteContext = {
  scrollContainerRef: scrollRef,
  version: quoteVersion,
  getMatch: (key) => quoteCache.get(key),
  getOrComputeMatch,
  getRun: (runId) => runMap.get(runId) || null,
  registerBlock,
  registerRunController,
  expandRun,
  openThinking,
  getBlockEl,
  setReturnReading,
  clearReturnReading,
};

provide(QUOTE_CTX_KEY, quoteCtx);

let scrollToBottomScheduled = false;
let scrollScheduleToken = 0;
let autoScrollUntil = 0;

function scrollToBottom() {
  const el = scrollRef.value;
  if (!el) return;
  autoScrollUntil = performance.now() + 120;
  el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
}

async function scheduleScrollToBottom() {
  if (manualIntervening.value) return;
  if (scrollToBottomScheduled) return;
  scrollToBottomScheduled = true;
  const token = scrollScheduleToken;
  await nextTick();
  scrollToBottomScheduled = false;
  if (token !== scrollScheduleToken) return;
  if (manualIntervening.value) return;
  scrollToBottom();
}

function isNearBottom(el: HTMLDivElement) {
  const threshold = 120;
  return el.scrollHeight - (el.scrollTop + el.clientHeight) <= threshold;
}

function handleScroll() {
  const el = scrollRef.value;
  if (!el) return;

  const near = isNearBottom(el);
  atBottom.value = near;

  if (performance.now() < autoScrollUntil) return;

  if (manualIntervening.value && near) manualIntervening.value = false;
}

function handleWheel(event: WheelEvent) {
  const el = scrollRef.value;
  if (!el) return;

  const near = isNearBottom(el);
  atBottom.value = near;

  if (!near && !manualIntervening.value) {
    scrollScheduleToken++;
    autoScrollUntil = 0;
    manualIntervening.value = true;
  }

  if (event.deltaY < 0) {
    if (!manualIntervening.value) {
      scrollScheduleToken++;
      autoScrollUntil = 0;
      manualIntervening.value = true;
    }
    return;
  }

  if (event.deltaY > 0 && manualIntervening.value && near) {
    scrollScheduleToken++;
    autoScrollUntil = 0;
    manualIntervening.value = false;
  }
}

function handleTouchMove() {
  scrollScheduleToken++;
  autoScrollUntil = 0;
  manualIntervening.value = true;
}

function handlePointerDown(event: PointerEvent) {
  const el = scrollRef.value;
  if (!el) return;

  const rect = el.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const hitSize = 28;
  if (x >= rect.width - hitSize) {
    scrollScheduleToken++;
    autoScrollUntil = 0;
    manualIntervening.value = true;
  }
}

function handleClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null;
  if (!target) return;
  if (target.closest(".am-quote")) {
    scrollScheduleToken++;
    autoScrollUntil = 0;
    manualIntervening.value = true;
  }
}

const streamRevision = computed(() => {
  const roots = props.task.rootRuns || [];
  const all = flattenRuns(roots);
  let totalItems = 0;
  let lastKey = "";
  for (const r of all) {
    const items = r.contents || [];
    totalItems += items.length;
    if (items.length === 0) continue;
    const last = items[items.length - 1] as any;
    const text = typeof last?.text === "string" ? (last.text as string) : "";
    lastKey = `${r.id}:${String(last?.id ?? "")}:${text.length}`;
  }
  return `${all.length}:${totalItems}:${lastKey}`;
});

onMounted(() => {
  const el = scrollRef.value;
  if (el) {
    atBottom.value = isNearBottom(el);
    el.addEventListener("scroll", handleScroll, { passive: true });
    el.addEventListener("wheel", handleWheel, { passive: true });
    el.addEventListener("touchmove", handleTouchMove, { passive: true });
    el.addEventListener("pointerdown", handlePointerDown, { passive: true });
    el.addEventListener("click", handleClick);
  }
  scheduleScrollToBottom();
});

onUnmounted(() => {
  const el = scrollRef.value;
  if (el) {
    el.removeEventListener("scroll", handleScroll);
    el.removeEventListener("wheel", handleWheel);
    el.removeEventListener("touchmove", handleTouchMove);
    el.removeEventListener("pointerdown", handlePointerDown);
    el.removeEventListener("click", handleClick);
  }
});

watch(
  () => streamRevision.value,
  () => {
    updateRunIndexes();
    if (!manualIntervening.value) scheduleScrollToBottom();
  },
  { flush: "post" }
);

watch(
  () => props.task.rootRuns,
  () => {
    const roots = props.task.rootRuns || [];
    const all = flattenRuns(roots);
    for (const r of all) {
      for (const item of r.contents || []) {
        const text = (item as any).text as string | undefined;
        if (!text) continue;
        const quotes = extractQuotes(text);
        for (const q of quotes) {
          const key = `${r.id}${KEY_SEP}${item.id}${KEY_SEP}${q}`;
          if (quoteKnownKeys.has(key)) continue;
          quoteKnownKeys.add(key);
          getOrComputeMatch({ key, quoteFull: q, anchorRunId: r.id, anchorItemId: item.id });
        }
      }
    }
  },
  { deep: true, immediate: true }
);

const statusText = computed(() => {
  const s = props.task.status;
  switch (s) {
    case "analyzing":
      return t("分析中");
    case "completed":
      return t("已完成");
    case "failed":
      return t("失败");
    case "cancelled":
      return t("已取消");
    default:
      return "";
  }
});

const recommendationText = computed(() => {
  const r = props.task.result?.recommendation;
  switch (r) {
    case "BUY":
      return t("买入");
    case "SELL":
      return t("卖出");
    case "HOLD":
      return t("观望");
    default:
      return "";
  }
});

const reportSummary = computed(() => stripQuoteMarkers(props.task.result?.summary ?? ""));
</script>

<template>
  <div
    :class="[
      'relative flex flex-col h-full bg-[#FAFAFA]',
      props.immersive ? 'fixed inset-0 z-50' : 'relative rounded-xl overflow-hidden border border-gray-200',
    ]"
  >
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 z-10 sticky top-0">
      <div class="flex items-center gap-4">
        <div
          :class="[
            'flex items-center justify-center w-8 h-8 rounded-full border',
            props.task.status === 'analyzing'
              ? 'bg-white border-slate-900 text-slate-900'
              : props.task.status === 'completed'
                ? 'bg-slate-900 border-slate-900 text-white'
                : 'bg-red-500 border-red-500 text-white',
          ]"
        >
          <LucideIcon v-if="props.task.status === 'analyzing'" name="Loader2" :size="16" class="animate-spin" />
          <LucideIcon v-else-if="props.task.status === 'completed'" name="CheckCircle" :size="16" />
          <LucideIcon v-else name="AlertCircle" :size="16" />
        </div>

        <div>
          <div class="flex items-center gap-2">
            <h2 class="text-lg font-bold text-slate-900 tracking-tight">{{ props.task.stockCode }}</h2>
            <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 border border-gray-200">
              {{ props.task.market }}
            </span>
          </div>
          <div v-if="props.task.companyName" class="text-xs text-gray-400 font-medium leading-4">{{ props.task.companyName }}</div>
        </div>
      </div>

      <button
        v-if="props.showClose ?? props.immersive"
        type="button"
        class="w-8 h-8 flex items-center justify-center rounded hover:bg-gray-100 text-gray-400 hover:text-slate-900 transition-colors"
        @click="emit('close')"
      >
        <LucideIcon name="X" :size="20" />
      </button>
    </div>

    <div ref="scrollRef" class="flex-1 overflow-y-auto relative p-6 md:p-10 scroll-smooth bg-[#FAFAFA]">
      <div class="max-w-4xl mx-auto">
        <div class="grid grid-cols-3 gap-4 mb-10 text-xs font-mono text-gray-400 border-b border-gray-200 pb-4">
          <div>{{ t("会话ID：") }}{{ props.task.id }}</div>
          <div class="text-center">{{ t("模式：") }}{{ t("多智能体") }}</div>
          <div class="text-right">{{ t("状态：") }}{{ statusText }}</div>
        </div>

        <div class="relative pl-2">
          
          <!-- Structured Agent Stream -->
          <template v-if="props.task.rootRuns && props.task.rootRuns.length > 0">
             <AgentRunItem
               v-for="run in props.task.rootRuns"
               :key="run.id"
               :run="run"
               :root-runs="props.task.rootRuns"
               :agent-name-map="AGENT_NAME_TO_I18N_KEY"
             />
          </template>

          <!-- Report Section -->
          <div v-if="props.task.status === 'completed' && props.task.result" class="my-12 animate-slide-up px-4 md:px-0">
              <div class="max-w-4xl mx-auto mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-[12px] leading-5">
                <div class="flex items-start gap-2 text-amber-900">
                  <LucideIcon name="ShieldAlert" :size="16" class="mt-0.5 text-amber-700" />
                  <div>
                    <div class="font-black tracking-wide">{{ t("重要风险揭示与合规声明") }}</div>
                    <div class="mt-1 text-amber-800 whitespace-pre-line">
                      {{
                        t(
                          "本内容由大语言模型（LLM）结合有限数据自动生成，仅用于信息展示与研究参考，不构成证券投资咨询服务、个股推荐、交易指令或任何形式的收益承诺。\n\nLLM 存在固有局限与风险（包括但不限于）：\n• 不同模型/版本/参数/数据获取范围会导致输出差异，结果不具一致性与可复现性\n• 可能出现事实性错误、推断偏差或“幻觉”内容（看似合理但并非真实）\n• 信息可能不完整、过时或存在采集/解析误差，无法保证覆盖所有重要信息\n• 可能误解上下文、忽略关键约束，尤其在极端行情或小样本情形下\n\n请仅将其作为辅助线索，结合公开信息与自身风险承受能力独立判断，必要时咨询持牌专业机构/人士；据此操作，风险自担。",
                        )
                      }}
                    </div>
                  </div>
                </div>
              </div>
              <div class="bg-white border-y md:border border-gray-200 md:rounded-xl p-8 shadow-sm max-w-4xl mx-auto">
                <div class="flex justify-between items-start mb-8 border-b border-gray-100 pb-6">
                  <div class="flex items-center gap-4">
                    <div class="w-12 h-12 bg-slate-900 text-white flex items-center justify-center rounded-lg">
                      <LucideIcon name="Cpu" :size="24" />
                    </div>
                    <div>
                      <h3 class="text-2xl font-bold text-slate-900 tracking-tight">{{ t("分析报告") }}</h3>
                      <p class="text-xs text-gray-500 font-mono mt-1">
                        {{ t("参考编号：") }}{{ props.task.id.substring(Math.max(0, props.task.id.length - 8)) }}
                      </p>
                    </div>
                  </div>

                  <div v-if="props.task.result" class="text-right">
                    <div class="text-xs text-gray-400 uppercase font-bold tracking-wider mb-1">{{ t("参考信号") }}</div>
                    <div
                      :class="[
                        'text-2xl font-black tracking-tight',
                        props.task.result.recommendation === 'BUY'
                          ? 'text-emerald-600'
                          : props.task.result.recommendation === 'SELL'
                            ? 'text-rose-600'
                            : 'text-amber-600',
                      ]"
                    >
                      {{ recommendationText }}
                    </div>
                  </div>
                </div>

                <div class="prose prose-sm prose-slate max-w-none mb-8 prose-p:text-base prose-p:leading-7 prose-p:font-medium">
                  <MarkdownRender :custom-id="`report:${props.task.id}`" :content="reportSummary" />
                </div>

                <div v-if="props.task.result" class="flex justify-end pt-4 border-t border-gray-100">
                  <button
                    type="button"
                    class="flex items-center gap-2 bg-slate-900 hover:bg-black text-white px-6 py-3 rounded-lg shadow-sm transition-colors font-bold text-sm"
                    @click="emit('trade', props.task)"
                  >
                    <LucideIcon name="Play" :size="16" class="fill-current" />
                    {{ t("跟踪评估") }}
                  </button>
                </div>
              </div>
            </div>

          <div v-if="props.task.status === 'analyzing'" class="flex items-center gap-3 mt-4 ml-14 opacity-60">
            <LucideIcon name="Loader2" :size="14" class="animate-spin text-slate-900" />
            <span class="text-xs font-mono text-slate-900">{{ t("流式处理中...") }}</span>
          </div>

          <div class="h-24"></div>
        </div>
      </div>
    </div>

    <div v-if="returnReadingScrollTop !== null" class="absolute bottom-4 right-4 z-30">
      <div class="flex items-center gap-1 rounded-full border border-slate-200/70 bg-white/85 backdrop-blur px-1.5 py-1 shadow-sm">
        <button
          type="button"
          class="h-8 w-8 rounded-full flex items-center justify-center text-slate-600 hover:text-slate-900 hover:bg-slate-900/5"
          :aria-label="t('返回阅读区域')"
          :title="t('返回阅读区域')"
          @click="returnToReading"
        >
          <LucideIcon name="CornerUpLeft" :size="16" />
        </button>
        <button
          type="button"
          class="h-8 w-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-900/5"
          aria-label="close"
          @click="clearReturnReading"
        >
          <LucideIcon name="X" :size="14" />
        </button>
      </div>
    </div>
  </div>
</template>
