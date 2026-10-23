from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import settings
from .routes import kline, margin, volume
from .scheduler import start_scheduler, stop_scheduler
from .ws.realtime import manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    logger.info("DuckDB initialized at %s", settings.duckdb_path)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="TAIEX Chart API", version="1.0.0", lifespan=lifespan)


def _cors_origins() -> list[str]:
    return [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]


def origin_allowed(origin: str | None, host: str | None = None) -> bool:
    """WebSocket 的來源檢查；"*" 時放行（唯讀公開資料）。

    同源（前端與 WS 同一站台、經 nginx/Cloudflare/Traefik 同域代理）一律放行，
    跨站則需符合白名單——可相容 CORS_ORIGINS 與實際網域格式不一致的情況
    （如帶 www、port 或路徑差異）。
    """
    origins = _cors_origins()
    if "*" in origins:
        return True
    # 限制明確白名單時，缺少 Origin（非瀏覽器客戶端）一律拒絕
    if origin is None:
        return False
    origin = origin.rstrip("/")
    if origin in [o.rstrip("/") for o in origins]:
        return True
    origin_host = origin.split("://", 1)[-1].lower()
    req_host = (host or "").split(":", 1)[0].lower()
    return bool(origin_host) and bool(req_host) and origin_host == req_host


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    # 本 API 無 cookie/session 認證；"*" 時不得允許 credentials（規範亦禁止）
    allow_credentials="*" not in _cors_origins(),
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(kline.router)
app.include_router(volume.router)
app.include_router(margin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/realtime")
async def ws_realtime(ws: WebSocket):
    # 連線數上限與 Origin 白名單（防跨站 WebSocket 劫持與資源耗盡）
    if settings.ws_max_connections and manager.count() >= settings.ws_max_connections:
        await ws.close(code=1013)  # Try Again Later
        return
    if not origin_allowed(ws.headers.get("origin"), ws.headers.get("host")):
        await ws.close(code=1008)  # Policy Violation
        return
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)
