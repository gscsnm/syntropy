import { computed, ref, reactive } from "vue";
import type { AnalysisTask, Market, WatchlistItem, PortfolioPosition, AgentRun } from "../types/alphaMind";
import { Channel } from "@tauri-apps/api/core";
import { startAnalysis as startAnalysisCommand, subscribeTaskEvents } from "../client/apiClient";
import { pyInvoke } from "tauri-plugin-pytauri-api";

/**
 * 设计稿的“轻量全局状态”
 *
 * 为什么不用 Pinia？
 * - 目前仓库没有引入 Pinia；为了减少额外依赖与迁移成本，这里使用模块级 `ref` 作为共享状态。
 * - 后续若需要更复杂的跨页面状态与调试能力，可无痛迁移到 Pinia（对外 API 尽量保持 action 风格）。
 */

const tasks = ref<AnalysisTask[]>([]);

const watchlist = ref<WatchlistItem[]>([
  { id: "1", stockCode: "NVDA", market: "US", periodicAnalysis: true },
  { id: "2", stockCode: "0700.HK", market: "HK", periodicAnalysis: false },
  { id: "3", stockCode: "600519", market: "CN", periodicAnalysis: true },
]);

const portfolio = ref<PortfolioPosition[]>([
  { stockCode: "AAPL", market: "US", quantity: 15, avgCost: 145, currentPrice: 178.5 },
  { stockCode: "BABA", market: "US", quantity: 50, avgCost: 85, currentPrice: 72.3 },
]);

/**
 * 当前“沉浸式查看”的任务 id（用于全局弹窗）
 */
const viewingTaskId = ref<string | null>(null);

function mapDbStatusToUi(status: string): AnalysisTask["status"] {
  switch (status) {
    case "running":
    case "pending":
      return "analyzing";
    case "completed":
      return "completed";
    case "failed":
      return "failed";
    case "stopped":
    case "cancelled":
      return "cancelled";
    default:
      return "analyzing";
  }
}

function toMillis(v: any): number | null {
  if (!v) return null;
  if (typeof v === "number") return v;
  const d = new Date(v);
  const ms = d.getTime();
  return Number.isFinite(ms) ? ms : null;
}

function parseTaskResultSnapshot(raw: any): AnalysisTask["result"] | null {
  if (!raw) return null;
  let snap: any = raw;
  if (typeof raw === "string") {
    try {
      snap = JSON.parse(raw);
    } catch {
      return { recommendation: "HOLD", confidence: 0, summary: String(raw) };
    }
  }
  const recommendation = snap?.recommendation;
  const confidence = snap?.confidence;
  const summary = snap?.summary;
  if (
    (recommendation === "BUY" || recommendation === "SELL" || recommendation === "HOLD") &&
    typeof confidence === "number" &&
    typeof summary === "string"
  ) {
    return { recommendation, confidence, summary };
  }
  const text =
    typeof snap?.result === "string"
      ? snap.result
      : typeof snap?.raw_run_completed_content === "string"
        ? snap.raw_run_completed_content
        : JSON.stringify(snap);
  return { recommendation: "HOLD", confidence: 0, summary: text };
}

function applyWorkflowPayload(targetTask: AnalysisTask, runMap: Map<string, AgentRun>, payload: any) {
  if (!payload) return;

  const { type, run_id, parent_run_id, agent_name, step_name, timestamp, data } = payload;

  if (type === "TaskResult") {
    const next = parseTaskResultSnapshot(data);
    if (next) targetTask.result = next;
    return;
  }

  const isRunScopedEvent =
    type === "RunContent" ||
    type === "RunCompleted" ||
    type === "RunError" ||
    type === "RunCancelled" ||
    type === "ToolCallStarted" ||
    type === "ToolCallCompleted" ||
    type === "ToolCallError";

  if (!targetTask.rootRuns) targetTask.rootRuns = [];

  if (isRunScopedEvent && run_id && !runMap.has(run_id)) {
    const newRun: AgentRun = reactive({
      id: run_id,
      parentId: parent_run_id,
      agentName: agent_name || step_name || "Agent",
      status: "running",
      children: [],
      startTime: timestamp,
      contents: [],
    });
    runMap.set(run_id, newRun);

    if (parent_run_id) {
      const parent = runMap.get(parent_run_id);
      if (parent) parent.children.push(newRun);
      else targetTask.rootRuns.push(newRun);
    } else {
      targetTask.rootRuns.push(newRun);
    }
  }

  const run = run_id ? runMap.get(run_id) : undefined;
  if (run) {
    if (type === "RunContent") {
      const addC = data?.content ?? "";
      const addR = data?.reasoning_content ?? "";
      if (addR) {
        const last = run.contents[run.contents.length - 1];
        if (!last || last.type !== "thinking") {
          run.contents.push({
            id: `${run.id}-thinking-${Date.now()}`,
            type: "thinking",
            text: addR,
            timestamp: timestamp ?? Date.now(),
          });
        } else {
          (last as any).text = ((last as any).text || "") + addR;
        }
      }
      if (addC) {
        const last = run.contents[run.contents.length - 1];
        if (!last || last.type !== "content") {
          run.contents.push({
            id: `${run.id}-content-${Date.now()}`,
            type: "content",
            text: addC,
            timestamp: timestamp ?? Date.now(),
          });
        } else {
          (last as any).text = ((last as any).text || "") + addC;
        }
      }
    } else if (type === "ToolCallStarted") {
      const toolData = data?.tool;
      if (toolData) {
        const existingToolItem = run.contents.find(
          (it) => it.type === "tool" && (it as any).tool.id === toolData.tool_call_id
        ) as any;
        const toolObj = {
          id: toolData.tool_call_id,
          name: toolData.tool_name,
          args: toolData.tool_args,
          status: "started" as const,
          startTime: toolData.created_at ? toolData.created_at * 1000 : Date.now(),
        };
        if (existingToolItem) {
          existingToolItem.tool = toolObj;
        } else {
          run.contents.push({
            id: `${run.id}-tool-${toolObj.id}`,
            type: "tool",
            tool: toolObj,
          });
        }
      }
    } else if (type === "ToolCallCompleted") {
      const toolData = data?.tool;
      if (toolData) {
        const toolItem = run.contents.find(
          (it) => it.type === "tool" && (it as any).tool.id === toolData.tool_call_id
        ) as any;
        if (toolItem) {
          toolItem.tool.status = "completed";
          toolItem.tool.result = toolData.result;
          toolItem.tool.endTime = Date.now();
        } else {
          run.contents.push({
            id: `${run.id}-tool-${toolData.tool_call_id}`,
            type: "tool",
            tool: {
              id: toolData.tool_call_id,
              name: toolData.tool_name,
              args: toolData.tool_args,
              status: "completed",
              result: toolData.result,
              startTime: toolData.created_at ? toolData.created_at * 1000 : Date.now(),
              endTime: Date.now(),
            },
          });
        }
      }
    } else if (type === "ToolCallError") {
      const toolData = data?.tool;
      const errorMsg = data?.error;
      if (toolData) {
        const toolItem = run.contents.find(
          (it) => it.type === "tool" && (it as any).tool.id === toolData.tool_call_id
        ) as any;
        if (toolItem) {
          toolItem.tool.status = "failed";
          toolItem.tool.error = errorMsg ?? toolData.error;
          toolItem.tool.endTime = Date.now();
        } else {
          run.contents.push({
            id: `${run.id}-tool-${toolData.tool_call_id}`,
            type: "tool",
            tool: {
              id: toolData.tool_call_id,
              name: toolData.tool_name,
              args: toolData.tool_args,
              status: "failed",
              error: errorMsg ?? toolData.error,
              startTime: toolData.created_at ? toolData.created_at * 1000 : Date.now(),
              endTime: Date.now(),
            },
          });
        }
      }
    } else if (type === "RunCompleted") {
      if (!run.contents.some((i) => i.type === "content")) {
        const addC = data?.content ?? "";
        if (addC) {
          run.contents.push({
            id: `${run.id}-content-${Date.now()}`,
            type: "content",
            text: addC,
            timestamp: timestamp ?? Date.now(),
          });
        }
      }
      if (!run.contents.some((i) => i.type === "thinking")) {
        const addR = data?.reasoning_content ?? "";
        if (addR) {
          run.contents.push({
            id: `${run.id}-thinking-${Date.now()}`,
            type: "thinking",
            text: addR,
            timestamp: timestamp ?? Date.now(),
          });
        }
      }
      run.status = "completed";
      run.endTime = timestamp ?? Date.now();
    } else if (type === "RunCancelled") {
      run.status = "cancelled";
      run.endTime = timestamp ?? Date.now();
    } else if (type === "RunError") {
      run.status = "failed";
      run.endTime = timestamp ?? Date.now();
    }
  }

  if (type === "WorkflowCompleted") {
    targetTask.status = "completed";
    targetTask.endTime = Date.now();
    for (const r of runMap.values()) {
      if (r.status === "running") {
        r.status = "completed";
        r.endTime = Date.now();
      }
    }
    if (!targetTask.result) {
      const runs = Array.from(runMap.values()).sort((a, b) => (a.startTime ?? 0) - (b.startTime ?? 0));
      const last = runs[runs.length - 1];
      const texts = last ? last.contents.filter((i: any) => i.type === "content").map((i: any) => i.text) : [];
      targetTask.result = {
        recommendation: "HOLD",
        confidence: 0,
        summary: texts.length ? texts.join("") : "分析完成",
      };
    }
  } else if (type === "WorkflowCancelled") {
    targetTask.status = "cancelled";
    targetTask.endTime = Date.now();
    for (const r of runMap.values()) {
      if (r.status === "running") {
        r.status = "cancelled";
        r.endTime = Date.now();
      }
    }
    if (!targetTask.result) {
      targetTask.result = { recommendation: "HOLD", confidence: 0, summary: "任务已取消" };
    }
  } else if (type === "WorkflowError") {
    targetTask.status = "failed";
    targetTask.endTime = Date.now();
    for (const r of runMap.values()) {
      if (r.status === "running") {
        r.status = "failed";
        r.endTime = Date.now();
      }
    }
    const errorMsg = data?.content || "未知错误";
    if (!targetTask.result) {
      targetTask.result = { recommendation: "HOLD", confidence: 0, summary: `分析失败: ${errorMsg}` };
    }
  }
}

async function ensureTaskHydrated(taskId: string) {
  const t = tasks.value.find((x) => x.id === taskId);
  if (!t) return;
  if (t.rootRuns && t.rootRuns.length > 0) return;

  let resp: any;
  try {
    resp = await pyInvoke("get_task_events", { task_id: taskId });
  } catch {
    return;
  }

  const events = Array.isArray(resp?.events) ? resp.events : [];
  const runMap = new Map<string, AgentRun>();
  for (const p of events) {
    applyWorkflowPayload(t, runMap, p);
  }
}

async function refreshTasks() {
  let resp: any;
  try {
    resp = await pyInvoke("get_analysis_tasks", { limit: 200, offset: 0 });
  } catch {
    return;
  }

  const rows = Array.isArray(resp?.tasks) ? resp.tasks : [];
  const existing = new Map(tasks.value.map((t) => [t.id, t] as const));
  const next: AnalysisTask[] = [...tasks.value];

  for (const r of rows) {
    const id = String(r?.task_id ?? "");
    if (!id) continue;

    let spec: any = null;
    try {
      spec = typeof r?.spec === "string" ? JSON.parse(r.spec) : r?.spec;
    } catch {
      spec = null;
    }
    const stockCode = String(spec?.symbols?.[0] ?? "").toUpperCase();
    const market = String(spec?.markets?.[0] ?? "US") as Market;
    const status = mapDbStatusToUi(String(r?.status ?? "running"));
    const startTime = toMillis(r?.created_at) ?? Date.now();
    const endTime = toMillis(r?.completed_at) ?? undefined;
    const companyName = String(r?.company_name ?? "").trim() || undefined;

    const existingTask = existing.get(id);
    if (existingTask) {
      existingTask.stockCode = stockCode || existingTask.stockCode;
      existingTask.companyName = companyName ?? existingTask.companyName;
      existingTask.market = (market as any) || existingTask.market;
      existingTask.status = status;
      existingTask.startTime = startTime;
      existingTask.endTime = endTime;
      if (!existingTask.result && r?.result_snapshot != null) {
        const parsed = parseTaskResultSnapshot(r.result_snapshot);
        if (parsed) existingTask.result = parsed;
      }
      continue;
    }

    const newTask: AnalysisTask = reactive({
      id,
      stockCode: stockCode || id.substring(0, 6),
      companyName,
      market: (market as any) || "US",
      status,
      startTime,
      endTime,
      logs: [],
      rootRuns: [],
    });

    if (r?.result_snapshot != null) {
      const parsed = parseTaskResultSnapshot(r.result_snapshot);
      if (parsed) newTask.result = parsed;
    }

    next.push(newTask);
  }

  next.sort((a, b) => (b.startTime ?? 0) - (a.startTime ?? 0));
  tasks.value = next;
}


function openTask(taskId: string) {
  viewingTaskId.value = taskId;
  void (async () => {
    await refreshTasks();
    await ensureTaskHydrated(taskId);
  })();
}

function closeTask() {
  viewingTaskId.value = null;
}

function removeWatchlistItem(itemId: string) {
  watchlist.value = watchlist.value.filter((i) => i.id !== itemId);
}

function addWatchlistItem(item: Omit<WatchlistItem, "id">) {
  const id = Date.now().toString();
  watchlist.value = [{ ...item, id }, ...watchlist.value];
}

function withTask(taskId: string, updater: (task: AnalysisTask) => void) {
  const t = tasks.value.find((x) => x.id === taskId);
  if (!t) return;
  updater(t);
}


/**
 * 启动一次“设计态分析任务”
 *
 * 说明：
 * - 当前仅用于前端演示，会按固定步骤写入日志；
 * - 后续接入后端流式推送时，可以复用 task/log 的数据结构，只替换日志来源。
 */
async function startAnalysis(market: Market, stockCodeRaw: string) {
  const stockCode = stockCodeRaw.trim().toUpperCase();
  if (!stockCode) return;

  const mappedMarket = market;    
  const spec = {
    symbols: [stockCode],
    markets: [mappedMarket],
  } as const;

  let taskId = "";
  try {
    const resp = await startAnalysisCommand(spec as any);
    taskId = resp.task_id;
  } catch {
    return;
  }

  const newTask: AnalysisTask = reactive({
    id: taskId,
    stockCode,
    companyName: undefined,
    market,
    status: "analyzing",
    startTime: Date.now(),
    logs: [],
    rootRuns: [],
  });

  tasks.value = [newTask, ...tasks.value];
  openTask(taskId);

  // Map to track runs for O(1) access
  const runMap = new Map<string, AgentRun>();

  const channel = new Channel<any>((msg: any) => {
    try {
        let payload: any | null = null;
        if (typeof msg === "string") {
          payload = JSON.parse(msg);
        } else if (msg && typeof (msg as any).data === "string") {
          payload = JSON.parse((msg as any).data);
        } else if (msg && typeof (msg as any).data === "object") {
          payload = (msg as any).data;
        } else {
          return;
        }
        if (!payload) return;
        withTask(taskId, (t) => {
          applyWorkflowPayload(t, runMap, payload);
        });

    } catch (e) {
        console.error("Error parsing event", e);
    }
  });

  try {
    await subscribeTaskEvents({ channel, task_id: taskId } as any);
  } catch {
  }
}

const viewingTask = computed(() => {
  if (!viewingTaskId.value) return null;
  return tasks.value.find((t) => t.id === viewingTaskId.value) ?? null;
});

export function useAlphaMindStore() {
  return {
    tasks,
    watchlist,
    portfolio,
    viewingTask,
    openTask,
    closeTask,
    refreshTasks,
    startAnalysis,
    removeWatchlistItem,
    addWatchlistItem,
  };
}
