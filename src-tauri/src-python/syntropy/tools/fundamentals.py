import pandas as pd
import random
import time
import logging
from typing import Callable, Optional, Sequence

from .utils import normalize_cn_symbol, throttle

logger = logging.getLogger(__name__)


def _is_rate_limited_error(err: Exception) -> bool:
    text = str(err or "").lower()
    needles = (
        "too many requests",
        "rate limit",
        "ratelimit",
        "http 429",
        "status code 429",
        "temporarily blocked",
        "throttle",
    )
    return any(x in text for x in needles)


def _sleep_retry(attempt: int) -> None:
    base = 1.0 * (2 ** attempt)
    delay = min(10.0, base) + random.uniform(0.0, 0.5)
    time.sleep(delay)


def _ak_call(func):
    last_err = None
    for attempt in range(4):
        try:
            throttle("akshare", 0.8)
            return func()
        except Exception as e:
            last_err = e
            if attempt < 3 and _is_rate_limited_error(e):
                _sleep_retry(attempt)
                continue
            raise
    if last_err is not None:
        raise last_err


def _ak_call_with_variants(func: Callable, kwargs_variants: Sequence[dict], args_variants: Sequence[tuple] = ()) -> object:
    last_err: Optional[Exception] = None
    for kwargs in kwargs_variants:
        try:
            return _ak_call(lambda: func(**kwargs))
        except TypeError as e:
            last_err = e
            continue
    for args in args_variants:
        try:
            return _ak_call(lambda: func(*args))
        except TypeError as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return _ak_call(lambda: func())


def _ak_first_non_empty_df(sources: Sequence[Callable[[], object]]) -> Optional[pd.DataFrame]:
    last_err: Optional[Exception] = None
    for source in sources:
        try:
            value = source()
            df = value if isinstance(value, pd.DataFrame) else None
            if df is None or df.empty:
                continue
            return df
        except Exception as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return None


def _sort_df_by_possible_date(df: pd.DataFrame, possible_cols: Sequence[str]) -> pd.DataFrame:
    date_col = next((c for c in possible_cols if c in df.columns), None)
    if date_col is None:
        return df
    date_series = pd.to_datetime(df[date_col], errors="coerce")
    if date_series.isna().all():
        return df
    sorted_df = df.assign(__date_sort=date_series).sort_values("__date_sort", ascending=False)
    return sorted_df.drop(columns=["__date_sort"], errors="ignore")

def get_fundamentals_by_akshare(symbol: str) -> str:
    """
    Get general fundamental info for a company.
    
    Args:
        symbol: Stock symbol.
    
    Returns:
        String summary of fundamentals.
    """
    try:
        import akshare as ak

        stock_digits = normalize_cn_symbol(symbol, "digits")

        def _source_em_abstract() -> object:
            func = getattr(ak, "stock_financial_abstract", None)
            if func is None:
                raise RuntimeError("stock_financial_abstract not available")
            return _ak_call_with_variants(
                func,
                kwargs_variants=[{k: stock_digits} for k in ("symbol", "stock", "code")],
                args_variants=[(stock_digits,)],
            )

        def _source_ths_abstract_report() -> object:
            func = getattr(ak, "stock_financial_abstract_new_ths", None)
            if func is None:
                raise RuntimeError("stock_financial_abstract_new_ths not available")
            return _ak_call_with_variants(
                func,
                kwargs_variants=[
                    {"symbol": stock_digits, "indicator": "按报告期"},
                    {"symbol": stock_digits, "indicator": "按年度"},
                ],
            )

        df = _ak_first_non_empty_df([_source_em_abstract, _source_ths_abstract_report])
        if df is None or df.empty:
            return f"No data found for {symbol}."

        df = _sort_df_by_possible_date(df, ("report_date", "报告期", "截止日期", "日期"))
        latest = df.iloc[0].to_dict()
        result = [f"Fundamental Data for {symbol}:"]
        for k, v in latest.items():
            if k is None:
                continue
            key = str(k).strip()
            if not key:
                continue
            value = "" if v is None else str(v).strip()
            if value:
                result.append(f"{key}: {value}")
        return "\n".join(result)
    except Exception as e:
        logger.error("Error fetching fundamentals (akshare)", exc_info=True)
        raise RuntimeError("Error fetching fundamentals") from e

def get_balance_sheet_by_akshare(symbol: str, freq: str = "quarterly") -> str:
    """
    Get balance sheet.
    
    Args:
        symbol: Stock symbol.
        freq: 'annual' or 'quarterly'.
    """
    try:
        import akshare as ak

        stock_prefix = normalize_cn_symbol(symbol, "prefix")
        stock_digits = normalize_cn_symbol(symbol, "digits")
        ths_indicator = "按报告期" if freq == "quarterly" else "按年度"

        def _source_em() -> object:
            if freq == "quarterly":
                func = getattr(ak, "stock_balance_sheet_by_report_em", None)
                if func is None:
                    raise RuntimeError("stock_balance_sheet_by_report_em not available")
                return _ak_call(lambda: func(symbol=stock_prefix))
            func = getattr(ak, "stock_balance_sheet_by_yearly_em", None)
            if func is None:
                raise RuntimeError("stock_balance_sheet_by_yearly_em not available")
            return _ak_call(lambda: func(symbol=stock_prefix))

        def _source_ths() -> object:
            func = getattr(ak, "stock_financial_debt_new_ths", None)
            if func is None:
                raise RuntimeError("stock_financial_debt_new_ths not available")
            return _ak_call_with_variants(
                func,
                kwargs_variants=[
                    {"symbol": stock_digits, "indicator": ths_indicator},
                    {"symbol": stock_digits, "indicator": "按报告期"},
                    {"symbol": stock_digits, "indicator": "按年度"},
                ],
            )

        df = _ak_first_non_empty_df([_source_em, _source_ths])
        if df is None or df.empty:
            return f"No data found for {symbol}."
        return df.to_csv(index=False)
    except Exception as e:
        logger.error("Error fetching balance sheet (akshare)", exc_info=True)
        raise RuntimeError("Error fetching balance sheet") from e

def get_cashflow_by_akshare(symbol: str, freq: str = "quarterly") -> str:
    """Get cash flow statement."""
    try:
        import akshare as ak

        stock_prefix = normalize_cn_symbol(symbol, "prefix")
        stock_digits = normalize_cn_symbol(symbol, "digits")
        ths_indicator = "按报告期" if freq == "quarterly" else "按年度"

        def _source_em() -> object:
            if freq == "quarterly":
                func = getattr(ak, "stock_cash_flow_sheet_by_quarterly_em", None)
                if func is None:
                    raise RuntimeError("stock_cash_flow_sheet_by_quarterly_em not available")
                return _ak_call(lambda: func(symbol=stock_prefix))
            func = getattr(ak, "stock_cash_flow_sheet_by_yearly_em", None)
            if func is None:
                raise RuntimeError("stock_cash_flow_sheet_by_yearly_em not available")
            return _ak_call(lambda: func(symbol=stock_prefix))

        def _source_ths() -> object:
            func = getattr(ak, "stock_financial_cash_new_ths", None)
            if func is None:
                raise RuntimeError("stock_financial_cash_new_ths not available")
            return _ak_call_with_variants(
                func,
                kwargs_variants=[
                    {"symbol": stock_digits, "indicator": ths_indicator},
                    {"symbol": stock_digits, "indicator": "按报告期"},
                    {"symbol": stock_digits, "indicator": "按年度"},
                ],
            )

        df = _ak_first_non_empty_df([_source_em, _source_ths])
        if df is None or df.empty:
            return f"No data found for {symbol}."
        return df.to_csv(index=False)
    except Exception as e:
        logger.error("Error fetching cashflow (akshare)", exc_info=True)
        raise RuntimeError("Error fetching cashflow") from e

def get_income_statement_by_akshare(symbol: str, freq: str = "quarterly") -> str:
    """Get income statement."""
    try:
        import akshare as ak

        stock_prefix = normalize_cn_symbol(symbol, "prefix")
        stock_digits = normalize_cn_symbol(symbol, "digits")
        ths_indicator = "按报告期" if freq == "quarterly" else "按年度"

        def _source_em() -> object:
            if freq == "quarterly":
                func = getattr(ak, "stock_profit_sheet_by_quarterly_em", None)
                if func is None:
                    raise RuntimeError("stock_profit_sheet_by_quarterly_em not available")
                return _ak_call(lambda: func(symbol=stock_prefix))
            func = getattr(ak, "stock_profit_sheet_by_yearly_em", None)
            if func is None:
                raise RuntimeError("stock_profit_sheet_by_yearly_em not available")
            return _ak_call(lambda: func(symbol=stock_prefix))

        def _source_ths() -> object:
            func = getattr(ak, "stock_financial_benefit_new_ths", None)
            if func is None:
                raise RuntimeError("stock_financial_benefit_new_ths not available")
            return _ak_call_with_variants(
                func,
                kwargs_variants=[
                    {"symbol": stock_digits, "indicator": ths_indicator},
                    {"symbol": stock_digits, "indicator": "按报告期"},
                    {"symbol": stock_digits, "indicator": "按年度"},
                ],
            )

        df = _ak_first_non_empty_df([_source_em, _source_ths])
        if df is None or df.empty:
            return f"No data found for {symbol}."
        return df.to_csv(index=False)
    except Exception as e:
        logger.error("Error fetching income statement (akshare)", exc_info=True)
        raise RuntimeError("Error fetching income statement") from e

def get_insider_transactions_by_akshare(symbol: str) -> str:
    """Get recent insider transactions."""
    try:
        import akshare as ak

        stock_digits = normalize_cn_symbol(symbol, "digits")
        def _source_em_detail() -> object:
            func = getattr(ak, "stock_hold_management_detail_em", None)
            if func is None:
                raise RuntimeError("stock_hold_management_detail_em not available")
            return _ak_call_with_variants(
                func,
                kwargs_variants=[{k: stock_digits} for k in ("symbol", "stock", "code")],
                args_variants=[(stock_digits,)],
            )

        def _source_ths_management_change() -> object:
            func = getattr(ak, "stock_management_change_ths", None)
            if func is None:
                raise RuntimeError("stock_management_change_ths not available")
            return _ak_call_with_variants(
                func,
                kwargs_variants=[{"symbol": stock_digits}],
                args_variants=[(stock_digits,)],
            )

        def _source_ths_shareholder_change() -> object:
            func = getattr(ak, "stock_shareholder_change_ths", None)
            if func is None:
                raise RuntimeError("stock_shareholder_change_ths not available")
            return _ak_call_with_variants(
                func,
                kwargs_variants=[{"symbol": stock_digits}],
                args_variants=[(stock_digits,)],
            )

        df = _ak_first_non_empty_df(
            [_source_em_detail, _source_ths_management_change, _source_ths_shareholder_change]
        )

        if df is None or df.empty:
            return f"No data found for {symbol}."

        possible_code_cols = ("代码", "股票代码", "证券代码")
        code_col = next((c for c in possible_code_cols if c in df.columns), None)
        if code_col is not None:
            df = df[df[code_col].astype(str).str.zfill(6) == stock_digits.zfill(6)]

        if df is None or df.empty:
            return f"No data found for {symbol}."

        df = _sort_df_by_possible_date(df, ("变动日期", "公告日期", "日期", "report_date"))

        return df.head(10).to_csv(index=False)
    except Exception as e:
        logger.error("Error fetching insider transactions (akshare)", exc_info=True)
        raise RuntimeError("Error fetching insider transactions") from e
