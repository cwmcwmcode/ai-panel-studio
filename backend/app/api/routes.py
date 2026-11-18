"""REST + SSE 路由。

SSE 严格输出 SDD 约定的六类事件帧：
token / status_change / insight_update / speech_end / summary / done。
客户端断开时通过生成器的 finally 释放订阅队列。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db import database
from app.services.llm_service import llm_service
from app.services.room_manager import room_manager

router = APIRouter()

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class CreateRoomRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    expert_count: int = Field(default=4, ge=1, le=8)
    style: Literal["balanced", "debate", "exploratory"] = "balanced"


def _request_id() -> str:
    return f"req_{uuid.uuid4().hex[:8]}"


def _ok(data: Any, **meta: Any) -> dict[str, Any]:
    return {"data": data, "meta": {"request_id": _request_id(), **meta}}


def _error(status_code: int, code: str, message: str, **details: Any) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details}},
    )


def _room_payload(room: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": room["id"],
        "topic": room["topic"],
        "status": room["status"],
        "expert_count": room["expert_count"],
        "summary": room["summary"],
        "created_at": room["created_at"],
        "finished_at": room["finished_at"],
    }


def _persona_payload(persona: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": persona["id"],
        "name": persona["name"],
        "title": persona["title"],
        "stance": persona["stance"],
        "color_theme": persona["color_theme"],
        "is_host": bool(persona["is_host"]),
        "current_status": persona["current_status"],
        "current_focus": persona["current_focus"],
    }


# --------------------------------------------------------------------------- #
# REST
# --------------------------------------------------------------------------- #
@router.get("/rooms")
async def list_rooms(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    if status and status not in {"draft", "active", "finished"}:
        raise _error(400, "INVALID_PARAMETER", "status 取值非法")

    rows, total = await database.list_rooms(status, page_size, (page - 1) * page_size)
    data = []
    for room in rows:
        summary = room.get("summary") or ""
        data.append(
            {
                **_room_payload(room),
                "summary_excerpt": summary[:60],
            }
        )
    return _ok(data, total=total, has_more=page * page_size < total)


@router.post("/rooms", status_code=201)
async def create_room(payload: CreateRoomRequest) -> dict[str, Any]:
    topic = payload.topic.strip()
    if not topic:
        raise _error(400, "INVALID_PARAMETER", "议题不能为空")
    if len(topic) > 200:
        raise _error(422, "TOPIC_TOO_LONG", "议题不能超过 200 字")

    room = await database.create_room(topic, payload.expert_count)
    lineup = await llm_service.generate_lineup(topic, payload.expert_count, payload.style)
    personas = await database.insert_personas(int(room["id"]), lineup)
    room_manager.cache_lineup(int(room["id"]), lineup)

    return _ok(
        {
            "room": _room_payload(room),
            "personas": [_persona_payload(persona) for persona in personas],
        },
        degraded=llm_service.demo_mode,
    )


@router.get("/rooms/{room_id}")
async def get_room(room_id: int) -> dict[str, Any]:
    room = await database.fetch_room(room_id)
    if room is None:
        raise _error(404, "ROOM_NOT_FOUND", "房间不存在", room_id=room_id)

    personas = await database.fetch_personas(room_id)
    transcripts = await database.fetch_transcripts(room_id)
    progress = await database.fetch_progress(room_id)
    version, items = await database.fetch_latest_insights(room_id)

    return _ok(
        {
            "room": _room_payload(room),
            "personas": [_persona_payload(persona) for persona in personas],
            "transcripts": [
                {
                    "id": transcript["id"],
                    "persona_id": transcript["persona_id"],
                    "persona_name": transcript.get("persona_name") or "",
                    "color_theme": transcript.get("color_theme") or "#8B93A7",
                    "is_host": bool(transcript.get("is_host")),
                    "sequence_no": transcript["sequence_no"],
                    "content": transcript["content"],
                    "speech_type": transcript["speech_type"],
                    "created_at": transcript["created_at"],
                }
                for transcript in transcripts
            ],
            "insights": {"version": version, "items": items},
            "progress": progress,
        }
    )


@router.post("/rooms/{room_id}/start")
async def start_room(room_id: int) -> dict[str, Any]:
    room = await database.fetch_room(room_id)
    if room is None:
        raise _error(404, "ROOM_NOT_FOUND", "房间不存在", room_id=room_id)
    if room["status"] == "finished":
        raise _error(409, "INVALID_STATE_TRANSITION", "已结束的房间无法重新启动")

    if room["status"] == "draft":
        await database.update_room_status(room_id, "active")
        room = await database.fetch_room(room_id)

    personas = await database.fetch_personas(room_id)
    await room_manager.register(room, personas)

    return _ok(
        {
            "id": room_id,
            "status": room["status"],
            "events_url": f"/api/rooms/{room_id}/events",
        }
    )


@router.post("/rooms/{room_id}/finish")
async def finish_room(room_id: int) -> dict[str, Any]:
    """提前收束：通知调度循环进入主持人总结阶段。"""
    room = await database.fetch_room(room_id)
    if room is None:
        raise _error(404, "ROOM_NOT_FOUND", "房间不存在", room_id=room_id)
    if room["status"] != "active":
        raise _error(409, "ROOM_NOT_ACTIVE", "仅进行中的房间可以结束")

    accepted = await room_manager.request_finish(room_id)
    return _ok({"id": room_id, "status": "finishing" if accepted else room["status"]})


# --------------------------------------------------------------------------- #
# SSE
# --------------------------------------------------------------------------- #
def _sse_frame(frame: dict[str, Any]) -> str:
    lines: list[str] = []
    if frame.get("id") is not None:
        lines.append(f"id: {frame['id']}")
    lines.append(f"event: {frame['event']}")
    lines.append(f"data: {json.dumps(frame['data'], ensure_ascii=False, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


@router.get("/rooms/{room_id}/events")
async def room_events(room_id: int, request: Request) -> StreamingResponse:
    room = await database.fetch_room(room_id)
    if room is None:
        raise _error(404, "ROOM_NOT_FOUND", "房间不存在", room_id=room_id)
    if room["status"] != "active":
        raise _error(
            409,
            "ROOM_NOT_ACTIVE",
            f"房间当前状态为 {room['status']}，无法建立事件通道",
            room_id=room_id,
            status=room["status"],
        )

    personas = await database.fetch_personas(room_id)
    await room_manager.register(room, personas)
    _, queue = await room_manager.subscribe(room_id)

    async def event_stream():
        try:
            # 首个事件告知客户端已接入
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue

                yield _sse_frame(frame)
                if frame["event"] == "done":
                    break
        except asyncio.CancelledError:
            raise
        finally:
            await room_manager.unsubscribe(room_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)
