from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from . import http_util
from .config import settings

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; taiex-chart/1.0)",
    "Accept": "application/json",
}


async def fetch_market_volume(
    start: date, end: date
) -> list[dict[str, Any]]:
    """FinMind — 大盤（TAIEX）每日成交量歷史（全市場，單位：股）。

    dataset: TaiwanStockPrice, data_id=TAIEX
    回傳 list of {date, volume, value, transactions}
    """
    url = settings.finmind_base
    params: dict[str, str] = {
        "dataset": "TaiwanStockPrice",
        "data_id": "TAIEX",
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
    }
    if settings.finmind_token:
        params["token"] = settings.finmind_token

    try:
        payload = await http_util.throttled_get_json(url, params, headers=_HEADERS)
    except Exception:
        logger.exception("fetch_market_volume failed")
        return []

    rows = payload.get("data", []) if isinstance(payload, dict) else []
    out: list[dict[str, Any]] = []
    for r in rows:
        d_str = r.get("date")
        if not d_str:
            continue
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        out.append(
            {
                "date": d,
                "volume": int(r.get("Trading_Volume") or 0),
                "value": int(r.get("Trading_money") or 0),
                "transactions": int(r.get("Trading_turnover") or 0),
            }
        )
    return out


async def fetch_market_margin(
    start: date, end: date
) -> list[dict[str, Any]]:
    """FinMind — 全市場融資融券歷史（全市場合計，單位：張）。

    dataset: TaiwanStockTotalMarginPurchaseShortSale
    回傳 list of {date, margin_balance, margin_buy, margin_sell,
                   short_balance, short_buy, short_sell}
    """
    url = settings.finmind_base
    params: dict[str, str] = {
        "dataset": "TaiwanStockTotalMarginPurchaseShortSale",
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
    }
    if settings.finmind_token:
        params["token"] = settings.finmind_token

    try:
        payload = await http_util.throttled_get_json(url, params, headers=_HEADERS)
    except Exception:
        logger.exception("fetch_market_margin failed")
        return []

    rows = payload.get("data", []) if isinstance(payload, dict) else []
    if not rows:
        return []

    pivoted: dict[str, dict[str, Any]] = {}
    for r in rows:
        d_str = r.get("date")
        if not d_str:
            continue
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        entry = pivoted.setdefault(
            d.isoformat(),
            {
                "date": d,
                "margin_balance": 0,
                "margin_buy": 0,
                "margin_sell": 0,
                "short_balance": 0,
                "short_buy": 0,
                "short_sell": 0,
                "margin_value": 0,
            },
        )
        name = r.get("name")
        if name == "MarginPurchase":
            entry["margin_balance"] = int(r.get("TodayBalance") or 0)
            entry["margin_buy"] = int(r.get("buy") or 0)
            entry["margin_sell"] = int(r.get("sell") or 0)
        elif name == "ShortSale":
            entry["short_balance"] = int(r.get("TodayBalance") or 0)
            entry["short_buy"] = int(r.get("buy") or 0)
            entry["short_sell"] = int(r.get("sell") or 0)
        elif name == "MarginPurchaseMoney":
            # 融資金額（元）
            entry["margin_value"] = int(r.get("TodayBalance") or 0)

    return [pivoted[k] for k in sorted(pivoted)]
