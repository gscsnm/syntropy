import type { AgentRole, Market } from "../types/alphaMind";

/**
 * 市场枚举：用于首页下拉选择与 Watchlist 展示
 */
export const MARKETS: Market[] = ["CN", "HK", "US"];

/**
 * 智能体在 UI 上的表现配置（颜色/标签/图标）
 *
 * 说明：
 * - `icon` 为 lucide 图标组件名（由 `LucideIcon` 进行映射）
 * - `color/bg` 用于 Tailwind class 拼接
 */
export const AGENT_CONFIG: Record<
  AgentRole,
  { color: string; bg: string; label: string; icon: string; desc: string }
> = {
  Manager: {
    color: "text-indigo-600",
    bg: "bg-indigo-50 border-indigo-200",
    label: "首席策略官",
    desc: "任务统筹与最终决策",
    icon: "BrainCircuit",
  },
  DataAnalyst: {
    color: "text-cyan-600",
    bg: "bg-cyan-50 border-cyan-200",
    label: "量化分析师",
    desc: "处理K线与技术指标",
    icon: "LineChart",
  },
  SentimentAnalyst: {
    color: "text-rose-600",
    bg: "bg-rose-50 border-rose-200",
    label: "舆情监控员",
    desc: "分析新闻与社交情绪",
    icon: "Newspaper",
  },
  RiskManager: {
    color: "text-amber-600",
    bg: "bg-amber-50 border-amber-200",
    label: "风控专家",
    desc: "评估下行风险与回撤",
    icon: "ShieldAlert",
  },
  Strategist: {
    color: "text-emerald-600",
    bg: "bg-emerald-50 border-emerald-200",
    label: "交易执行",
    desc: "制定具体买卖点位",
    icon: "Zap",
  },
};

/**
 * 模拟流式输出步骤（用于设计态演示）
 *
 * 说明：
 * - `content` 内允许使用 `{stock}` 占位符，启动分析时会替换为真实代码
 * - `metadata.tool` 仅用于 LiveStream 的“系统调用”展示
 */
export const MOCK_STREAM_STEPS = [
  { role: "Manager", type: "thought", content: "收到分析指令。正在拆解任务，首先需要获取市场基础数据和近期新闻面。" },
  { role: "Manager", type: "sub-agent-start", content: "启动多模态分析流程" },
  { role: "DataAnalyst", type: "thought", content: "开始获取 K 线数据，重点关注最近 3 个月的量价关系。" },
  {
    role: "DataAnalyst",
    type: "tool",
    content: 'Calling API: get_kline_data(symbol="{stock}", period="3m", indicators=["MA20", "RSI"])',
    metadata: { tool: "MarketDataAPI" },
  },
  { role: "DataAnalyst", type: "content", content: "数据获取成功。检测到股价在 MA20 均线附近获得支撑，RSI 指标处于 45 的中性区域，并未超买。" },
  { role: "SentimentAnalyst", type: "thought", content: "正在扫描全网舆情，检索关键词：财报、新产品、监管。" },
  {
    role: "SentimentAnalyst",
    type: "tool",
    content: 'Calling API: search_news(q="{stock} 财报 预测")',
    metadata: { tool: "WebSearch" },
  },
  { role: "SentimentAnalyst", type: "content", content: "发现 3 篇重磅研报。普遍预期下季度营收增长 15%。社交媒体情绪指数：正面 (0.72)。" },
  { role: "RiskManager", type: "thought", content: "正在评估下行风险，计算最大回撤。" },
  { role: "RiskManager", type: "content", content: "当前波动率处于历史低位。主要风险点在于下周的美联储议息会议可能带来的宏观扰动。" },
  { role: "Manager", type: "thought", content: "汇总各方信息。技术面支撑稳固，基本面预期向好，但需注意宏观风险。建议分批建仓。" },
  { role: "Manager", type: "report", content: "最终分析报告已生成。" },
] as const;
