from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Query

from .. import db
from ..models import dict_to_daily_bar, dict_to_minute_bar

router = APIRouter(prefix="/api", tags=["kline"])


@router.get("/kline")
async def get_kline(
    period: str = Query("day", pattern="^(day|minute)$"),
    date: date | None = Query(None, alias="date"),
):
    if period == "minute":
        rows = db.get_minute_kline(day=date)
        return {"period": "minute", "bars": [dict_to_minute_bar(r).model_dump() for r in rows]}
    else:
        rows = db.get_merged_daily()
        return {"period": "day", "bars": [dict_to_daily_bar(r).model_dump() for r in rows]}
