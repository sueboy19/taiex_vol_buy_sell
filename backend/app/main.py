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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
