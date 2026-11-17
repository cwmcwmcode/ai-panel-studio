"""SQLite 异步数据访问层。

- 使用 aiosqlite 打开 backend/data/panel_studio.db。
- 应用启动时执行 schema.sql 建表：仅在 rooms 表不存在时执行，避免重复 DROP
  造成运行期数据丢失（schema.sql 本身可作为开发期重建脚本）。
- 所有写操作显式 commit；查询统一返回普通 dict，便于路由层序列化。
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterable

import aiosqlite

from app.config import DATA_DIR, DATABASE_PATH, SCHEMA_PATH

_init_lock: asyncio.Lock | None = None


def utc_now() -> str:
    """返回与 schema.sql 一致的毫秒级 UTC ISO 时间。"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@asynccontextmanager
async def get_connection() -> AsyncIterator[aiosqlite.Connection]:
    """打开一个自动关闭的异步连接。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(DATABASE_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        await conn.close()


async def init_db() -> None:
    """启动时初始化数据库结构（幂等）。"""
    global _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()

    async with _init_lock:
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'rooms'"
            )
            exists = await cursor.fetchone()
            if exists:
                return

            schema = SCHEMA_PATH.read_text(encoding="utf-8")
            await conn.executescript(schema)
            await conn.commit()


# --------------------------------------------------------------------------- #
# rooms
# --------------------------------------------------------------------------- #
async def create_room(topic: str, expert_count: int) -> dict[str, Any]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO rooms (topic, status, expert_count) VALUES (?, 'draft', ?)",
            (topic, expert_count),
        )
        room_id = cursor.lastrowid
        await conn.commit()
    room = await fetch_room(room_id)
    assert room is not None
    return room


async def fetch_room(room_id: int) -> dict[str, Any] | None:
    async with get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


async def list_rooms(
    status: str | None = None, limit: int = 20, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    where_sql = "WHERE status = ?" if status else ""
    params: list[Any] = [status] if status else []

    async with get_connection() as conn:
        cursor = await conn.execute(f"SELECT COUNT(*) AS total FROM rooms {where_sql}", params)
        total_row = await cursor.fetchone()
        cursor = await conn.execute(
            f"SELECT * FROM rooms {where_sql} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        rows = await cursor.fetchall()

    return [dict(row) for row in rows], int(total_row["total"]) if total_row else 0


async def update_room_status(
    room_id: int,
    status: str,
    summary: str | None = None,
    finished_at: str | None = None,
) -> None:
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE rooms SET status = ?, summary = COALESCE(?, summary), "
            "finished_at = COALESCE(?, finished_at) WHERE id = ?",
            (status, summary, finished_at, room_id),
        )
        await conn.commit()


async def finish_room(room_id: int, summary: str) -> None:
    await update_room_status(room_id, "finished", summary=summary, finished_at=utc_now())


# --------------------------------------------------------------------------- #
# personas
# --------------------------------------------------------------------------- #
async def insert_personas(
    room_id: int, lineup: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    async with get_connection() as conn:
        for persona in lineup:
            await conn.execute(
                "INSERT INTO personas "
                "(room_id, name, title, stance, color_theme, is_host, current_status, current_focus) "
                "VALUES (?, ?, ?, ?, ?, ?, 'idle', ?)",
                (
                    room_id,
                    persona["name"],
                    persona["title"],
                    persona["stance"],
                    persona["color_theme"],
                    1 if persona["is_host"] else 0,
                    persona.get("current_focus") or persona.get("focus"),
                ),
            )
        await conn.commit()
    return await fetch_personas(room_id)


async def fetch_personas(room_id: int) -> list[dict[str, Any]]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM personas WHERE room_id = ? ORDER BY is_host DESC, id ASC",
            (room_id,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def update_persona_status(
    room_id: int, persona_id: int, status: str, focus: str | None = None
) -> None:
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE personas SET current_status = ?, "
            "current_focus = COALESCE(?, current_focus) WHERE room_id = ? AND id = ?",
            (status, focus, room_id, persona_id),
        )
        await conn.commit()


# --------------------------------------------------------------------------- #
# transcripts
# --------------------------------------------------------------------------- #
async def insert_transcript(
    room_id: int,
    persona_id: int,
    sequence_no: int,
    content: str,
    speech_type: str,
) -> dict[str, Any]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO transcripts "
            "(room_id, persona_id, sequence_no, content, speech_type) VALUES (?, ?, ?, ?, ?)",
            (room_id, persona_id, sequence_no, content, speech_type),
        )
        transcript_id = cursor.lastrowid
        await conn.commit()
        cursor = await conn.execute("SELECT * FROM transcripts WHERE id = ?", (transcript_id,))
        row = await cursor.fetchone()
    assert row is not None
    return dict(row)


async def fetch_transcripts(
    room_id: int, after_sequence_no: int = 0, limit: int = 500
) -> list[dict[str, Any]]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT t.*, p.name AS persona_name, p.color_theme, p.is_host "
            "FROM transcripts t JOIN personas p ON p.id = t.persona_id "
            "WHERE t.room_id = ? AND t.sequence_no > ? ORDER BY t.sequence_no ASC LIMIT ?",
            (room_id, after_sequence_no, limit),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# --------------------------------------------------------------------------- #
# insights
# --------------------------------------------------------------------------- #
async def save_insights(
    room_id: int, version: int, items: Iterable[dict[str, str]]
) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    async with get_connection() as conn:
        for item in items:
            cursor = await conn.execute(
                "INSERT INTO insights (room_id, type, content, version) VALUES (?, ?, ?, ?)",
                (room_id, item["type"], item["content"], version),
            )
            saved.append(
                {"id": cursor.lastrowid, "type": item["type"], "content": item["content"]}
            )
        await conn.commit()
    return saved


async def fetch_latest_insights(room_id: int) -> tuple[int, list[dict[str, Any]]]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT MAX(version) AS version FROM insights WHERE room_id = ?", (room_id,)
        )
        row = await cursor.fetchone()
        version = int(row["version"]) if row and row["version"] is not None else 0
        if version == 0:
            return 0, []

        cursor = await conn.execute(
            "SELECT id, type, content, version FROM insights "
            "WHERE room_id = ? AND version = ? ORDER BY id ASC",
            (room_id, version),
        )
        rows = await cursor.fetchall()
    return version, [dict(row) for row in rows]


async def fetch_progress(room_id: int) -> dict[str, int]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) AS count, COALESCE(MAX(sequence_no), 0) AS last_seq "
            "FROM transcripts WHERE room_id = ?",
            (room_id,),
        )
        transcript_row = await cursor.fetchone()
        cursor = await conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM insights WHERE room_id = ?",
            (room_id,),
        )
        insight_row = await cursor.fetchone()

    return {
        "transcript_count": int(transcript_row["count"]) if transcript_row else 0,
        "last_sequence_no": int(transcript_row["last_seq"]) if transcript_row else 0,
        "insight_version": int(insight_row["version"]) if insight_row else 0,
    }
