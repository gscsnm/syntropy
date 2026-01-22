import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import logging

from .utils import normalize_cn_symbol

logger = logging.getLogger(__name__)


def _normalize_indicator_id(indicator_id: str) -> str:
    indicator_id = (indicator_id or "").strip()
    aliases = {
        "sma_50": "close_50_sma",
        "sma_200": "close_200_sma",
        "ema_10": "close_10_ema",
        "bollinger": "boll",
    }
    return aliases.get(indicator_id, indicator_id)


def _calculate_indicator(df: pd.DataFrame, indicator_id: str) -> Optional[pd.Series]:
    indicator_id = _normalize_indicator_id(indicator_id)

    if "Close" not in df.columns:
        return None

    close = df["Close"]

    if indicator_id == "close_50_sma":
        return close.rolling(window=50).mean()
    if indicator_id == "close_200_sma":
        return close.rolling(window=200).mean()
    if indicator_id == "close_10_ema":
        return close.ewm(span=10, adjust=False).mean()
    if indicator_id == "rsi":
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    if indicator_id in ("macd", "macds", "macdh"):
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal = macd_line.ewm(span=9, adjust=False).mean()
        if indicator_id == "macd":
            return macd_line
        if indicator_id == "macds":
            return signal
        return macd_line - signal

    if indicator_id in ("boll", "boll_ub", "boll_lb"):
        mid = close.rolling(window=20).mean()
        std = close.rolling(window=20).std(ddof=0)
        if indicator_id == "boll":
            return mid
        if indicator_id == "boll_ub":
            return mid + 2 * std
        return mid - 2 * std

    if indicator_id == "atr":
        if "High" not in df.columns or "Low" not in df.columns:
            return None
        high = df["High"]
        low = df["Low"]
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                (high - low).abs(),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(window=14).mean()

    if indicator_id == "vwma":
        if "Volume" not in df.columns:
            return None
        volume = df["Volume"]
        numerator = (close * volume).rolling(window=20).sum()
        denominator = volume.rolling(window=20).sum()
        return numerator / denominator

    return None


def get_market_data_by_akshare(
    symbol: str, start_date: str, end_date: str, interval: str = "1d"
) -> str:
    """
    Get historical market data for a given symbol.
    
    Args:
        symbol: The stock symbol (e.g., '000001', 'SH600000', 'sz000001').
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        interval: Data interval (e.g., '1d').
        
    Returns:
        CSV string of the market data.
    """
    try:
        import akshare as ak

        start_ymd = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d")
        end_ymd = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y%m%d")
        stock = normalize_cn_symbol(symbol, "digits")

        interval_map = {
            "1d": "daily",
            "1wk": "weekly",
            "1mo": "monthly",
        }
        period = interval_map.get(interval)
        if period is None:
            raise RuntimeError(
                f"Error fetching market data: interval {interval} not supported for akshare."
            )

        df = ak.stock_zh_a_hist(
            symbol=stock, period=period, start_date=start_ymd, end_date=end_ymd, adjust=""
        )
        if df is None or df.empty:
            return f"No data found for {symbol} from {start_date} to {end_date}."

        rename_map = {
            "日期": "Date",
            "开盘": "Open",
            "收盘": "Close",
            "最高": "High",
            "最低": "Low",
            "成交量": "Volume",
            "成交额": "Amount",
            "振幅": "Amplitude",
            "涨跌幅": "ChangePct",
            "涨跌额": "Change",
            "换手率": "Turnover",
        }
        df = df.rename(columns=rename_map)

        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

        numeric_cols = ["Open", "High", "Low", "Close", "Volume"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

        return df.to_csv(index=False)
    except Exception as e:
        logger.error("Error fetching market data (akshare)", exc_info=True)
        raise RuntimeError("Error fetching market data") from e


def get_indicator_timeseries_by_akshare(
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
    try:
        import akshare as ak

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        lookback_start = (start_dt - timedelta(days=365)).strftime("%Y%m%d")
        end_ymd = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y%m%d")

        stock = normalize_cn_symbol(symbol, "digits")
        df = ak.stock_zh_a_hist(
            symbol=stock, period="daily", start_date=lookback_start, end_date=end_ymd, adjust=""
        )
        if df is None or df.empty:
            return f"No data for {symbol}"

        required_columns = {"日期", "收盘", "最高", "最低", "成交量"}
        if not required_columns.issubset(set(df.columns)):
            raise RuntimeError(
                f"Error calculating indicator: unexpected akshare columns for {symbol}."
            )

        date_index = pd.to_datetime(df["日期"], errors="coerce")
        close = pd.to_numeric(df["收盘"], errors="coerce").to_numpy()
        high = pd.to_numeric(df["最高"], errors="coerce").to_numpy()
        low = pd.to_numeric(df["最低"], errors="coerce").to_numpy()
        volume = pd.to_numeric(df["成交量"], errors="coerce").to_numpy()

        aligned = pd.DataFrame(
            {
                "Close": close,
                "High": high,
                "Low": low,
                "Volume": volume,
            },
            index=pd.DatetimeIndex(date_index),
        )
        aligned = aligned[~aligned.index.isna()].sort_index().dropna(subset=["Close"])

        result_series = _calculate_indicator(aligned, indicator_id)
        if result_series is None:
            return f"Indicator {indicator_id} not implemented or data unavailable."

        start_ts = pd.to_datetime(start_date, errors="coerce")
        end_ts = pd.to_datetime(end_date, errors="coerce")
        if pd.isna(start_ts) or pd.isna(end_ts):
            raise RuntimeError(
                f"Error calculating indicator: invalid date range {start_date} to {end_date}."
            )

        mask = (result_series.index >= start_ts) & (result_series.index <= end_ts)
        filtered = result_series.loc[mask]

        rows: list[str] = []
        for date, value in filtered.items():
            if pd.isna(value):
                continue
            date_str = pd.to_datetime(date).strftime("%Y-%m-%d")
            rows.append(f"{date_str}: {value:.2f}")

        if not rows:
            return (
                f"No data for {symbol} indicator {indicator_id} "
                f"from {start_date} to {end_date}."
            )

        output = [f"Indicator {indicator_id} for {symbol}:"]
        output.extend(rows)
        return "\n".join(output)
    except Exception as e:
        logger.error("Error calculating indicator (akshare)", exc_info=True)
        raise RuntimeError("Error calculating indicator") from e
