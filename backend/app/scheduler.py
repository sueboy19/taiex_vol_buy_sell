from __future__ import annotations

import logging
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import aggregator, db, finmind_client, taifex_client, twse_client, yahoo_client
from .config import settings
from .market_time import is_after_close, is_market_open, is_trading_day, now_tw
from .models import to_ms
from .ws.realtime import manager

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None
_tz = ZoneInfo(settings.tz_name)

INTRADAY_JOBS = ("intraday_index", "intraday_volume")


async def job_intraday_index() -> None:
    """盤中：每 N 秒從 Yahoo 取得分鐘K指數，寫入 DB 並推播。"""
    bars = await yahoo_client.fetch_intraday_minute_kline()
    if not bars:
        return
    db.upsert_minute_kline(bars)
    latest = bars[-1]
    ts_minute = latest["ts"].replace(second=0, microsecond=0)
    vol_row = db.fetchone_dict(
        "SELECT volume FROM minute_kline WHERE ts = ?", [ts_minute]
    )
    volume = int((vol_row or {}).get("volume") or 0)
    await manager.broadcast(
        {
            "type": "minute",
            "timestamp": to_ms(latest["ts"]),
            "open": latest["open"],
            "high": latest["high"],
            "low": latest["low"],
            "close": latest["close"],
            "volume": volume,
        }
    )


async def job_intraday_volume() -> None:
    """盤中：每 N 秒從 TWSE MI_5MINS 取累計量，計算差值更新分鐘量。"""
    latest = await twse_client.fetch_intraday_5min()
    if latest is None:
        return
    updates = aggregator.compute_minute_volumes(latest)
    if updates:
        db.upsert_minute_kline(updates)
        u = updates[0]
        await manager.broadcast(
            {
                "type": "volume",
                "timestamp": to_ms(u["ts"]),
                "volume": int(u["volume"]),
            }
        )


async def job_daily_fetch() -> None:
    """收盤後：抓取日線、成交量、融資融券。"""
    if not is_trading_day():
        return
    today = date.today()

    kline = await twse_client.fetch_daily_kline(today)
    if kline:
        db.upsert_daily_kline(kline)
        logger.info("daily_kline upserted: %d rows", len(kline))

    vol = await twse_client.fetch_daily_volume(today)
    if vol:
        db.upsert_daily_volume(vol)
        logger.info("daily_volume upserted: %d rows", len(vol))

    margin = await twse_client.fetch_daily_margin(today)
    if margin:
        db.upsert_daily_margin(margin)
        logger.info("daily_margin upserted: %d rows", len(margin))

    ff = await taifex_client.fetch_foreign_future_oi(today)
    if ff:
        db.upsert_daily_foreign_future([ff])
        logger.info("daily_foreign_future upserted: %s", ff.get("date"))


async def backfill_foreign_future_taifex() -> None:
    """以期交所回填外資台指期貨未平倉口數歷史（每日一次請求，節流）。

    守衛：若與日線相比無缺漏，直接跳過。
    """
    rows = db.fetchall_dict(
        """
        SELECT k.date
        FROM daily_kline k
        LEFT JOIN daily_foreign_future f ON k.date = f.date
        WHERE f.date IS NULL
        ORDER BY k.date DESC
        LIMIT ?
        """,
        [settings.taifex_backfill_days],
    )
    if not rows:
        logger.info("foreign future history already complete, skip TAIFEX")
        return
    total = 0
    for r in rows:
        d = r["date"]
        ff = await taifex_client.fetch_foreign_future_oi(d)
        if ff:
            db.upsert_daily_foreign_future([ff])
            total += 1
    logger.info("TAIFEX foreign future backfilled: %d rows", total)


def _add_intraday_jobs() -> None:
    """動態加入盤中 interval jobs。"""
    assert _scheduler is not None
    if _scheduler.get_job("intraday_index") is None:
        _scheduler.add_job(
            job_intraday_index,
            "interval",
            seconds=settings.intraday_index_interval_sec,
            id="intraday_index",
            max_instances=1,
            replace_existing=True,
        )
    if _scheduler.get_job("intraday_volume") is None:
        _scheduler.add_job(
            job_intraday_volume,
            "interval",
            seconds=settings.intraday_volume_interval_sec,
            id="intraday_volume",
            max_instances=1,
            replace_existing=True,
        )
    logger.info("Intraday jobs started (market session open)")


def _remove_intraday_jobs() -> None:
    """動態移除盤中 interval jobs。"""
    assert _scheduler is not None
    for job_id in INTRADAY_JOBS:
        if _scheduler.get_job(job_id) is not None:
            _scheduler.remove_job(job_id)
    logger.info("Intraday jobs stopped (market session closed)")


def job_market_open() -> None:
    """開盤（09:00）：加入盤中 jobs。"""
    if is_trading_day():
        _add_intraday_jobs()


def job_market_close() -> None:
    """收盤（13:30）：移除盤中 jobs。"""
    _remove_intraday_jobs()


async def job_backfill_check() -> None:
    """啟動後檢查：若在盤中加入即時 jobs；若已收盤且資料缺漏則補抓。"""
    if is_market_open():
        _add_intraday_jobs()
    if is_after_close() and is_trading_day():
        last = db.get_latest_daily_date()
        today = date.today()
        if last is None or last < today:
            logger.info("backfill detected gap, fetching daily data...")
            await job_daily_fetch()
    await backfill_minute_kline()
    await backfill_daily_kline_yahoo()
    await backfill_volume_finmind()
    await backfill_margin_finmind()
    await backfill_foreign_future_taifex()


async def backfill_minute_kline() -> None:
    """收盤後補抓近日分鐘 K 線（Yahoo），讓「分鐘」圖不致全空。"""
    if not is_trading_day():
        return
    bars = await yahoo_client.fetch_intraday_minute_kline("5d")
    if bars:
        db.upsert_minute_kline(bars)
        logger.info("minute_kline backfilled: %d rows", len(bars))


async def backfill_daily_kline_yahoo() -> None:
    """以 Yahoo 回填日線歷史（一次抓 5 年）。

    守衛：若 daily_kline 最早日期已早於一年前，代表歷史足夠，直接跳過。
    """
    earliest = db.get_earliest_daily_date()
    threshold = date.today() - timedelta(days=365)
    if earliest is not None and earliest <= threshold:
        logger.info("daily kline history sufficient (earliest=%s), skip Yahoo", earliest)
        return
    bars = await yahoo_client.fetch_daily_kline_yahoo("5y")
    if bars:
        db.upsert_daily_kline(bars)
        logger.info("Yahoo daily kline backfilled: %d rows (earliest now %s)", len(bars), bars[0]["date"])


async def backfill_volume_finmind() -> None:
    """以 FinMind（TAIEX）回填大盤成交量歷史。

    守衛：若 daily_kline 的日期皆已有成交量，直接跳過（不呼叫 FinMind）。
    TAIEX 為單列/日，無 500 列截斷問題，可一次抓整段。
    """
    missing = db.get_missing_volume_dates()
    if not missing:
        logger.info("volume history already complete, skip FinMind")
        return
    start, end = min(missing), max(missing)
    rows = await finmind_client.fetch_market_volume(start, end)
    if rows:
        db.upsert_daily_volume(rows)
        logger.info(
            "FinMind volume backfilled: %d rows (%s ~ %s)", len(rows), start, end
        )
    else:
        logger.warning("FinMind volume backfill returned no rows for %s ~ %s", start, end)


async def backfill_margin_finmind() -> None:
    """以 FinMind 回填全市場融資融券歷史（分段避開單次 500 列上限）。

    守衛：若 daily_kline 的日期皆已有融資融券，直接跳過（不呼叫 FinMind）。
    只抓「含有缺失日期」的區段，已完整的區段不重複請求。
    """
    missing = db.get_missing_margin_dates(limit=10000)
    if not missing:
        logger.info("margin history already complete, skip FinMind")
        return
    missing_set = set(missing)
    start_all, end_all = min(missing), max(missing)

    chunk_days = 150  # 每段約 150 日 × 3 名稱 ≈ 450 列 < FinMind 500 列上限
    total = 0
    cur = start_all
    while cur <= end_all:
        seg_end = min(cur + timedelta(days=chunk_days - 1), end_all)
        # 此區段含有缺失日期才抓
        has_gap = any(
            cur + timedelta(days=i) in missing_set
            for i in range((seg_end - cur).days + 1)
        )
        if has_gap:
            rows = await finmind_client.fetch_market_margin(cur, seg_end)
            if rows:
                db.upsert_daily_margin(rows)
                total += len(rows)
        cur = seg_end + timedelta(days=1)
    logger.info(
        "FinMind margin backfill done: %d rows (%s ~ %s)", total, start_all, end_all
    )


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone=_tz)

    # 開盤加入 jobs
    _scheduler.add_job(
        job_market_open,
        "cron",
        hour=9,
        minute=0,
        second=0,
        day_of_week="mon-fri",
        id="market_open",
    )
    # 收盤移除 jobs
    _scheduler.add_job(
        job_market_close,
        "cron",
        hour=13,
        minute=30,
        second=0,
        day_of_week="mon-fri",
        id="market_close",
    )
    # 收盤後抓日資料
    _scheduler.add_job(
        job_daily_fetch,
        "cron",
        hour=settings.daily_fetch_hour,
        minute=settings.daily_fetch_minute,
        day_of_week="mon-fri",
        id="daily_fetch",
    )
    # 啟動時檢查當前狀態
    _scheduler.add_job(
        job_backfill_check,
        "date",
        run_date=now_tw(),
        id="backfill_init",
    )

    _scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
