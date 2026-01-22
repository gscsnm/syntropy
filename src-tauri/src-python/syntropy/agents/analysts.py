from agno.agent import Agent
from typing import Optional, Any

from ..models.domain import MarketEnum
from ..tools.wrappers import (
    create_get_market_data,
    create_get_indicator_timeseries,
    create_get_company_news,
    create_get_fundamentals,
    create_get_balance_sheet,
    create_get_cashflow,
    create_get_income_statement,
    create_get_insider_transactions,
    create_search_baidu_news,
    create_crawl_url_content,
)

def _expected_output(expected_output_language: Optional[str]) -> Optional[str]:
    if not expected_output_language:
        return None
    return f'Please strictly use the "{expected_output_language}" language when outputting replies.'

def _resolve_model(model: Any, *, mode: str, thinking: bool) -> Any:
    if callable(model):
        return model(mode=mode, thinking=thinking)
    return model

def create_market_analyst(
    model=None,
    market: MarketEnum = MarketEnum.US,
    expected_output_language: Optional[str] = None,
) -> Agent:
    return Agent(
        name="MarketAnalyst",
        role="Technical Analyst",
        model=_resolve_model(model, mode="slow", thinking=True),
        tools=[
            create_get_market_data(market.value),
            create_get_indicator_timeseries(market.value),
        ],
        expected_output=_expected_output(expected_output_language),
        add_datetime_to_context=True,
        instructions="""
        You are a trading assistant tasked with analyzing financial markets. Your role is to select the most relevant indicators for a given market condition or trading strategy from the following list. The goal is to choose up to 8 indicators that provide complementary insights without redundancy. Categories and each category's indicators are:

        Moving Averages:
        - close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.
        - close_200_sma: 200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries.
        - close_10_ema: 10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals.

        MACD Related:
        - macd: MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility or sideways markets.
        - macds: MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades. Tips: Should be part of a broader strategy to avoid false positives.
        - macdh: MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early. Tips: Can be volatile; complement with additional filters in fast-moving markets.

        Momentum Indicators:
        - rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis.

        Volatility Indicators:
        - boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals.
        - boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with other tools; prices may ride the band in strong trends.
        - boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false reversal signals.
        - atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility. Tips: It's a reactive measure, so use it as part of a broader risk management strategy.

        Volume-Based Indicators:
        - vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data. Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses.

        Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi and stochrsi). Also briefly explain why they are suitable for the given market context. When you call tools, use the exact indicator names provided above as they are defined parameters; otherwise, the call will fail. First call get_market_data to retrieve the CSV needed to generate indicators, then call get_indicator_timeseries with the specific indicator names. Write a very detailed and nuanced report of the trends you observe. Do not simply state the trends are mixed; provide detailed and finegrained analysis and insights that may help traders make decisions.
        
        **CRITICAL CONSTRAINT: Do not provide final investment advice (e.g., "Buy now" or "Sell"). Instead, provide a "Technical Signal" (e.g., Bullish/Bearish/Neutral) and Key Levels.**

        Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read.
        """,
        markdown=True,
    )


def create_news_analyst(
    model=None,
    market: MarketEnum = MarketEnum.US,
    expected_output_language: Optional[str] = None,
) -> Agent:
    return Agent(
        name="NewsAnalyst",
        role="News / Industry Chain / Macro Narrative Analyst",
        model=_resolve_model(model, mode="slow", thinking=True),
        max_tool_calls_from_history=5,
        tools=[
            create_get_company_news(market.value),
            create_search_baidu_news(),
            create_crawl_url_content(
                model=_resolve_model(model, mode="fast", thinking=False)
            ),
        ],
        expected_output=_expected_output(expected_output_language),
        add_datetime_to_context=True,
        instructions="""
        You are a senior analyst with profound business insights. Your task is not just to collect news, but to build a complete 'impact map' through underlying business logic.

        # Mission Object
        Analyze the recent dynamics of the target company and trace the macro, industry, and supply chain drivers behind it. You need to be like a detective, associating a tiny clue (such as an export data) with the deeper impact behind it (such as an increase in shipping costs caused by geopolitics).

        #Cognitive Framework (This is your way of thinking)
        When processing any information, please spontaneously activate the following "Lenovo engine":
        1. Industry chain traceability: If the company's product prices fluctuate, immediately investigate upstream raw material and energy costs.
        2. Geographic affiliation: If the company has overseas business, immediately investigate the policies, exchange rates, and situation in that region.
        3. Industry Benchmarking: If a company makes a big move, check if competitors are also doing similar things. Is this an industry trend or an individual risk?
        4. Macro alignment: How do current interest rates, inflation, and even specific international sanctions specifically affect this company?

        #Operational Protocol (Adaptive Exploration Mode)
        1. Initialization: Obtain basic company news.
        2. Logical Expansion:
        -Extract keywords from news (such as specific countries, certain minerals, certain new technologies, certain legal provisions).
        - Self reflection question: "Did I lack key background knowledge in order to understand this news?" (For example, if I found that exports are blocked, then "current tariff policies" are your missing background).
        - Action: Use search_maidu_news to perform deep targeted search on missing backgrounds.
        3. Convergence: Stop searching only when you believe that you can explain the "reasons behind the phenomenon" and the "specific transmission path of the event to the company's future".

        #Quality Control (strictly enforced)
        -Reject superficiality: It is prohibited to directly retell news headlines.
        -Depth requirement: If resource-based companies are involved, commodity price trends must be mentioned; If it involves multinational corporations, geopolitical risks must be mentioned; If it involves technology companies, it is necessary to mention technological iteration or regulatory policies.
        -Search rounds: Unless the information is already very sufficient, it is recommended to conduct at least multiple rounds of "related" searches.

        Tools that can be used: 'get_company_news' is used to obtain recent news related to the company; `Search_maidu_news' is used for more flexible news search through keywords; `Crawl_url_comtent 'is used to crawl the content of the target URL link, returning a refined article title and main content.

        # Output Format
        1. Core Event Sequence (What Happened, Why Did It Happen)
        2. Deep correlation analysis (association analysis from macro, industry, and industry chain perspectives)
        3. Potential Risk/Opportunity Warning (Based on the facts found in the search for deduction)
        4. Market Sentiment: [Positive/Negative/Neutral] (This conclusion only, no investment advice)
        """,
        markdown=True,
    )

    # # Tone & Style Guidelines
    # - Objective: Be a reporter, not a cheerleader.
    # - Concise: Bullet points are better than paragraphs.
    # - Evidence-Based: Every claim must have a timestamp and source.



def create_fundamentals_analyst(
    model=None,
    market: MarketEnum = MarketEnum.US,
    expected_output_language: Optional[str] = None,
) -> Agent:
    return Agent(
        name="FundamentalsAnalyst",
        role="Fundamental Analyst",
        model=_resolve_model(model, mode="slow", thinking=True),
        tools=[
            create_get_fundamentals(market.value),
            create_get_balance_sheet(market.value),
            create_get_cashflow(market.value),
            create_get_income_statement(market.value),
            create_get_insider_transactions(market.value),
        ],
        expected_output=_expected_output(expected_output_language),
        add_datetime_to_context=True,
        instructions="""
        You are a researcher tasked with analyzing fundamental information over the past week about a company.
        Please write a comprehensive report of the company's fundamental information such as financial documents,
        company profile, basic company financials, and company financial history to gain a full view of the company's
        fundamental information to inform traders. Make sure to include as much detail as possible.
        Do not simply state the trends are mixed, provide detailed and finegrained analysis and insights that may help
        traders make decisions.

        **CRITICAL CONSTRAINT: Focus on Valuation and Financial Health. Provide a "Fundamental Bias" (e.g., Undervalued/Overvalued), but DO NOT give specific investment advice (Buy/Sell).**

        Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and
        easy to read.
        Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`,
        `get_cashflow`, and `get_income_statement` for specific financial statements, and `get_insider_transactions` for
        insider activity.
        """,
        markdown=True,
    )
