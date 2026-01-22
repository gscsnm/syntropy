<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { AgentRun } from "../../types/alphaMind";
import LucideIcon from "../icons/LucideIcon.vue";
import { AGENT_CONFIG } from "../../constants/alphaMind";
import MarkdownRender from "markstream-vue";
defineOptions({ name: "AgentRunItem" });

const props = defineProps<{
  run: AgentRun;
  rootRuns?: AgentRun[];
  agentNameMap?: Record<string, string>;
}>();

const { t } = useI18n();

const agentNameDisplay = inject<((rawName: string) => string) | null>("amAgentNameDisplay", null);
const displayAgentName = computed(() => (agentNameDisplay ? agentNameDisplay(props.run.agentName) : props.run.agentName));
const toolNameDisplay = inject<((rawName: string) => string) | null>("amToolNameDisplay", null);
const displayToolName = (rawName: string) => (toolNameDisplay ? toolNameDisplay(rawName) : rawName);

const isExpanded = ref(true);
const manualThinkingIds = ref<Set<string>>(new Set());
const thinkingRefs = ref<Record<string, HTMLDivElement | null>>({});
const rootElRef = ref<HTMLDivElement | null>(null);

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

const quoteCtx = inject<QuoteContext | null>("amQuoteContext", null);

const escapeHtml = (input: string): string =>
  input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const truncateQuote = (input: string, maxLength: number): string => {
  if (input.length <= maxLength) return input;
  return input.slice(0, maxLength).trimEnd() + "…";
};

const isWordChar = (ch: string | undefined): boolean => {
  if (!ch) return false;
  return /[A-Za-z0-9_]/.test(ch);
};

const isBoundaryChar = (ch: string | undefined): boolean => !isWordChar(ch);

const findNextAgentMatch = (text: string, start: number, keys: string[]): { pos: number; key: string } => {
  let bestPos = -1;
  let bestKey = "";

  for (const key of keys) {
    let pos = text.indexOf(key, start);
    while (pos !== -1) {
      const before = pos > 0 ? text[pos - 1] : undefined;
      const after = pos + key.length < text.length ? text[pos + key.length] : undefined;
      if (isBoundaryChar(before) && isBoundaryChar(after)) {
        if (bestPos === -1 || pos < bestPos || (pos === bestPos && key.length > bestKey.length)) {
          bestPos = pos;
          bestKey = key;
        }
        break;
      }
      pos = text.indexOf(key, pos + 1);
    }
  }

  return { pos: bestPos, key: bestKey };
};

const customMarkdownIt = (md: any) => {
  if (md) {
    const map = props.agentNameMap ?? {};
    (md as any).__amAgentNameMap = map;
    (md as any).__amAgentKeys = Object.keys(map).sort((a: string, b: string) => b.length - a.length);
  }

  if (md && !(md as any).__amQuoteRuleInstalled) {
    (md as any).__amQuoteRuleInstalled = true;

    const marker = "[[quote:";
    md.inline.ruler.before("emphasis", "am_quote", (state: any, silent: boolean) => {
      const start = state.pos;
      if (state.src.slice(start, start + marker.length) !== marker) return false;

      const close = state.src.indexOf("]]", start + marker.length);
      if (close === -1) return false;

      const fullRaw = state.src.slice(start + marker.length, close).trim();
      const fullEscaped = escapeHtml(fullRaw);
      const labelEscaped = escapeHtml(t("QUOTE"));
      const shortEscaped = escapeHtml(truncateQuote(fullRaw, 34));

      if (!silent) {
        const token = state.push("html_inline", "", 0);
        token.content = `<button type="button" class="am-quote" data-am-quote-full="${fullEscaped}" title="${fullEscaped}"><span class="am-quote-label">${labelEscaped}</span><span class="am-quote-text">${shortEscaped}</span></button>`;
      }

      state.pos = close + 2;
      return true;
    });
  }

  if (md && !(md as any).__amAgentRuleInstalled) {
    (md as any).__amAgentRuleInstalled = true;

    md.core.ruler.after("inline", "am_agent_badge", (state: any) => {
      const map = (md as any).__amAgentNameMap as Record<string, string> | undefined;
      const keys = (md as any).__amAgentKeys as string[] | undefined;
      if (!map || !keys || keys.length === 0) return;

      const Token = state.Token;
      for (const blockToken of state.tokens || []) {
        if (blockToken.type !== "inline" || !blockToken.children || blockToken.children.length === 0) continue;

        const nextChildren: any[] = [];
        for (const child of blockToken.children) {
          if (child.type !== "text" || !child.content) {
            nextChildren.push(child);
            continue;
          }

          const text: string = child.content;
          let idx = 0;
          while (idx < text.length) {
            const { pos, key } = findNextAgentMatch(text, idx, keys);
            if (pos === -1) {
              const tail = text.slice(idx);
              if (tail) {
                const tToken = new Token("text", "", 0);
                tToken.content = tail;
                nextChildren.push(tToken);
              }
              break;
            }

            const head = text.slice(idx, pos);
            if (head) {
              const tToken = new Token("text", "", 0);
              tToken.content = head;
              nextChildren.push(tToken);
            }

            const display = map[key] ? t(map[key]) : key;
            const badge = new Token("html_inline", "", 0);
            badge.content = `<span class="am-agent" data-am-agent-key="${escapeHtml(key)}"><span class="am-agent-dot"></span><span class="am-agent-text">${escapeHtml(display)}</span></span>`;
            nextChildren.push(badge);

            idx = pos + key.length;
          }
        }

        blockToken.children = nextChildren;
      }
    });
  }

  return md;
};

const agentConfig = computed(() => {
  const name = props.run.agentName;
  if (name.includes("Manager")) return AGENT_CONFIG.Manager;
  if (name.includes("Market") || name.includes("Data")) return AGENT_CONFIG.DataAnalyst;
  if (name.includes("Risk")) return AGENT_CONFIG.RiskManager;
  if (name.includes("Strategist")) return AGENT_CONFIG.Strategist;
  if (name.includes("Sentiment")) return AGENT_CONFIG.SentimentAnalyst;
  return AGENT_CONFIG.Manager;
});

const latestThinkingId = computed(() => {
  const items = props.run.contents;
  if (!items || items.length === 0) return null;
  const last = items[items.length - 1];
  return last.type === "thinking" ? last.id : null;
});

const openThinkingIds = computed(() => {
  const set = new Set<string>(manualThinkingIds.value);
  const id = latestThinkingId.value;
  if (id) set.add(id);
  return set;
});

const setThinkingRef = (id: string, el: HTMLDivElement | null) => {
  thinkingRefs.value[id] = el;
};

type QuotePopoverState = {
  anchor: HTMLElement;
  full: string;
  short: string;
  top: number;
  left: number;
  anchorRunId: string;
  anchorItemId: string;
  key: string;
  status: QuoteMatchStatus;
  score: number;
  sourceRunId: string | null;
  sourceItemId: string | null;
  sourceAgentName: string | null;
  previewHitEl: HTMLElement | null;
  previewMarkdown: string;
};

const quotePopover = ref<QuotePopoverState | null>(null);
const quotePreviewRef = ref<HTMLDivElement | null>(null);
const locateHitEl = ref<HTMLElement | null>(null);

const updateQuotePopoverPosition = (state: QuotePopoverState) => {
  const rect = state.anchor.getBoundingClientRect();
  const preferredWidth = 380;
  const margin = 12;
  const left = Math.min(
    Math.max(margin, rect.left),
    Math.max(margin, window.innerWidth - preferredWidth - margin),
  );
  const top = Math.min(rect.bottom + 8, window.innerHeight - margin);
  state.left = left;
  state.top = top;
};

const normalizeForMatch = (input: string): string => {
  const s = (input || "").toLowerCase().normalize("NFKC");
  try {
    return s.replace(/[^\p{L}\p{N}]+/gu, "");
  } catch {
    return s.replace(/[\s"“”'‘’`.,，。:：;；!?！？()（）【】\[\]{}<>*_~#>|\\/-]/g, "").replace(/[—–\-]/g, "");
  }
};

const closeQuotePopover = () => {
  const st = quotePopover.value;
  if (st?.previewHitEl) st.previewHitEl.classList.remove("am-quote-preview-hit");
  quotePopover.value = null;
};

const clearLocateHit = () => {
  const el = locateHitEl.value;
  if (el) el.classList.remove("am-quote-locate-hit");
  locateHitEl.value = null;
};

const markLocateHit = (el: HTMLElement) => {
  clearLocateHit();
  locateHitEl.value = el;
  el.classList.add("am-quote-locate-hit");
  window.setTimeout(() => {
    if (locateHitEl.value === el) clearLocateHit();
  }, 5200);
};

type ContentItem = { id: string; type: "content"; text: string; timestamp: number };
const isContentItem = (it: any): it is ContentItem => it?.type === "content" && typeof it?.text === "string";

const buildRunMarkdown = (run: AgentRun): string => {
  const parts = (run.contents || []).filter(isContentItem).map((it) => it.text).filter(Boolean);
  return parts.join("\n\n");
};

const KEY_SEP = "\u0000";
const buildKey = (anchorRunId: string, anchorItemId: string, full: string) => `${anchorRunId}${KEY_SEP}${anchorItemId}${KEY_SEP}${full}`;

const findPreviewHitElement = (root: HTMLElement, quoteFull: string): HTMLElement | null => {
  const qNorm = normalizeForMatch(quoteFull);
  if (!qNorm) return null;
  const needle = qNorm.slice(0, Math.min(24, qNorm.length));
  const selectors = "p, li, blockquote, h1, h2, h3, h4, h5, h6, td, th, pre, code";
  const blocks = Array.from(root.querySelectorAll(selectors)) as HTMLElement[];
  for (const el of blocks) {
    const txt = el.textContent || "";
    if (!txt.trim()) continue;
    const tNorm = normalizeForMatch(txt);
    if (!tNorm) continue;
    if (tNorm.includes(qNorm)) return el;
    if (needle && tNorm.includes(needle)) return el;
  }
  return null;
};

const focusPreviewHit = async (st: QuotePopoverState) => {
  await nextTick();
  const root = quotePreviewRef.value;
  if (!root) return;

  if (st.previewHitEl) st.previewHitEl.classList.remove("am-quote-preview-hit");
  const hit = findPreviewHitElement(root, st.full);
  st.previewHitEl = hit;
  if (!hit) return;

  hit.classList.add("am-quote-preview-hit");
  hit.scrollIntoView({ behavior: "smooth", block: "center" });
};

const applyQuoteMarkerState = async () => {
  if (!quoteCtx) return;
  await nextTick();
  const root = rootElRef.value;
  if (!root) return;
  const quotes = Array.from(root.querySelectorAll(".am-quote")) as HTMLElement[];
  for (const el of quotes) {
    const full = el.getAttribute("data-am-quote-full") || "";
    const container = el.closest("[data-am-run-id][data-am-item-id]") as HTMLElement | null;
    const runId = container?.dataset.amRunId || "";
    const itemId = container?.dataset.amItemId || "";
    const key = full && runId && itemId ? buildKey(runId, itemId, full) : "";
    const match = key ? quoteCtx.getMatch(key) : undefined;
    const warn = match?.status === "not_found" || match?.status === "low_confidence";
    el.classList.toggle("am-quote--warn", Boolean(warn));
    el.classList.toggle("am-quote--notfound", match?.status === "not_found");
  }
};

watch(
  () => quoteCtx?.version.value,
  () => {
    applyQuoteMarkerState();
  },
  { immediate: true },
);

const setBlockRef = (runId: string, itemId: string, el: HTMLElement | null) => {
  if (!quoteCtx) return;
  quoteCtx.registerBlock(runId, itemId, el);
};

const setThinkingBlockRef = (itemId: string, runId: string, el: HTMLDivElement | null) => {
  setThinkingRef(itemId, el);
  setBlockRef(runId, itemId, el);
};

const showQuoteTip = (anchor: HTMLElement, message: string) => {
  const rect = anchor.getBoundingClientRect();
  const tip = document.createElement("div");
  tip.className = "am-quote-tip";
  tip.textContent = message;
  document.body.appendChild(tip);

  const margin = 10;
  const left = Math.min(Math.max(margin, rect.left), window.innerWidth - tip.offsetWidth - margin);
  const top = Math.max(margin, rect.top - tip.offsetHeight - 8);
  tip.style.left = `${left}px`;
  tip.style.top = `${top}px`;

  window.setTimeout(() => {
    tip.classList.add("am-quote-tip--hide");
    window.setTimeout(() => tip.remove(), 260);
  }, 1400);
};

onMounted(() => {
  if (!quoteCtx) return;
  quoteCtx.registerRunController(props.run.id, {
    expand: () => {
      isExpanded.value = true;
    },
    openThinking: (itemId: string) => {
      const s = new Set(manualThinkingIds.value);
      s.add(itemId);
      manualThinkingIds.value = s;
    },
  });
});

onUnmounted(() => {
  if (!quoteCtx) return;
  quoteCtx.registerRunController(props.run.id, null);
});

const handleQuoteClick = async (event: MouseEvent) => {
  const target = event.target as HTMLElement | null;
  if (!target) return;
  const el = target.closest(".am-quote") as HTMLElement | null;
  if (!el) return;

  event.preventDefault();

  const full = el.getAttribute("data-am-quote-full") || "";
  if (!full) return;
  const short = (el.querySelector(".am-quote-text") as HTMLElement | null)?.textContent || truncateQuote(full, 34);
  const container = (event.currentTarget as HTMLElement | null) || (el.parentElement as HTMLElement | null);
  const anchorRunId = container?.dataset.amRunId || props.run.id;
  const anchorItemId = container?.dataset.amItemId || "";
  const key = buildKey(anchorRunId, anchorItemId, full);

  if (!quoteCtx) return;
  const match = await quoteCtx.getOrComputeMatch({ key, quoteFull: full, anchorRunId, anchorItemId });
  if (match.status === "not_found" || !match.sourceRunId || !match.sourceItemId) {
    applyQuoteMarkerState();
    showQuoteTip(el, t("当前参考证据存疑"));
    return;
  }

  const st: QuotePopoverState = {
    anchor: el,
    full,
    short,
    top: 0,
    left: 0,
    anchorRunId,
    anchorItemId,
    key,
    status: match.status,
    score: match.score,
    sourceRunId: match.sourceRunId,
    sourceItemId: match.sourceItemId,
    sourceAgentName: match.sourceAgentName,
    previewHitEl: null,
    previewMarkdown: "",
  };
  updateQuotePopoverPosition(st);
  quotePopover.value = st;

  const run = match.sourceRunId ? quoteCtx.getRun(match.sourceRunId) : null;
  const next = quotePopover.value;
  if (!next || next.key !== key) return;
  next.previewMarkdown = run ? buildRunMarkdown(run) : "";
  focusPreviewHit(next);
  applyQuoteMarkerState();
};

const handleDocumentClick = (event: MouseEvent) => {
  const st = quotePopover.value;
  if (!st) return;
  const target = event.target as HTMLElement | null;
  if (!target) return;
  if (target.closest(".am-quote-popover")) return;
  if (target.closest(".am-quote")) return;
  closeQuotePopover();
};

const handleViewportChange = () => {
  const st = quotePopover.value;
  if (!st) return;
  updateQuotePopoverPosition(st);
};

watch(
  () => Boolean(quotePopover.value),
  (open) => {
    if (open) {
      window.addEventListener("click", handleDocumentClick, true);
      window.addEventListener("scroll", handleViewportChange, true);
      window.addEventListener("resize", handleViewportChange);
    } else {
      window.removeEventListener("click", handleDocumentClick, true);
      window.removeEventListener("scroll", handleViewportChange, true);
      window.removeEventListener("resize", handleViewportChange);
    }
  }
);

const expandChainToRun = (runId: string) => {
  if (!quoteCtx) return;
  let r = quoteCtx.getRun(runId);
  const seen = new Set<string>();
  while (r?.parentId) {
    if (seen.has(r.parentId)) break;
    seen.add(r.parentId);
    quoteCtx.expandRun(r.parentId);
    r = quoteCtx.getRun(r.parentId);
  }
  quoteCtx.expandRun(runId);
};

const findLocateHitInRun = (runId: string, quoteFull: string): HTMLElement | null => {
  const scroller = quoteCtx?.scrollContainerRef.value;
  const root = scroller || document.body;
  const blocks = Array.from(root.querySelectorAll(`[data-am-run-id="${runId}"][data-am-item-id]`)) as HTMLElement[];
  const primary = blocks.filter((b) => b.classList.contains("prose"));
  const secondary = blocks.filter((b) => !b.classList.contains("prose"));

  for (const b of primary) {
    const hit = findPreviewHitElement(b, quoteFull);
    if (hit) return hit;
  }
  for (const b of secondary) {
    const hit = findPreviewHitElement(b, quoteFull);
    if (hit) return hit;
  }
  return null;
};

const waitForLocateHit = async (runId: string, quoteFull: string): Promise<HTMLElement | null> => {
  for (let i = 0; i < 14; i++) {
    quoteCtx?.expandRun(runId);
    await nextTick();
    const hit = findLocateHitInRun(runId, quoteFull);
    if (hit) return hit;
    await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
  }
  return null;
};

const toggleExpanded = () => {
  quoteCtx?.clearReturnReading();
  isExpanded.value = !isExpanded.value;
};

const toggleThinking = (itemId: string) => {
  quoteCtx?.clearReturnReading();
  const s = new Set(manualThinkingIds.value);
  if (s.has(itemId)) s.delete(itemId);
  else s.add(itemId);
  manualThinkingIds.value = s;
};

const locateOriginal = async () => {
  const st = quotePopover.value;
  if (!st || !quoteCtx) return;

  closeQuotePopover();

  const scroller = quoteCtx.scrollContainerRef.value;
  const scrollTop = scroller ? scroller.scrollTop : (window.scrollY || 0);
  quoteCtx.setReturnReading(scrollTop);

  const match = await quoteCtx.getOrComputeMatch({
    key: st.key,
    quoteFull: st.full,
    anchorRunId: st.anchorRunId,
    anchorItemId: st.anchorItemId,
  });

  st.status = match.status;
  st.score = match.score;
  st.sourceRunId = match.sourceRunId;
  st.sourceItemId = match.sourceItemId;
  st.sourceAgentName = match.sourceAgentName;

  if (!match.sourceRunId) {
    applyQuoteMarkerState();
    return;
  }

  expandChainToRun(match.sourceRunId);
  await nextTick();
  await nextTick();

  const hit = await waitForLocateHit(match.sourceRunId, st.full);
  if (hit) {
    hit.scrollIntoView({ behavior: "smooth", block: "center" });
    markLocateHit(hit);
    return;
  }

  const fallbackBlock = match.sourceItemId ? quoteCtx.getBlockEl(match.sourceRunId, match.sourceItemId) : null;
  if (!fallbackBlock) return;

  fallbackBlock.scrollIntoView({ behavior: "smooth", block: "center" });
  markLocateHit(fallbackBlock);
};

const lastThinkingItem = computed(() => {
  const items = props.run.contents;
  if (!items || items.length === 0) return null;
  for (let i = items.length - 1; i >= 0; i--) {
    const it = items[i];
    if (it.type === "thinking") return it as any;
  }
  return null;
});

const lastThinkingKey = computed(() => {
  const it = lastThinkingItem.value;
  if (!it) return "";
  const t = (it.text ?? "") as string;
  return `${it.id}:${t.length}`;
});

watch(
  () => lastThinkingKey.value,
  async () => {
    const it = lastThinkingItem.value as any;
    if (!it) return;
    await nextTick();
    const el = thinkingRefs.value[it.id];
    if (el && openThinkingIds.value.has(it.id)) {
      el.scrollTop = el.scrollHeight;
    }
  },
  { flush: "post" }
);
</script>

<template>
  <div ref="rootElRef" class="mb-6 animate-slide-up">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-2 cursor-pointer select-none group" @click="toggleExpanded">
      <div class="w-8 h-8 rounded border flex items-center justify-center bg-white border-gray-200 text-slate-700 shadow-sm group-hover:border-slate-400 transition-colors">
         <LucideIcon :name="agentConfig.icon" :size="16" />
      </div>
      <div class="flex-1">
         <div class="flex items-center gap-2">
            <span class="font-bold text-sm text-slate-900">{{ displayAgentName }}</span>
            <span v-if="run.status === 'running'" class="flex h-2 w-2 relative">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
         </div>
      </div>
      <div class="text-gray-400 group-hover:text-slate-900">
         <LucideIcon :name="isExpanded ? 'ChevronDown' : 'ChevronRight'" :size="14" />
      </div>
    </div>

    <div v-if="isExpanded" class="pl-4 border-l-2 border-gray-100 ml-4 space-y-4">
        <div v-for="item in run.contents" :key="item.id">
          <template v-if="item.type === 'thinking'">
            <div class="bg-yellow-50/50 rounded text-xs text-slate-600/80 font-mono border border-yellow-100/50">
              <button
                type="button"
                class="w-full px-3 py-2 flex items-center justify-between"
                @click="toggleThinking(item.id)"
              >
                <div class="flex items-center gap-2 text-yellow-600/70 font-bold uppercase tracking-wider text-[10px]">
                  <LucideIcon name="BrainCircuit" :size="12" />
                  Thinking Process
                </div>
                <LucideIcon :name="openThinkingIds.has(item.id) ? 'ChevronDown' : 'ChevronRight'" :size="12" class="text-yellow-600/70" />
              </button>
              <div
                v-if="openThinkingIds.has(item.id)"
                class="relative px-3 pb-3 text-[11px] leading-6 opacity-70 italic max-h-48 overflow-y-auto"
                :data-am-run-id="run.id"
                :data-am-item-id="item.id"
                :ref="(el) => setThinkingBlockRef(item.id, run.id, el as HTMLDivElement | null)"
                @click.capture="handleQuoteClick"
              >
                <MarkdownRender :custom-id="(item as any).id" :content="(item as any).text" :custom-markdown-it="customMarkdownIt" />
                <div class="pointer-events-none absolute left-0 right-0 top-0 h-6 bg-gradient-to-b from-yellow-50/70 to-transparent"></div>
                <div class="pointer-events-none absolute left-0 right-0 bottom-0 h-6 bg-gradient-to-t from-yellow-50/70 to-transparent"></div>
              </div>
            </div>
          </template>
          <template v-else-if="item.type === 'content'">
            <div
              class="prose prose-sm max-w-none text-slate-800 bg-white p-4 rounded-lg border border-gray-100 shadow-sm leading-relaxed"
              :data-am-run-id="run.id"
              :data-am-item-id="item.id"
              :ref="(el) => setBlockRef(run.id, item.id, el as HTMLElement | null)"
              @click.capture="handleQuoteClick"
            >
              <MarkdownRender :custom-id="(item as any).id" :content="(item as any).text" :custom-markdown-it="customMarkdownIt" />
            </div>
          </template>
          <template v-else>
            <div class="bg-slate-50 rounded border border-gray-200 text-xs overflow-hidden">
              <div class="bg-gray-100 px-3 py-1.5 flex items-center justify-between border-b border-gray-200">
                <div class="flex items-center gap-2">
                  <LucideIcon name="Terminal" :size="12" class="text-gray-500" />
                  <span class="font-bold text-gray-600">{{ displayToolName((item as any).tool.name) }}</span>
                </div>
                <div :class="[
                    'text-[10px] uppercase font-bold px-1.5 py-0.5 rounded',
                    (item as any).tool.status === 'started' ? 'bg-blue-100 text-blue-600' : 
                    (item as any).tool.status === 'completed' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'
                ]">
                  {{ (item as any).tool.status }}
                </div>
              </div>
              <div class="p-2 font-mono text-slate-600 break-all">
                <span class="text-slate-400 select-none">$ </span>{{ JSON.stringify((item as any).tool.args) }}
              </div>
              <div v-if="(item as any).tool.result" class="p-2 border-t border-gray-200 bg-white font-mono text-slate-500 break-all max-h-32 overflow-y-auto">
                <span class="text-green-600 select-none">➜ </span>{{ typeof (item as any).tool.result === 'object' ? JSON.stringify((item as any).tool.result) : (item as any).tool.result }}
              </div>
              <div v-else-if="(item as any).tool.error" class="p-2 border-t border-gray-200 bg-white font-mono text-rose-600 break-all max-h-32 overflow-y-auto">
                <span class="text-rose-600 select-none">✖ </span>{{ typeof (item as any).tool.error === 'object' ? JSON.stringify((item as any).tool.error) : (item as any).tool.error }}
              </div>
            </div>
          </template>
        </div>

        <!-- Nested Children -->
        <div v-if="run.children && run.children.length > 0" class="mt-4">
            <AgentRunItem v-for="child in run.children" :key="child.id" :run="child" :root-runs="rootRuns" :agent-name-map="agentNameMap" />
        </div>
    </div>

    <div
      v-if="quotePopover"
      class="am-quote-popover"
      :style="{ top: `${quotePopover.top}px`, left: `${quotePopover.left}px` }"
      role="dialog"
    >
      <div class="am-quote-popover-header">
        <div class="am-quote-popover-title">{{ t("引用预览") }}</div>
        <div class="am-quote-popover-header-actions">
          <button type="button" class="am-quote-popover-action" @click="locateOriginal">
            {{ t("定位到原文") }}
          </button>
          <button type="button" class="am-quote-popover-close" @click="closeQuotePopover">
            {{ t("关闭") }}
          </button>
        </div>
      </div>
      <div class="am-quote-popover-body">
        <div
          ref="quotePreviewRef"
          class="am-quote-popover-preview"
          @wheel.stop
          @touchmove.stop
        >
          <MarkdownRender
            :custom-id="`${quotePopover.sourceRunId || 'unknown'}:${quotePopover.full}`"
            :content="quotePopover.previewMarkdown"
            :custom-markdown-it="customMarkdownIt"
          />
        </div>
    <div v-if="quotePopover.status === 'pending'" class="am-quote-popover-empty">
      {{ t("匹配中...") }}
    </div>
    <div v-else-if="quotePopover.status === 'not_found'" class="am-quote-popover-empty">
      {{ t("未找到原文匹配") }}
    </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.am-quote) {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.12em 0.55em;
  margin-left: 0.2rem;
  border-radius: 0.6rem;
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.28);
  color: rgba(51, 65, 85, 0.92);
  font-style: normal;
  font-weight: 600;
  white-space: nowrap;
  line-height: 1.1;
  height: 1.45em;
  font-size: 0.82em;
  vertical-align: baseline;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease, transform 120ms ease;
}

:deep(.am-quote:hover) {
  background: rgba(251, 191, 36, 0.18);
  border-color: rgba(251, 191, 36, 0.42);
}

:deep(.am-quote--warn) {
  background: rgba(244, 63, 94, 0.08);
  border-color: rgba(244, 63, 94, 0.35);
  color: rgba(136, 19, 55, 0.92);
}

:deep(.am-quote--notfound) {
  background: rgba(244, 63, 94, 0.12);
  border-color: rgba(244, 63, 94, 0.5);
}

:deep(.am-quote:active) {
  transform: scale(0.98);
}

:deep(.am-quote-label) {
  font-size: 0.65rem;
  line-height: 1rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(180, 83, 9, 0.75);
}

:deep(.am-quote-text) {
  max-width: 14rem;
  overflow: hidden;
  text-overflow: ellipsis;
}

:deep(.am-agent) {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.12em 0.55em;
  margin: 0 0.15rem;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.26);
  color: rgba(51, 65, 85, 0.95);
  font-style: normal;
  font-weight: 750;
  white-space: nowrap;
  line-height: 1.1;
  height: 1.45em;
  font-size: 0.82em;
  vertical-align: middle;
  transform: translateY(-0.06em);
}

:deep(.am-agent-dot) {
  width: 0.45em;
  height: 0.45em;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.95), rgba(56, 189, 248, 0.9));
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.12);
  flex: 0 0 auto;
}

:deep(.am-agent-text) {
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
}

.am-quote-popover {
  position: fixed;
  z-index: 60;
  width: 380px;
  max-width: calc(100vw - 24px);
  height: min(320px, calc(100vh - 24px));
  background: white;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 0.75rem;
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.12);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.am-quote-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(248, 250, 252, 0.75);
}

.am-quote-popover-header-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.am-quote-popover-title {
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(51, 65, 85, 0.85);
}

.am-quote-popover-close {
  font-size: 0.75rem;
  font-weight: 700;
  color: rgba(100, 116, 139, 0.9);
  padding: 0.25rem 0.5rem;
  border-radius: 0.5rem;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: white;
}

.am-quote-popover-close:hover {
  color: rgba(15, 23, 42, 0.9);
  border-color: rgba(100, 116, 139, 0.5);
}

.am-quote-popover-body {
  padding: 0;
  overflow: hidden;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.am-quote-popover-preview {
  max-height: none;
  overflow: auto;
  background: white;
  border-radius: 0;
  border: none;
  padding: 0.75rem;
  flex: 1;
  min-height: 0;
  box-sizing: border-box;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  touch-action: pan-y;
}

.am-quote-popover-action {
  font-size: 0.75rem;
  font-weight: 800;
  color: rgba(30, 64, 175, 0.9);
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.22);
  padding: 0.25rem 0.5rem;
  border-radius: 0.5rem;
}

.am-quote-popover-action:hover {
  background: rgba(59, 130, 246, 0.18);
  border-color: rgba(59, 130, 246, 0.35);
}

.am-quote-popover-empty {
  font-size: 0.85rem;
  color: rgba(100, 116, 139, 0.9);
  padding: 0.5rem 0.75rem;
  border-top: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(248, 250, 252, 0.7);
}

:deep(.am-quote-preview-hit) {
  outline: 2px dashed rgba(59, 130, 246, 0.8);
  outline-offset: -2px;
  border-radius: 0.5rem;
}

:global(.am-quote-locate-hit) {
  outline: 2px solid rgba(59, 130, 246, 0.85);
  outline-offset: -2px;
  border-radius: 0.5rem;
  background: rgba(59, 130, 246, 0.1);
}

:global(.am-quote-hit-overlay) {
  position: fixed;
  inset: 0;
  z-index: 80;
  pointer-events: none;
}

:global(.am-quote-hit-overlay-box) {
  position: fixed;
  background: rgba(59, 130, 246, 0.16);
  border: 2px solid rgba(59, 130, 246, 0.75);
  border-radius: 0.5rem;
  box-sizing: border-box;
  animation: am-quote-hit-fade 5.2s ease-out forwards;
}

:global(.am-quote-tip) {
  position: fixed;
  z-index: 90;
  max-width: min(320px, calc(100vw - 20px));
  padding: 0.5rem 0.7rem;
  border-radius: 0.65rem;
  background: rgba(15, 23, 42, 0.92);
  color: rgba(248, 250, 252, 0.98);
  font-size: 0.85rem;
  font-weight: 700;
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.28);
  opacity: 1;
  transform: translateY(0);
  transition: opacity 200ms ease, transform 200ms ease;
  pointer-events: none;
}

:global(.am-quote-tip--hide) {
  opacity: 0;
  transform: translateY(-4px);
}

@keyframes am-quote-hit-fade {
  0% {
    opacity: 1;
  }
  70% {
    opacity: 1;
  }
  100% {
    opacity: 0;
  }
}
</style>
