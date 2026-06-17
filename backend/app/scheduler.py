from __future__ import annotations

import logging
from datetime import date
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import aggregator, db, twse_client, yahoo_client
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
