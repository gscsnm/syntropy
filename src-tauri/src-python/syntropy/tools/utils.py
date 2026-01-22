import re
from typing import Literal
import logging
import threading
import time


SymbolFormat = Literal["digits", "prefix", "sina", "yahoo"]

logger = logging.getLogger(__name__)

_throttle_lock = threading.Lock()
_throttle_next_allowed: dict[str, float] = {}


def throttle(key: str, min_interval_s: float) -> None:
    if min_interval_s <= 0:
        return

    now = time.monotonic()
    with _throttle_lock:
        next_allowed = _throttle_next_allowed.get(key, 0.0)
        scheduled = now if now >= next_allowed else next_allowed
        _throttle_next_allowed[key] = scheduled + float(min_interval_s)

    delay = scheduled - now
    if delay > 0:
        time.sleep(delay)


def normalize_cn_symbol(symbol: str, output: SymbolFormat = "digits") -> str:
    value = (symbol or "").strip()
    if not value:
        return value

    upper = value.upper().replace(" ", "")
    matches = re.findall(r"\d{6}", upper)
    if matches:
        code = matches[-1]
    else:
        digits = "".join(ch for ch in upper if ch.isdigit())
        code = digits[-6:] if len(digits) >= 6 else digits

    if not code:
        return ""

    prefix = None
    m = re.match(r"^(SH|SZ|BJ)[\.\-_]?", upper)
    if m:
        prefix = m.group(1)
    elif upper.endswith((".SS", "SS", ".SH", "SH")):
        prefix = "SH"
    elif upper.endswith((".SZ", "SZ")):
        prefix = "SZ"
    elif upper.endswith((".BJ", "BJ")):
        prefix = "BJ"
    elif len(code) == 6:
        first = code[0]
        if first in ("6", "9"):
            prefix = "SH"
        elif first in ("0", "3"):
            prefix = "SZ"
        elif first in ("8", "4"):
            prefix = "BJ"

    if output == "digits":
        return code

    if output == "prefix":
        if prefix:
            return f"{prefix}{code}"
        return code

    if output == "sina":
        if prefix == "SH":
            return f"sh{code}"
        if prefix == "SZ":
            return f"sz{code}"
        if prefix == "BJ":
            return f"bj{code}"
        return code.lower()

    if output == "yahoo":
        if prefix == "SH":
            return f"{code}.SS"
        if prefix == "SZ":
            return f"{code}.SZ"
        if prefix == "BJ":
            return f"{code}.BJ"
        return code

    return code


def _akshare_cn_symbol_digits(symbol: str) -> str:
    return normalize_cn_symbol(symbol, "digits")


def _format_akshare_cn_symbol(symbol: str) -> str:
    return normalize_cn_symbol(symbol, "prefix")


def get_company_basic_info(market: str, symbol: str) -> str:
    market = (market or "").strip().upper()
    symbol = (symbol or "").strip()
    if not symbol:
        return ""

    if market != "CN":
        return ""

    try:
        import akshare as ak

        stock = normalize_cn_symbol(symbol, "digits")
        df = ak.stock_individual_info_em(symbol=stock)
        if df is None or df.empty:
            return ""

        columns = [str(c) for c in df.columns]
        if "item" in columns and "value" in columns:
            key_col = "item"
            val_col = "value"
        else:
            key_col = df.columns[0]
            val_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

        info: dict[str, str] = {}
        for _, row in df.iterrows():
            key = str(row.get(key_col, "")).strip()
            val = str(row.get(val_col, "")).strip()
            if key and val and val.lower() not in ("nan", "none"):
                info[key] = val

        preferred_keys = [
            "股票简称",
            "行业",
            "上市时间",
            "总市值",
            "流通市值",
            "市盈率(动)",
            "市净率",
            "每股收益",
            "每股净资产",
        ]

        lines = [
            "--- COMPANY BASICS ---",
            f"Market: {market}",
            f"Symbol: {symbol}",
            f"AKShareSymbol: {stock}",
        ]

        for k in preferred_keys:
            v = info.get(k)
            if v:
                lines.append(f"{k}: {v}")

        if len(lines) <= 4:
            for k, v in list(info.items())[:12]:
                lines.append(f"{k}: {v}")

        lines.append("--- END COMPANY BASICS ---")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"获取公司基本信息异常: {e}", exc_info=True)
        raise RuntimeError("获取公司基本信息异常") from e
