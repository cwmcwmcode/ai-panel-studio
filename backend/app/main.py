"""FastAPI 应用入口。

启动时自动初始化 SQLite 结构；关闭时取消所有房间讨论协程。
CORS 放行 Vite 开发服务器，同时支持通过 Vite 代理同源访问。
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import CORS_ORIGINS
from app.db.database import init_db
from app.services.room_manager import room_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield
    await room_manager.shutdown()


app = FastAPI(title="AI Panel Studio API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """把路由层的 detail 统一收敛为契约中的 error 信封。"""
    detail: Any = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        error = detail["error"]
    else:
        error = {"code": "INTERNAL_ERROR", "message": str(detail), "details": {}}
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error, "meta": {"request_id": f"req_{uuid.uuid4().hex[:8]}"}},
    )


app.include_router(router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
