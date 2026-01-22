# Implementation Plan: Agno + PyTauri Trading Agent

## 1. Project Configuration & Dependencies
- **Update `pyproject.toml`**:
  - Correct the entry point from `fintropy.ext_mod` to `syntropy.ext_mod` (or verify the correct rust extension name).
  - Add Python dependencies: `agno`, `yfinance` (for market data), `chromadb` (vector DB), `pandas`, `duckdb`.
- **Verify Rust Configuration**:
  - Ensure `src-tauri/src/lib.rs` exports the module expected by PyTauri.

## 2. Core Infrastructure (`src-tauri/src-python/syntropy/`)
- **`config.py`**:
  - Define `Settings` class for LLM keys (OpenAI/Anthropic/DeepSeek), API endpoints, and model selection (fast vs slow).
- **`models/`**:
  - `types.py`: Pydantic models for IPC (e.g., `AnalysisSpec`, `TaskStatus`, `AgentEvent`).
- **`live_context.py`**:
  - Implement `LiveContext` class as a singleton or global manager.
  - Manage active `Task` states.
  - Implement event buffering and `subscribe` mechanism using PyTauri Channels.

## 3. Data & Tools Layer (`syntropy/tools/`)
- **Interfaces**: Define protocol/abstract base classes for `MarketDataProvider`, `NewsProvider`.
- **Implementations**:
  - `market_data.py`: Implement `YFinanceProvider` for `get_market_data`, `get_ticker_info`.
  - `technicals.py`: Implement technical indicators (RSI, MACD, Bollinger Bands) using `pandas` / `ta-lib` (or manual calculation if ta-lib is heavy).
  - `news.py`: Implement simple news fetcher (e.g., via `duckduckgo-search` or `yfinance` news).

## 4. Agent & Team Definition (`syntropy/teams/` & `syntropy/agents/`)
- **Base Agents**: Create a configured `BaseAgent` with shared tools and memory.
- **Analyst Team**: `MarketAnalyst`, `NewsAnalyst`, `FundamentalsAnalyst`.
- **Research Team**: `BullResearcher`, `BearResearcher`, `ResearchManager`.
- **Risk Team**: `RiskManager`, `RiskyAgent`, `SafeAgent`.
- **Trader**: `TraderAgent`.

## 5. Workflow Orchestration (`syntropy/workflow.py`)
- **`AnalysisWorkflow`**:
  - Define the multi-step process: `Parallel Analysis` -> `Research Debate` -> `Trading Plan` -> `Risk Review` -> `Final Signal`.
  - Integrate with `LiveContext` to emit events at each step.

## 6. IPC Bridge (`syntropy/commands.py` & `__init__.py`)
- **`commands.py`**:
  - `start_analysis`: Initialize workflow, generate `task_id`, start background execution.
  - `stop_analysis`: Signal cancellation.
  - `get_live_context_snapshot`: Return event history.
  - `subscribe_to_live_context_output`: Stream events to frontend.
- **`__init__.py`**:
  - Register commands and start the PyTauri application.

## 7. Execution Strategy
- I will implement the backend logic step-by-step, starting with the `LiveContext` and `Models`, then `Tools`, `Agents`, `Workflow`, and finally wiring it up in `Commands`.
