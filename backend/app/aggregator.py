from __future__ import annotations

from typing import Any

from . import db


def compute_minute_volumes(latest_acc: dict[str, Any]) -> list[dict[str, Any]]:
    """根據最新累計量與資料庫中上一筆累計量，計算分鐘成交量。

    將差值寫入 minute_kline 中對應分鐘的 volume 欄位。
    回傳需要更新的 minute_kline 條目 list。
    """
    prev = db.get_last_intraday_acc_before(latest_acc["ts"])
    if prev is None:
        diff_vol = latest_acc["acc_volume"]
        diff_val = latest_acc["acc_value"]
    else:
        diff_vol = max(0, latest_acc["acc_volume"] - prev["acc_volume"])
        diff_val = max(0, latest_acc["acc_value"] - prev["acc_value"])

    ts_minute = latest_acc["ts"].replace(second=0, microsecond=0)

    existing = db.fetchone_dict(
        "SELECT ts, open, high, low, close, volume FROM minute_kline WHERE ts = ?",
        [ts_minute],
    )

    updates: list[dict[str, Any]] = []
    if existing:
        new_vol = (existing.get("volume") or 0) + diff_vol
        updates.append(
            {
                "ts": ts_minute,
                "open": existing["open"],
                "high": existing["high"],
                "low": existing["low"],
                "close": existing["close"],
                "volume": new_vol,
            }
        )
    db.upsert_intraday_acc([latest_acc])
    return updates
