from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; taiex-chart/1.0)",
    "Accept": "application/json",
}


async def fetch_intraday_minute_kline(range: str = "1d") -> list[dict[str, Any]]:
    """Yahoo Finance v8 chart API — 取得分鐘 K 線（指數 OHLC）。

    URL: /v8/finance/chart/^TWII?interval=1m&range=<range>
    預設 range=1d（當日盤中每分鐘）；收盤後可用 "5d" 補抓近日分鐘線。
    回傳 list of {ts, open, high, low, close}（volume 恆為 0，指數無量）
    """
    url = f"{settings.yahoo_chart_base}/v8/finance/chart/{settings.yahoo_index_symbol}"
    params = {"interval": "1m", "range": range}
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_sec, headers=_HEADERS, follow_redirects=True
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        logger.exception("fetch_intraday_minute_kline failed")
        return []

    result = payload.get("chart", {}).get("result")
    if not result:
        return []
    root = result[0]
    timestamps: list[int] = root.get("timestamp", [])
    quotes = root.get("indicators", {}).get("quote", [{}])[0]
    opens = quotes.get("open", [])
    highs = quotes.get("high", [])
    lows = quotes.get("low", [])
    closes = quotes.get("close", [])

    bars: list[dict[str, Any]] = []
    for i, ts_epoch in enumerate(timestamps):
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        c = closes[i] if i < len(closes) else None
        if o is None or h is None or l is None or c is None:
            continue
        bars.append(
            {
                "ts": datetime.fromtimestamp(ts_epoch, tz=timezone.utc),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
            }
        )
    return bars


async def fetch_realtime_quote() -> dict[str, Any] | None:
    """TWSE MIS getStockInfo.jsp — 即時大盤指數（備援來源）。

    回傳 {ts, open, high, low, close, prev_close}
    """
    url = f"{settings.twse_mis_base}/stock/api/getStockInfo.jsp"
    params = {"ex_ch": settings.twse_index_symbol, "json": "1", "delay": "0"}
    headers = {**_HEADERS, "Referer": settings.twse_mis_base + "/"}
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_sec, headers=headers, follow_redirects=True
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        logger.exception("fetch_realtime_quote failed")
        return None

    msg = payload.get("msgArray", [])
    if not msg:
        return None
    item = msg[0]

    def _f(key: str) -> float:
        v = item.get(key)
        if v in (None, "-", "--", ""):
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    tlong = item.get("tlong")
    if tlong:
        ts = datetime.fromtimestamp(int(tlong) / 1000, tz=timezone.utc)
    else:
        ts = datetime.now(tz=timezone.utc)

    return {
        "ts": ts,
        "open": _f("o"),
        "high": _f("h"),
        "low": _f("l"),
        "close": _f("z"),
        "prev_close": _f("y"),
    }
