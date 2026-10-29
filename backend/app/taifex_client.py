from __future__ import annotations

import csv
import io
import logging
import re
from datetime import date, datetime
from typing import Any

from . import http_util
from .config import settings

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; taiex-chart/1.0)",
    "Accept": "text/html,application/xhtml+xml",
}

_URL = f"{settings.taifex_base}/cht/3/futContractsDate"
_ROLES = {"自營商", "投信", "外資", "外資及陸資", "陸資"}

_PCR_URL = f"{settings.taifex_base}/cht/3/dlPcRatioDown"
_PCR_HEADERS = {
    "User-Agent": _HEADERS["User-Agent"],
    "Accept": "*/*",
    "Referer": f"{settings.taifex_base}/cht/3/dlPcRatio",
}


def _cells(tr: str) -> list[str]:
    raw = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)
    out: list[str] = []
    for c in raw:
        t = re.sub(r"<[^>]+>", "", c).replace("&nbsp;", "").replace(",", "").strip()
        if t:
            out.append(t)
    return out


def _parse_foreign_tx_oi(html: str) -> dict[str, int] | None:
    """從 futContractsDate HTML 取出 外資「臺股期貨」多方/空方/淨 未平倉口數。"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I)
    current = None
    for tr in rows:
        cs = _cells(tr)
        if not cs:
            continue
        # 商品起始列：[序號, 商品名稱, 身份別, ...12 數字]
        if len(cs) >= 15 and cs[0].isdigit() and not cs[1].isdigit():
            current = cs[1]
            role, nums = cs[2], cs[3:15]
        elif cs[0] in _ROLES and len(cs) >= 13:
            role, nums = cs[0], cs[1:13]
        else:
            continue
        if current == "臺股期貨" and role.startswith("外資"):
            try:
                # nums 排列：多方交易(口/額), 空方交易(口/額), 淨額交易(口/額),
                #           多方未平倉(口/額), 空方未平倉(口/額), 淨未平倉(口/額)
                return {
                    "long_oi": int(nums[6]),
                    "short_oi": int(nums[8]),
                    "net_oi": int(nums[10]),
                }
            except (ValueError, IndexError):
                return None
    return None


async def fetch_foreign_future_oi(target_date: date) -> dict[str, Any] | None:
    """期交所三大法人 — 外資 臺股期貨 未平倉口數（單位：口）。"""
    form = {
        "queryType": "1",
        "queryDate": target_date.strftime("%Y/%m/%d"),
        "commodityId": "",
        "doQuery": "1",
    }
    try:
        html = await http_util.throttled_post_text(_URL, form, headers=_HEADERS)
    except Exception:
        logger.exception("fetch_foreign_future_oi failed")
        return None
    if "查無資料" in html:
        return None
    parsed = _parse_foreign_tx_oi(html)
    if parsed is None:
        return None
    return {"date": target_date, **parsed}


def _parse_pcr_csv(text: str) -> list[dict[str, Any]]:
    """解析期交所「臺指選擇權 Put/Call 比」CSV（Big5/MS950 由 httpx 依 header 解碼）。

    欄位：日期,賣權成交量,買權成交量,買賣權成交量比率%,賣權未平倉量,買權未平倉量,買賣權未平倉量比率%
    比率以原始成交量/未平倉量重算（比取整後的百分比更精確）。
    """
    out: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        raw_date = (row.get("日期") or "").strip()
        if not raw_date:
            continue
        try:
            d = datetime.strptime(raw_date, "%Y/%m/%d").date()
            call_vol = int((row.get("買權成交量") or "0").replace(",", ""))
            put_vol = int((row.get("賣權成交量") or "0").replace(",", ""))
            call_oi = int((row.get("買權未平倉量") or "0").replace(",", ""))
            put_oi = int((row.get("賣權未平倉量") or "0").replace(",", ""))
        except ValueError:
            continue
        out.append(
            {
                "date": d,
                "call_vol": call_vol,
                "put_vol": put_vol,
                "pcr_vol": round(put_vol / call_vol, 4) if call_vol else None,
                "call_oi": call_oi,
                "put_oi": put_oi,
                "pcr_oi": round(put_oi / call_oi, 4) if call_oi else None,
            }
        )
    return out


async def fetch_put_call_ratio(start: date, end: date) -> list[dict[str, Any]]:
    """期交所官方 臺指選擇權(TXO) Put/Call 比 CSV 下載（區間上限 30 日，由呼叫端分段）。"""
    form = {
        "queryStartDate": start.strftime("%Y/%m/%d"),
        "queryEndDate": end.strftime("%Y/%m/%d"),
        "down_type": "",
        "product_type": "1",
    }
    try:
        text = await http_util.throttled_post_text(_PCR_URL, form, headers=_PCR_HEADERS)
    except Exception:
        logger.exception("fetch_put_call_ratio failed")
        return []
    if not text or text.lstrip().startswith("<"):
        # 非 CSV（錯誤頁/alert HTML，如區間超過 30 日）
        logger.warning("put_call_ratio response is not CSV (start=%s end=%s)", start, end)
        return []
    return _parse_pcr_csv(text)
