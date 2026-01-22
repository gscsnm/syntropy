/**
 * AlphaMind 设计稿相关的领域模型（纯类型定义）
 *
 * 说明：
 * - 这些类型是从 `/src/design/App.tsx` 的 UI 行为抽象出来的；
 * - 目前属于“设计态/演示态”数据模型，后续接入真实后端时可以逐步替换字段。
 */

export type Market = "CN" | "HK" | "US";

export type AgentRole = "Manager" | "DataAnalyst" | "SentimentAnalyst" | "RiskManager" | "Strategist";

export type AgentLogType = "thought" | "tool" | "content" | "report" | "sub-agent-start";

export interface AgentLogMetadata {
  /**
   * 仅用于展示：描述“系统调用”的工具名称（例如 MarketDataAPI/WebSearch）。
   */
  tool?: string;
  [key: string]: unknown;
}

export interface AgentLog {
  id: string;
  timestamp: number;
  role: AgentRole;
  type: AgentLogType;
  content: string;
  metadata?: AgentLogMetadata;
}

export interface AgentToolCall {
  id: string;
  name: string;
  args: any;
  status: "started" | "completed" | "failed";
  result?: any;
  error?: any;
  startTime: number;
  endTime?: number;
}

export type AgentContentItemType = "thinking" | "content" | "tool";

export type AgentContentItem =
  | {
      id: string;
      type: "thinking" | "content";
      text: string;
      timestamp: number;
    }
  | {
      id: string;
      type: "tool";
      tool: AgentToolCall;
    };

export interface AgentRun {
  id: string; // run_id
  parentId: string | null;
  agentName: string;
  status: "running" | "completed" | "failed" | "cancelled";
  children: AgentRun[]; // Nested runs
  startTime: number;
  endTime?: number;
  contents: AgentContentItem[];
}

export type Recommendation = "BUY" | "SELL" | "HOLD";

export interface AnalysisResult {
  recommendation: Recommendation;
  confidence: number;
  summary: string;
}

export interface AnalysisTask {
  id: string;
  stockCode: string;
  companyName?: string;
  market: Market;
  status: "analyzing" | "completed" | "failed" | "cancelled";
  startTime: number;
  endTime?: number;
  logs: AgentLog[];
  rootRuns: AgentRun[]; // New structured data
  result?: AnalysisResult;
}

export interface WatchlistItem {
  id: string;
  stockCode: string;
  market: Market;
  periodicAnalysis: boolean;
}

export interface PortfolioPosition {
  stockCode: string;
  market: Market;
  quantity: number;
  avgCost: number;
  currentPrice: number;
}
