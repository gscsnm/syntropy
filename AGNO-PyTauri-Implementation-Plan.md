# Agno + PyTauri 桌面应用实施架构规划

## 目标与范围
- 构建一个跨平台桌面应用，采用 `pytauri` 作为桌面容器与 IPC 桥接，Python 侧运行多智能体系统。
- 使用 Agno 的 Agents、Teams、Workflows 组织智能体编排；可在本地运行，具备持久化会话、记忆与知识管理能力。
- 支持多市场与多货币：A股(A-share)、美股(US)、港股(HK)；提供统一的通过接收市场ID获取符号与货币、交易日历与时区处理的函数。
- 分析的核心是一条 agno 的 Workflows 按照顺序进行步骤: 分析师团队(市场分析师、社媒/情绪分析师、新闻分析师、基本面分析师) -> 研究团队(多头研究员、空头研究员 进行多轮辩论，最后由 研究经理裁决并给出交易计划) -> 交易员(生成交易方案与最终建议) -> 风险管理团队 (激进/保守/中立分析师三方辩论, 风险裁判综合并给出最终交易决策)
- 引入贯穿分析任务全生命周期的 `LiveContext`，LiveContext 托管每个任务的工作流的执行与停止并转发所有正在运行的工作流吐出的事件，以供查询、回访与订阅。
- 忽略供应商，实现工具的抽象契约（接口定义、输入参数、输出结构）；后续可按市场/数据源适配不同实现。

## 高层架构
- 桌面前端（Tauri）
  - 通过 `pytauri.Commands` 自动生成 TypeScript 客户端调用 Python 命令。
  - 监听全局事件以增量渲染分析直播（列表流、进度面板、报告区块、工具调用视图）。
- Python 后端（PyTauri）
  - 命令注册与 IPC：`src-tauri/src-python/app/commands.py`，所有命令使用 `async`，阻塞函数用 `async_tools.to_async` 包装。
  - 事件系统：使用 `Emitter.emit` 触发前端全局事件（遵循 pytauri 规则）。
- Agno 运行时（本地）
  - Agents 与 Teams：按分析阶段进行职责划分（分析师团队、研究团队、交易员Agent、风险团队、风险裁决与汇总Agent）。
  - Workflows：编排有条件分支与循环（多市场并行 → 汇总 → 辩论 → 裁决 → 风险 → 最终信号）。
  - 会话与记忆：`SqliteDb` 管理会话与运行记录；矢量记忆/知识库可使用 `ChromaDb`。
- 多市场与多货币支持
  - 市场、货币、时区、交易日历、符号映射与归一化；统一数据模型与工具契约。

## 目录结构（建议）
- `src-tauri/src-python/app/`
  - `commands.py`：命令注册（start/stop/snapshot/subscribe 等）
  - `live_context.py`：LiveContext 模型、事件转发
  - `workflow.py`：Agno Workflow 入口、编排逻辑（并行、条件、循环）
  - `teams/`：团队组装（AnalystTeam、ResearchTeam、RiskTeam、TradingTeam、Coordinator）
  - `agents/`：各智能体定义（职责、模型、工具）
  - `tools/`：工具契约与适配层（无供应商实现）
  - `models/`：通用数据模型（Instrument、Market、Currency、Report 等）
  - `utils.py`：通用工具函数（日期处理、货币转换、符号等）
  - `config.py`：全局配置（快速、慢速 LLM模型配置: 模型名称、API URL、API 密钥、温度），tips: 需要同时配置快速跟慢速模型，因为在分析过程中会根据需要切换模型。
- `src/client/`：由 `pytauri-gen-ts` 自动生成的 TS 客户端（无需手写）
- `app_data/`：开发使用的本地缓存与 DB 文件（SQLite、向量库）目录，创建公用的目录路径获取函数，区分开发与分发，在开发环境使用项目根目录的 app_data 文件夹，否则通过 pytauri 的函数来获取应用的数据目录

## LiveContext 设计
- LiveContext 概述
  - LiveContext，贯穿分析全过程。在底层设计上 LiveContext 托管所有的任务工作流并负责转发工作流吐出的事件，对外则提供对应任务的事件快照供回放与任务的实时事件订阅。工作流是后台运行的，不阻塞进程。
  - 提供快照（Snapshot）与事件订阅（Streaming） 方法。
  - 全局单例或函数优先设计

- 前端订阅
  - 使用 Tauri Channel监听，事件载荷即 LiveContext 增量事件，前端累积到本地 store 渲染。

## PyTauri 命令（IPC）
- `start_analysis(body: {spec: AnalysisSpec}) -> {task_id}`
  - 说明：启动一次多市场分析任务，创建任务到数据库，创建 Workflow 并将任务ID作为session ID， LiveContext 托管执行工作流。事件由 agno的工作流自行处理持久化。
  - 输入：`markets: [CN|HK|US]`、`symbol: [string] 股票名称 or 代码`、`research_depth: low|medium|high`、`options`
  - 输出：`task_id`（字符串）
- `stop_analysis(body: {task_id: str}) -> {status}`
  - 说明：通过 LiveContext 停止/取消运行中的任务。
  - 输入：`task_id`
  - 输出：`status: "stopped"|...`
- `get_live_context_snapshot(body: {task_id: str}) -> events`
  - 说明：拉取指定任务的事件快照。已完成的任务通过 Agno 本身的能力来拉取，运行中的任务则通过 LiveContext 来拉取托管的工作流事件列表。
  - 输入：`task_id`
  - 输出：events 是指定任务的事件数组。
- `subscribe_to_live_context_output(body: {channel: JavaScriptChannelId[Msg],task_id: str},webview_window: WebviewWindow) -> None`
  - 说明：订阅指定任务的事件流。已完成的任务通过 Agno 本身的能力来拉取，运行中的任务则通过 LiveContext 来拉取托管的工作流事件列表。
  - 输入：`task_id` 以及 `channel: JavaScriptChannelId[Msg]`
  - 输出：None,系统通过 ```
    channel: Channel[Msg] = body.channel_on(webview_window.as_ref_webview())

    # 👇 you should do this as background task, here just keep it simple as a example
    channel.send_model(Msg("message"))
    ``` 方式来向前端推送事件

- `list_tasks(filter?) -> [{task_id, created_at, status}]`
  - 说明：从数据库中获取任务列表与状态。
  - 输入：过滤参数（可选）
  - 输出：任务概览数组

...... 任务的删除函数（从数据库删除，如果有在运行还需要在内存中停止并删除）

## 数据工具契约（忽略供应商）
- 市场数据
  - `get_market_data(symbol, market, start_date, end_date, interval)`
    - 入参：`symbol: str`、`market: "CN"|"US"|"HK"|"CRYPTO"`、`start_date: YYYY-MM-DD`、`end_date: YYYY-MM-DD`、`interval: 1m/5m/1d/...`
    - 出参：`OHLCV[]`（`[{time, open, high, low, close, volume}]`）
- 技术指标
  - `get_indicator_timeseries(symbol, market, indicator_id, params, start_date, end_date)`
    - 入参：`indicator_id: "rsi"|"macd"|"boll_lb"|...`、`params: object`
    - 出参：`[{time, value}]` 或多列时 `[{time, v1, v2, v3}]`
- 基本面数据
  - `get_fundamentals(symbol, market, as_of_date)`
    - 入参：`as_of_date`
    - 出参：公司关键指标字典（PE、PS、现金流、负债、收入增长等）
  - `get_balance_sheet(symbol, market, freq, as_of_date)`
  - `get_cashflow(symbol, market, freq, as_of_date)`
  - `get_income_statement(symbol, market, freq, as_of_date)`
    - 入参：`freq: "annual"|"quarterly"`、`as_of_date`
    - 出参：结构化报表（字段-值列表或表格）
- 新闻与情绪
  - `get_company_news(query_or_symbol, market, start_date, end_date, limit)`
    - 出参：`[{title, source, published_at, summary, url}]`
  - `get_global_news(as_of_date, look_back_days, limit, locale)`
    - 出参：同上，偏宏观主题
  - `get_insider_sentiment(symbol, market, as_of_date)`
  - `get_insider_transactions(symbol, market, as_of_date)`
    - 出参：结构化数据列表（时间、人名、变动、交易价与代码等）


## Agents 与 Teams（Agno）
- 分析师团队（Analyst Team）
  - `MarketAnalystAgent`：选择与调用技术指标；撰写技术面报告（多市场、多货币归一化）。
  - `NewsSentimentAgent`：公司新闻与社媒情绪分析；撰写情绪报告。
  - `MacroNewsAgent`：宏观新闻分析；撰写宏观报告。
  - `FundamentalsAnalystAgent`：基本面与财报分析；撰写基本面报告。
- 研究团队（Research Team）
  - `BullResearcherAgent` / `BearResearcherAgent`：基于报告与记忆进行多轮辩论（根据研究深度参数 `research_depth` 进行轮数限制， low 研究深度对应 1 轮，medium 研究深度对应 3 轮，high 研究深度对应 5 轮）。
  - `ResearchManagerAgent`：裁决与合并投资计划（明确 BUY/SELL/HOLD 倾向与执行建议）。
- 交易员（Trading Agent）
  - `TraderAgent`：将研究计划转化为交易方案与执行细节（仓位、入场、风控）。
- 风险团队（Risk Team）
  - `RiskyAgent` / `NeutralAgent` / `SafeAgent`：三方风险辩论与修正。
- 风险裁决员
  - `RiskManagerAgent`：综合风险报告与裁决最终交易决策。


## Workflow（编排）
- 阶段与控制流
  - 阶段一（并行）：对 `symbols × markets` 进行分析师团队任务，产出四类报告。
  - 阶段二（研究辩论）：Bull↔Bear 回合轮换，至上限后进入研究经理裁决与投资计划。
  - 阶段三（交易方案）：Trader 生成方案。
  - 阶段四（风险辩论）：Risky→Safe→Neutral 回合轮换，至上限后风险经理裁决给出最终报告。
  - 阶段五（信号抽取）：使用一个简单的LLM从最终报告中生成核心信号(持有、购买、出售)并思考给出未来观测时间(未来观测时间用于在未来时间点在真实市场中观察并验证报告的正确性)。
- 条件与循环
  - 工作流支持并行、条件路由与回合计数。

## 观测与日志
- 命令与异常
  - 所有命令与工具调用记录到本地日志；异常日志使用 `exc_info=True`（与项目规则一致）。

## 安全与隐私
- 所有数据本地运行；不将会话与知识外发。
- 密钥与配置仅在本机存储；前端不暴露敏感信息。

