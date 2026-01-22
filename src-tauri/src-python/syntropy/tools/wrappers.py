import logging
import traceback
from typing import Callable, Dict, List

from .fundamentals import (
    get_fundamentals_by_akshare,
    get_balance_sheet_by_akshare,
    get_cashflow_by_akshare,
    get_income_statement_by_akshare,
    get_insider_transactions_by_akshare,
)
from .market_data import (
    get_market_data_by_akshare,
    get_indicator_timeseries_by_akshare,
)
from .news import get_company_news_by_ddgs, get_company_news_by_akshare, get_global_news


MarketType = str

logger = logging.getLogger(__name__)


def _is_unsuccessful_result(result: object) -> bool:
    if not isinstance(result, str):
        return False
    text = result.strip()
    if not text:
        return True
    lowered = text.lower()
    error_prefixes = (
        "error ",
        "error:",
        "error fetching",
        "error calculating",
    )
    if lowered.startswith(error_prefixes):
        return True
    no_data_prefixes = (
        "no data",
        "no news found",
    )
    if lowered.startswith(no_data_prefixes):
        return True
    return False


def _first_success(funcs: List[Callable], *args, **kwargs) -> str:
    def _summarize_value(value: object, max_len: int = 200) -> str:
        if value is None:
            return "None"
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, str):
            text = value.replace("\n", "\\n")
            if len(text) <= max_len:
                return text
            return f"{text[:max_len]}...(len={len(text)})"
        return f"<{type(value).__name__}>"

    def _summarize_call(max_items: int = 8) -> str:
        summarized_args = [_summarize_value(v) for v in args[:max_items]]
        extra_args = len(args) - len(summarized_args)
        if extra_args > 0:
            summarized_args.append(f"...(+{extra_args} args)")
        summarized_kwargs_items = list(kwargs.items())[:max_items]
        summarized_kwargs = {k: _summarize_value(v) for k, v in summarized_kwargs_items}
        extra_kwargs = len(kwargs) - len(summarized_kwargs_items)
        if extra_kwargs > 0:
            summarized_kwargs["..."] = f"+{extra_kwargs} kwargs"
        return f"args={summarized_args}, kwargs={summarized_kwargs}"

    last_error = None
    last_unsuccessful_text = None
    call_summary = _summarize_call()
    for func in funcs:
        func_name = getattr(func, "__name__", repr(func))
        try:
            result = func(*args, **kwargs)
            if _is_unsuccessful_result(result):
                last_unsuccessful_text = str(result)
                logger.warning(
                    "Wrapper fallback returned unsuccessful result (%s) for %s: %s",
                    func_name,
                    call_summary,
                    _summarize_value(str(result), max_len=500),
                )
                continue
            return str(result)
        except Exception as e:
            last_error = e
            logger.error(
                "Wrapper fallback raised exception (%s) for %s: %s\n%s",
                func_name,
                call_summary,
                str(e),
                traceback.format_exc(),
            )
            continue
    if last_unsuccessful_text is not None:
        return last_unsuccessful_text
    if last_error is not None:
        raise last_error
    return "No implementation functions provided."


def create_get_fundamentals(market: MarketType):
    market_map: Dict[MarketType, List[Callable]] = {
        "US": [get_fundamentals_by_akshare],
        "HK": [get_fundamentals_by_akshare],
        "CN": [get_fundamentals_by_akshare],
        "CRYPTO": [get_fundamentals_by_akshare],
        "default": [get_fundamentals_by_akshare],
    }
    impls = market_map.get(market, market_map["default"])

    def get_fundamentals(symbol: str) -> str:
        """
        Get general fundamental info for a company.

        Args:
            symbol: Stock symbol.

        Returns:
            String summary of fundamentals.
        """

        return _first_success(impls, symbol)

    return get_fundamentals


def create_get_balance_sheet(market: MarketType):
    market_map: Dict[MarketType, List[Callable]] = {
        "US": [get_balance_sheet_by_akshare],
        "HK": [get_balance_sheet_by_akshare],
        "CN": [get_balance_sheet_by_akshare],
        "CRYPTO": [get_balance_sheet_by_akshare],
        "default": [get_balance_sheet_by_akshare],
    }
    impls = market_map.get(market, market_map["default"])

    def get_balance_sheet_wrapper(symbol: str, freq: str = "quarterly") -> str:
        """
        Get balance sheet.

        Args:
            symbol: Stock symbol.
            freq: 'annual' or 'quarterly'.
        """

        return _first_success(impls, symbol, freq)

    get_balance_sheet_wrapper.__name__ = "get_balance_sheet"
    return get_balance_sheet_wrapper


def create_get_cashflow(market: MarketType):
    market_map: Dict[MarketType, List[Callable]] = {
        "US": [get_cashflow_by_akshare],
        "HK": [get_cashflow_by_akshare],
        "CN": [get_cashflow_by_akshare],
        "CRYPTO": [get_cashflow_by_akshare],
        "default": [get_cashflow_by_akshare],
    }
    impls = market_map.get(market, market_map["default"])

    def get_cashflow_wrapper(symbol: str, freq: str = "quarterly") -> str:
        """Get cash flow statement."""

        return _first_success(impls, symbol, freq)

    get_cashflow_wrapper.__name__ = "get_cashflow"
    return get_cashflow_wrapper


def create_get_income_statement(market: MarketType):
    market_map: Dict[MarketType, List[Callable]] = {
        "US": [get_income_statement_by_akshare],
        "HK": [get_income_statement_by_akshare],
        "CN": [get_income_statement_by_akshare],
        "CRYPTO": [get_income_statement_by_akshare],
        "default": [get_income_statement_by_akshare],
    }
    impls = market_map.get(market, market_map["default"])

    def get_income_statement_wrapper(symbol: str, freq: str = "quarterly") -> str:
        """Get income statement."""

        return _first_success(impls, symbol, freq)

    get_income_statement_wrapper.__name__ = "get_income_statement"
    return get_income_statement_wrapper


def create_get_insider_transactions(market: MarketType):
    market_map: Dict[MarketType, List[Callable]] = {
        "US": [get_insider_transactions_by_akshare],
        "HK": [get_insider_transactions_by_akshare],
        "CN": [get_insider_transactions_by_akshare],
        "CRYPTO": [get_insider_transactions_by_akshare],
        "default": [get_insider_transactions_by_akshare],
    }
    impls = market_map.get(market, market_map["default"])

    def get_insider_transactions_wrapper(symbol: str) -> str:
        """Get recent insider transactions."""

        return _first_success(impls, symbol)

    get_insider_transactions_wrapper.__name__ = "get_insider_transactions"
    return get_insider_transactions_wrapper


def create_get_market_data(market: MarketType):
    market_map: Dict[MarketType, List[Callable]] = {
        "US": [get_market_data_by_akshare],
        "HK": [get_market_data_by_akshare],
        "CN": [get_market_data_by_akshare],
        "CRYPTO": [get_market_data_by_akshare],
        "default": [get_market_data_by_akshare],
    }
    impls = market_map.get(market, market_map["default"])

    def get_market_data_wrapper(
        symbol: str, start_date: str, end_date: str, interval: str = "1d"
    ) -> str:
        """
        Get historical market data for a given symbol.

        Args:
            symbol: The stock symbol (e.g., 'AAPL').
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            interval: Data interval (e.g., '1d', '1h', '5m').

        Returns:
            CSV string of the market data.
        """

        return _first_success(impls, symbol, start_date, end_date, interval)

    get_market_data_wrapper.__name__ = "get_market_data"
    return get_market_data_wrapper


def create_get_indicator_timeseries(market: MarketType):
    market_map: Dict[MarketType, List[Callable]] = {
        "US": [get_indicator_timeseries_by_akshare],
        "HK": [get_indicator_timeseries_by_akshare],
        "CN": [get_indicator_timeseries_by_akshare],
        "CRYPTO": [get_indicator_timeseries_by_akshare],
        "default": [get_indicator_timeseries_by_akshare],
    }
    impls = market_map.get(market, market_map["default"])

    def get_indicator_timeseries_wrapper(
        symbol: str, indicator_id: str, start_date: str, end_date: str
    ) -> str:
        """
        Get technical indicator timeseries.
        Currently supports:
        - close_50_sma, close_200_sma, close_10_ema
        - macd, macds, macdh
        - rsi
        - boll, boll_ub, boll_lb
        - atr
        - vwma
        Also accepts legacy aliases: sma_50, sma_200, ema_10, bollinger.

        Args:
            symbol: Stock symbol.
            indicator_id: ID of the indicator.
            start_date: Start date YYYY-MM-DD.
            end_date: End date YYYY-MM-DD.

        Returns:
            String description of indicator values.
        """

        return _first_success(impls, symbol, indicator_id, start_date, end_date)

    get_indicator_timeseries_wrapper.__name__ = "get_indicator_timeseries"
    return get_indicator_timeseries_wrapper


def create_get_company_news(market: MarketType):
    market_map: Dict[MarketType, List[Callable]] = {
        "US": [get_company_news_by_ddgs],
        "HK": [get_company_news_by_ddgs],
        "CN": [get_company_news_by_akshare, get_company_news_by_ddgs],
        "CRYPTO": [get_company_news_by_ddgs],
        "default": [get_company_news_by_ddgs],
    }
    impls = market_map.get(market, market_map["default"])

    def get_company_news_wrapper(symbol: str, limit: int = 5) -> str:
        """
        Get latest news for a specific company using DuckDuckGo.

        Args:
            symbol: Stock symbol.
            limit: Number of news items.
        """

        return _first_success(impls, symbol, limit)

    get_company_news_wrapper.__name__ = "get_company_news"
    return get_company_news_wrapper


def create_get_global_news(market: MarketType):
    market_map: Dict[MarketType, List[Callable]] = {
        "US": [get_global_news],
        "HK": [get_global_news],
        "CN": [get_global_news],
        "CRYPTO": [get_global_news],
        "default": [get_global_news],
    }
    impls = market_map.get(market, market_map["default"])

    def get_global_news_wrapper(
        keywords: str = "financial markets economics", limit: int = 5
    ) -> str:
        """
        Get global financial news.
        """

        return _first_success(impls, keywords, limit)

    get_global_news_wrapper.__name__ = "get_global_news"
    return get_global_news_wrapper
