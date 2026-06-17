from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()
_last: dict[str, float] = {}


async def throttled_get_json(
    url: str,
    params: dict[str, str] | None = None,
    *,
    headers: dict[str, str] | None = None,
    min_interval: float | None = None,
    max_retries: int = 4,
    timeout: float | None = None,
) -> Any:
    return await _request(url, params=params, headers=headers, as_json=True,
                          min_interval=min_interval, max_retries=max_retries, timeout=timeout)


async def throttled_post_text(
    url: str,
    form: dict[str, str] | None = None,
    *,
    headers: dict[str, str] | None = None,
    min_interval: float | None = None,
    max_retries: int = 4,
    timeout: float | None = None,
) -> str:
    return await _request(url, form=form, headers=headers, as_json=False,
                          min_interval=min_interval, max_retries=max_retries, timeout=timeout)


async def _request(
    url: str,
    *,
    params: dict[str, str] | None = None,
    form: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    as_json: bool = True,
    min_interval: float | None = None,
    max_retries: int = 4,
    timeout: float | None = None,
) -> Any:
    """節流 + 指數退避的請求（GET 取 JSON／POST form 取文字）。

    - 以 host 為單位強制最小請求間隔（預設 settings.http_min_interval_sec）。
    - 遇 429 / 503 或網路例外時指數退避重試。
    - 全域鎖序化所有請求，避免併發突破節流。
    """
    host = httpx.URL(url).host
    interval = settings.http_min_interval_sec if min_interval is None else min_interval
    to = settings.http_timeout_sec if timeout is None else timeout

    async with _lock:
        elapsed = time.monotonic() - _last.get(host, 0.0)
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)

        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=to, headers=headers, follow_redirects=True
                ) as client:
                    if form is not None:
                        resp = await client.post(url, data=form)
                    else:
                        resp = await client.get(url, params=params)
                    if resp.status_code in (429, 503):
                        wait = min(2 ** attempt, 30)
                        logger.warning(
                            "throttled_request %s status %s, backoff %.1fs",
                            host,
                            resp.status_code,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    _last[host] = time.monotonic()
                    return resp.json() if as_json else resp.text
            except httpx.HTTPError as exc:
                last_exc = exc
                wait = min(2 ** attempt, 30)
                logger.warning("throttled_request %s error %s, retry in %.1fs", host, exc, wait)
                await asyncio.sleep(wait)

        _last[host] = time.monotonic()
        if last_exc is not None:
            raise last_exc
        return None
