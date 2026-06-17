from __future__ import annotations

import logging
import re
from datetime import date
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
