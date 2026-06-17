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


async def _get_json(url: str, params: dict[str, str] | None = None) -> Any:
    return await http_util.throttled_get_json(url, params, headers=_HEADERS)


def _today_str() -> str:
    return datetime.now().strftime("%Y%m%d")


def _parse_date(val: Any) -> date | None:
    """解析 TWSE 日期字串。

    TWSE OpenAPI 回傳民國年格式（YYYMMDD 或 YYY/MM/DD），
    例如 1150601 / 115/06/01 表示民國115年 = 西元 2026 年。
    同時相容西元年格式（YYYYMMDD / YYYY/MM/DD / YYYY-MM-DD）。
    """
    if not val:
        return None
    s = str(val).strip()
    digits = s.replace("/", "").replace("-", "")
    if len(digits) == 7:
        try:
            return date(int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:7]))
        except ValueError:
            return None
    if len(digits) == 8:
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


async def fetch_daily_kline(target_date: date | None = None) -> list[dict[str, Any]]:
    """發行量加權股價指數歷史資料（日 OHLC）。

    Endpoint: /indicesReport/MI_5MINS_HIST
    """
    url = f"{settings.twse_openapi_base}/indicesReport/MI_5MINS_HIST"
    params = {"date": (target_date or date.today()).strftime("%Y%m%d")}
    try:
        data = await _get_json(url, params)
    except Exception:
        logger.exception("fetch_daily_kline failed")
        return []

    rows: list[dict[str, Any]] = []
    for item in data:
        try:
            d = _parse_date(item["Date"])
            if d is None:
                continue
            rows.append(
                {
                    "date": d,
                    "open": float(str(item["OpeningIndex"]).replace(",", "")),
                    "high": float(str(item["HighestIndex"]).replace(",", "")),
                    "low": float(str(item["LowestIndex"]).replace(",", "")),
                    "close": float(str(item["ClosingIndex"]).replace(",", "")),
                }
            )
        except (KeyError, ValueError, TypeError):
            continue
    return rows


async def fetch_daily_volume(target_date: date | None = None) -> list[dict[str, Any]]:
    """集中市場每日市場成交資訊（成交量/值/筆數）。

    Endpoint: /exchangeReport/FMTQIK
    """
    url = f"{settings.twse_openapi_base}/exchangeReport/FMTQIK"
    params = {"date": (target_date or date.today()).strftime("%Y%m%d")}
    try:
        data = await _get_json(url, params)
    except Exception:
        logger.exception("fetch_daily_volume failed")
        return []

    rows: list[dict[str, Any]] = []
    for item in data:
        try:
            d = _parse_date(item["Date"])
            if d is None:
                continue
            rows.append(
                {
                    "date": d,
                    "volume": int(str(item.get("TradeVolume", "0")).replace(",", "")),
                    "value": int(str(item.get("TradeValue", "0")).replace(",", "")),
                    "transactions": int(
                        str(item.get("Transaction", "0")).replace(",", "")
                    ),
                }
            )
        except (KeyError, ValueError, TypeError):
            continue
    return rows


def _safe_int(val: Any) -> int:
    if val is None:
        return 0
    s = str(val).replace(",", "").replace("--", "0").strip()
    try:
        return int(float(s))
    except ValueError:
        return 0


async def fetch_daily_margin(target_date: date | None = None) -> list[dict[str, Any]]:
    """集中市場融資融券餘額（全市場所有個股合計）。

    Endpoint: /exchangeReport/MI_MARGN
    回傳逐筆個股資料，此函式加總為全市場合計。
    """
    url = f"{settings.twse_openapi_base}/exchangeReport/MI_MARGN"
    params = {"date": (target_date or date.today()).strftime("%Y%m%d")}
    try:
        data = await _get_json(url, params)
    except Exception:
        logger.exception("fetch_daily_margin failed")
        return []

    if not data:
        return []

    d = target_date or date.today()

    agg = {
        "margin_balance": 0,
        "margin_buy": 0,
        "margin_sell": 0,
        "short_balance": 0,
        "short_buy": 0,
        "short_sell": 0,
    }
    key_maps = {
        "margin_balance": ["融資今日餘額", "MarginBalance"],
        "margin_buy": ["融資買進", "MarginBuy"],
        "margin_sell": ["融資賣出", "MarginSell"],
        "short_balance": ["融券今日餘額", "ShortBalance"],
        "short_buy": ["融券買進", "ShortBuy"],
        "short_sell": ["融券賣出", "ShortSell"],
    }
    for item in data:
        for field, keys in key_maps.items():
            for k in keys:
                if k in item:
                    agg[field] += _safe_int(item[k])
                    break

    return [{"date": d, **agg}]


async def fetch_intraday_5min() -> dict[str, Any] | None:
    """每 5 秒委託成交統計（盤中即時累計量）。

    Endpoint: /exchangeReport/MI_5MINS
    回傳最後一筆的累計成交量/值與時間。
    """
    url = f"{settings.twse_openapi_base}/exchangeReport/MI_5MINS"
    params = {"date": _today_str()}
    try:
        data = await _get_json(url, params)
    except Exception:
        logger.exception("fetch_intraday_5min failed")
        return None

    if not data:
        return None

    last = data[-1]
    time_str = last.get("Time", last.get("時間", ""))
    try:
        hh, mm, ss = time_str.split(":")
        now = datetime.now()
        ts = now.replace(hour=int(hh), minute=int(mm), second=int(ss), microsecond=0)
    except Exception:
        ts = datetime.now()

    return {
        "ts": ts,
        "acc_volume": _safe_int(last.get("AccTradeVolume", last.get("累積成交數量"))),
        "acc_value": _safe_int(last.get("AccTradeValue", last.get("累積成交金額"))),
    }
