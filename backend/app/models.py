from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class DailyBar(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None
    value: int | None = None
    transactions: int | None = None
    margin_balance: int | None = None
    margin_buy: int | None = None
    margin_sell: int | None = None
    short_balance: int | None = None
    short_buy: int | None = None
    short_sell: int | None = None
    margin_value: int | None = None
    long_oi: int | None = None
    short_oi: int | None = None
    net_oi: int | None = None


class MinuteBar(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


class MarginData(BaseModel):
    date: date
    margin_balance: int
    margin_buy: int
    margin_sell: int
    short_balance: int
    short_buy: int
    short_sell: int


class RealtimeTick(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


def to_ms(dt: datetime | date) -> int:
    if isinstance(dt, datetime):
        return int(dt.timestamp() * 1000)
    return int(datetime(dt.year, dt.month, dt.day).timestamp() * 1000)


def dict_to_daily_bar(row: dict[str, Any]) -> DailyBar:
    d = row["date"]
    ts = to_ms(d)
    return DailyBar(
        timestamp=ts,
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        volume=row.get("volume"),
        value=row.get("value"),
        transactions=row.get("transactions"),
        margin_balance=row.get("margin_balance"),
        margin_buy=row.get("margin_buy"),
        margin_sell=row.get("margin_sell"),
        short_balance=row.get("short_balance"),
        short_buy=row.get("short_buy"),
        short_sell=row.get("short_sell"),
        margin_value=row.get("margin_value"),
        long_oi=row.get("long_oi"),
        short_oi=row.get("short_oi"),
        net_oi=row.get("net_oi"),
    )


def dict_to_minute_bar(row: dict[str, Any]) -> MinuteBar:
    return MinuteBar(
        timestamp=to_ms(row["ts"]),
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        volume=row.get("volume") or 0,
    )
