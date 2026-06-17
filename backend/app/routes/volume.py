from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from .. import db

router = APIRouter(prefix="/api", tags=["volume"])


@router.get("/volume")
async def get_volume(
    start: date | None = Query(None),
    end: date | None = Query(None),
):
    sql = "SELECT date, volume, value, transactions FROM daily_volume"
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
