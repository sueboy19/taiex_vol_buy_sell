from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from .config import settings

_tz = ZoneInfo(settings.tz_name)


def now_tw() -> datetime:
    return datetime.now(_tz)


def is_market_open(now: datetime | None = None) -> bool:
    """判斷是否在台股盤中時間（09:00-13:30 Asia/Taipei）。"""
    now = now or now_tw()
    if now.weekday() >= 5:
        return False
    current = now.time()
    return time(9, 0) <= current < time(13, 30)


def is_after_close(now: datetime | None = None) -> bool:
    """判斷是否已過收盤（13:30 以後）。"""
    now = now or now_tw()
    return now.time() >= time(13, 30)


def is_trading_day(now: datetime | None = None) -> bool:
    """判斷是否為平日（簡易判斷，不含國定假日）。"""
    now = now or now_tw()
    return now.weekday() < 5
