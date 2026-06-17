from __future__ import annotations

import threading
from datetime import date, datetime
from typing import Any

import duckdb

from .config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS daily_kline (
    date DATE PRIMARY KEY,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE
);

CREATE TABLE IF NOT EXISTS daily_volume (
    date DATE PRIMARY KEY,
    volume BIGINT,
    value BIGINT,
    transactions INT
);

CREATE TABLE IF NOT EXISTS daily_margin (
    date DATE PRIMARY KEY,
    margin_balance BIGINT,
    margin_buy BIGINT,
    margin_sell BIGINT,
    short_balance BIGINT,
    short_buy BIGINT,
    short_sell BIGINT
);

CREATE TABLE IF NOT EXISTS minute_kline (
    ts TIMESTAMP PRIMARY KEY,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume BIGINT
);

CREATE TABLE IF NOT EXISTS intraday_acc (
    ts TIMESTAMP PRIMARY KEY,
    acc_volume BIGINT,
    acc_value BIGINT
);
"""

_lock = threading.RLock()
_conn: duckdb.DuckDBPyConnection | None = None


def init_db() -> None:
    global _conn
    if _conn is not None:
        return
    _conn = duckdb.connect(settings.duckdb_path)
    _conn.execute(SCHEMA_SQL)


def get_conn() -> duckdb.DuckDBPyConnection:
    if _conn is None:
        init_db()
    assert _conn is not None
    return _conn


def execute(sql: str, params: list[Any] | None = None) -> None:
    with _lock:
        get_conn().execute(sql, params or [])


def fetchall(sql: str, params: list[Any] | None = None) -> list[list[Any]]:
    with _lock:
        cur = get_conn().execute(sql, params or [])
        return cur.fetchall()


def fetchall_dict(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    with _lock:
        cur = get_conn().execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetchone_dict(sql: str, params: list[Any] | None = None) -> dict[str, Any] | None:
    rows = fetchall_dict(sql, params)
    return rows[0] if rows else None


def upsert_daily_kline(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with _lock:
        conn = get_conn()
        conn.executemany(
            """
            INSERT OR REPLACE INTO daily_kline (date, open, high, low, close)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    r["date"],
                    float(r["open"]),
                    float(r["high"]),
                    float(r["low"]),
                    float(r["close"]),
                )
                for r in rows
            ],
        )
    return len(rows)


def upsert_daily_volume(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with _lock:
        conn = get_conn()
        conn.executemany(
            """
            INSERT OR REPLACE INTO daily_volume (date, volume, value, transactions)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    r["date"],
                    int(r.get("volume") or 0),
                    int(r.get("value") or 0),
                    int(r.get("transactions") or 0),
                )
                for r in rows
            ],
        )
    return len(rows)


def upsert_daily_margin(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with _lock:
        conn = get_conn()
        conn.executemany(
            """
            INSERT OR REPLACE INTO daily_margin
                (date, margin_balance, margin_buy, margin_sell,
                 short_balance, short_buy, short_sell)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r["date"],
                    int(r.get("margin_balance") or 0),
                    int(r.get("margin_buy") or 0),
                    int(r.get("margin_sell") or 0),
                    int(r.get("short_balance") or 0),
                    int(r.get("short_buy") or 0),
                    int(r.get("short_sell") or 0),
                )
                for r in rows
            ],
        )
    return len(rows)


def upsert_minute_kline(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with _lock:
        conn = get_conn()
        conn.executemany(
            """
            INSERT OR REPLACE INTO minute_kline (ts, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r["ts"],
                    float(r["open"]),
                    float(r["high"]),
                    float(r["low"]),
                    float(r["close"]),
                    int(r.get("volume") or 0),
                )
                for r in rows
            ],
        )
    return len(rows)


def upsert_intraday_acc(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with _lock:
        conn = get_conn()
        conn.executemany(
            """
            INSERT OR REPLACE INTO intraday_acc (ts, acc_volume, acc_value)
            VALUES (?, ?, ?)
            """,
            [
                (r["ts"], int(r.get("acc_volume") or 0), int(r.get("acc_value") or 0))
                for r in rows
            ],
        )
    return len(rows)


def get_merged_daily(start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
    # TWSE 的 MI_MARGN 只提供「最新」融資融券（不支援歷史查詢），
    # 且日線（MI_5MINS_HIST）較融資融券晚一天。為避免副圖全空，
    # 將最新一筆融資融券套用至尚無資料的日線（COALESCE），隨每日累積會自動呈現真實走勢。
    sql = """
        SELECT k.date, k.open, k.high, k.low, k.close,
               v.volume, v.value, v.transactions,
               COALESCE(m.margin_balance, lm.margin_balance) AS margin_balance,
               COALESCE(m.margin_buy, lm.margin_buy) AS margin_buy,
               COALESCE(m.margin_sell, lm.margin_sell) AS margin_sell,
               COALESCE(m.short_balance, lm.short_balance) AS short_balance,
               COALESCE(m.short_buy, lm.short_buy) AS short_buy,
               COALESCE(m.short_sell, lm.short_sell) AS short_sell
        FROM daily_kline k
        LEFT JOIN daily_volume v ON k.date = v.date
        LEFT JOIN daily_margin m ON k.date = m.date
        LEFT JOIN (
            SELECT margin_balance, margin_buy, margin_sell,
                   short_balance, short_buy, short_sell
            FROM daily_margin ORDER BY date DESC LIMIT 1
        ) lm ON TRUE
    """
    params: list[Any] = []
    clauses: list[str] = []
    if start is not None:
        clauses.append("k.date >= ?")
        params.append(start)
    if end is not None:
        clauses.append("k.date <= ?")
        params.append(end)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY k.date"
    return fetchall_dict(sql, params)


def get_minute_kline(day: date | None = None) -> list[dict[str, Any]]:
    sql = "SELECT ts, open, high, low, close, volume FROM minute_kline"
    params: list[Any] = []
    if day is not None:
        sql += " WHERE CAST(ts AS DATE) = ?"
        params.append(day)
    sql += " ORDER BY ts"
    return fetchall_dict(sql, params)


def get_last_intraday_acc() -> dict[str, Any] | None:
    rows = fetchall_dict(
        "SELECT ts, acc_volume, acc_value FROM intraday_acc ORDER BY ts DESC LIMIT 1"
    )
    return rows[0] if rows else None


def get_last_intraday_acc_before(ts: datetime) -> dict[str, Any] | None:
    rows = fetchall_dict(
        "SELECT ts, acc_volume, acc_value FROM intraday_acc WHERE ts < ? ORDER BY ts DESC LIMIT 1",
        [ts],
    )
    return rows[0] if rows else None


def get_latest_daily_date() -> date | None:
    rows = fetchall("SELECT MAX(date) FROM daily_kline")
    return rows[0][0] if rows and rows[0][0] else None


def get_earliest_daily_date() -> date | None:
    rows = fetchall("SELECT MIN(date) FROM daily_kline")
    return rows[0][0] if rows and rows[0][0] else None


def get_missing_margin_dates(limit: int = 500) -> list[date]:
    """回傳 daily_kline 中尚未有融資融券資料的日期（最近的優先）。"""
    rows = fetchall_dict(
        """
        SELECT k.date
        FROM daily_kline k
        LEFT JOIN daily_margin m ON k.date = m.date
        WHERE m.date IS NULL
        ORDER BY k.date DESC
        LIMIT ?
        """,
        [limit],
    )
    return [r["date"] for r in rows]


def get_missing_volume_dates(limit: int = 5000) -> list[date]:
    """回傳 daily_kline 中尚未有成交量資料的日期（最近的優先）。"""
    rows = fetchall_dict(
        """
        SELECT k.date
        FROM daily_kline k
        LEFT JOIN daily_volume v ON k.date = v.date
        WHERE v.date IS NULL
        ORDER BY k.date DESC
        LIMIT ?
        """,
        [limit],
    )
    return [r["date"] for r in rows]


def get_latest_minute_ts() -> datetime | None:
    rows = fetchall("SELECT MAX(ts) FROM minute_kline")
    return rows[0][0] if rows and rows[0][0] else None
