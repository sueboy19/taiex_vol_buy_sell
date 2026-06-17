from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from .. import db

router = APIRouter(prefix="/api", tags=["margin"])


@router.get("/margin")
async def get_margin(
    start: date | None = Query(None),
    end: date | None = Query(None),
):
    sql = "SELECT date, margin_balance, margin_buy, margin_sell, short_balance, short_buy, short_sell FROM daily_margin"
    clauses: list[str] = []
    params: list = []
    if start is not None:
        clauses.append("date >= ?")
        params.append(start)
    if end is not None:
        clauses.append("date <= ?")
        params.append(end)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY date"
    rows = db.fetchall_dict(sql, params)
    return {"rows": [{**r, "date": r["date"].isoformat()} for r in rows]}
