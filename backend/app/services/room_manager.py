"""多房间运行态管理与讨论调度循环。

隔离模型：
- 每个 room_id 对应一个 RoomRuntime，拥有独立的调度器、发言历史、序号、
  看板版本与订阅队列集合。
- 每个 SSE 连接订阅时获得独立的有界 asyncio.Queue；广播时把事件扇出到
  该房间的全部队列。不同房间之间没有任何共享可写状态，可完全并发运行。

讨论生命周期：
主持人开场 -> 调度器选拔专家交锋 -> 周期性提炼共识/分歧 -> 达到预设轮次
（或被提前要求结束）后主持人自然语言总结 -> 广播 summary 与 done。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.config import INSIGHT_INTERVAL, MAX_SPEECHES, MOCK_TOKEN_DELAY
from app.db import database
from app.services.insight_extractor import DialogueTurn, InsightBoard
from app.services.llm_service import LLMService, llm_service
from app.services.scheduler import (
    Persona,
    SpeechRecord,
    SpeechScheduler,
    SpeechValidationError,
)
from app.utils.sanitizer import (
    sanitize_focus,
    sanitize_insight,
    sanitize_summary,
    sanitize_transcript,
)

logger = logging.getLogger(__name__)

#: 每个 SSE 订阅队列的上限；token 洪峰时丢弃旧事件，由 speech_end 对齐终态
QUEUE_MAXSIZE = 512


@dataclass
class RoomRuntime:
    """一个讨论房间的独立运行态。"""

    room_id: int
    topic: str
    personas: list[dict[str, Any]]
    scheduler: SpeechScheduler
    history: list[SpeechRecord] = field(default_factory=list)
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    sequence_no: int = 0
    speeches: int = 0
    insight_version: int = 0
    board: InsightBoard = field(default_factory=InsightBoard)
    task: asyncio.Task | None = None
    started: bool = False
    finished: bool = False
    finish_event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def persona_map(self) -> dict[int, dict[str, Any]]:
        return {int(persona["id"]): persona for persona in self.personas}

    @property
    def host(self) -> dict[str, Any]:
        return next(persona for persona in self.personas if persona["is_host"])

    def dialogue(self) -> list[dict[str, Any]]:
        """转换为 LLM 可读的对话流。"""
        mapping = self.persona_map
        return [
            {
                "persona_id": record.persona_id,
                "speaker": mapping[record.persona_id]["name"]
                if record.persona_id in mapping
                else "嘉宾",
                "content": record.content,
            }
            for record in self.history
        ]


class RoomManager:
    """房间运行态注册表与讨论驱动器。"""

    def __init__(self, llm: LLMService | None = None) -> None:
        self._llm = llm or llm_service
        self._rooms: dict[int, RoomRuntime] = {}
        self._lineups: dict[int, list[dict[str, Any]]] = {}
        self._guard = asyncio.Lock()

    # ------------------------------------------------------------------ #
    # 注册与订阅
    # ------------------------------------------------------------------ #
    def cache_lineup(self, room_id: int, lineup: Sequence[dict[str, Any]]) -> None:
        """缓存含 stance_side 的阵容，供调度器使用。"""
        self._lineups[room_id] = [dict(item) for item in lineup]

    async def register(
        self, room: dict[str, Any], personas: Sequence[dict[str, Any]]
    ) -> RoomRuntime:
        """为房间建立（或复用）独立运行态。"""
        room_id = int(room["id"])
        existing = self._rooms.get(room_id)
        if existing is not None:
            return existing

        async with self._guard:
            existing = self._rooms.get(room_id)
            if existing is not None:
                return existing

            cached = self._lineups.get(room_id, [])
            side_by_name = {
                item.get("name"): item.get("stance_side", "neutral") for item in cached
            }
            runtime_personas = [
                {
                    **dict(persona),
                    "is_host": bool(persona["is_host"]),
                    "stance_side": side_by_name.get(persona["name"], "neutral"),
                    "focus": persona.get("current_focus") or "",
                    "status": "idle",
                }
                for persona in personas
            ]

            scheduler_personas = [
                Persona(
                    id=int(persona["id"]),
                    name=persona["name"],
                    stance=persona["stance"],
                    stance_side=persona["stance_side"],
                    is_host=persona["is_host"],
                    color_theme=persona["color_theme"],
                )
                for persona in runtime_personas
            ]

            runtime = RoomRuntime(
                room_id=room_id,
                topic=room["topic"],
                personas=runtime_personas,
                scheduler=SpeechScheduler(scheduler_personas),
            )

            # 进程重启后从数据库恢复历史与序号，避免 sequence_no 冲突
            rows = await database.fetch_transcripts(room_id, after_sequence_no=0, limit=500)
            for row in rows:
                speech_type = row["speech_type"]
                if speech_type not in {"intro", "speech", "counter", "summary"}:
                    speech_type = "speech"
                runtime.history.append(
                    SpeechRecord(
                        persona_id=int(row["persona_id"]),
                        sequence_no=int(row["sequence_no"]),
                        speech_type=speech_type,
                        content=row["content"],
                    )
                )
            runtime.sequence_no = max((record.sequence_no for record in runtime.history), default=0)
            runtime.speeches = sum(
                1 for record in runtime.history if record.speech_type != "intro"
            )
            version, _ = await database.fetch_latest_insights(room_id)
            runtime.insight_version = version

            self._rooms[room_id] = runtime
            return runtime

    async def subscribe(self, room_id: int) -> tuple[RoomRuntime, asyncio.Queue]:
        """订阅房间事件流，并在首个订阅者出现时启动讨论任务。"""
        runtime = self._rooms[room_id]
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        runtime.subscribers.add(queue)
        if not runtime.started:
            runtime.started = True
            runtime.task = asyncio.create_task(
                self._run_room(runtime), name=f"room-{room_id}"
            )
        return runtime, queue

    async def unsubscribe(self, room_id: int, queue: asyncio.Queue) -> None:
        """客户端断开时释放协程资源。"""
        runtime = self._rooms.get(room_id)
        if runtime is None:
            return
        runtime.subscribers.discard(queue)

    async def request_finish(self, room_id: int) -> bool:
        """请求提前收束：交给调度循环自然地完成主持总结。"""
        runtime = self._rooms.get(room_id)
        if runtime is None or runtime.finished:
            return False
        runtime.finish_event.set()
        return True

    async def shutdown(self) -> None:
        """应用关闭时取消全部房间任务。"""
        tasks = [runtime.task for runtime in self._rooms.values() if runtime.task]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ------------------------------------------------------------------ #
    # 广播
    # ------------------------------------------------------------------ #
    async def _broadcast(
        self,
        runtime: RoomRuntime,
        event: str,
        data: dict[str, Any],
        event_id: int | None = None,
    ) -> None:
        frame = {"event": event, "data": data, "id": event_id}
        for queue in list(runtime.subscribers):
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                # 丢弃最旧事件，保证慢客户端不会阻塞整个房间
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(frame)
                except asyncio.QueueFull:
                    logger.debug("房间 %s 队列持续拥塞，丢弃事件 %s", runtime.room_id, event)

    async def _set_status(
        self,
        runtime: RoomRuntime,
        persona: dict[str, Any],
        status: str,
        focus: str | None = None,
    ) -> None:
        safe_focus = sanitize_focus(focus) if focus else None
        persona["status"] = status
        if safe_focus:
            persona["focus"] = safe_focus
        await database.update_persona_status(
            runtime.room_id, int(persona["id"]), status, safe_focus
        )
        await self._broadcast(
            runtime,
            "status_change",
            {
                "room_id": runtime.room_id,
                "persona_id": int(persona["id"]),
                "status": status,
                "current_focus": persona.get("focus") or None,
                "changed_at": database.utc_now(),
            },
            event_id=runtime.sequence_no,
        )

    # ------------------------------------------------------------------ #
    # 讨论调度循环
    # ------------------------------------------------------------------ #
    async def _run_room(self, runtime: RoomRuntime) -> None:
        try:
            await database.update_room_status(runtime.room_id, "active")
            await self._deliver_host_intro(runtime)

            while runtime.speeches < MAX_SPEECHES and not runtime.finish_event.is_set():
                decision = runtime.scheduler.decide_next(runtime.history)
                persona = runtime.persona_map.get(decision.persona_id)
                if persona is None:
                    break

                await self._set_status(
                    runtime, persona, "thinking", persona.get("focus") or "正在组织观点"
                )
                await asyncio.sleep(0.2)

                chunks = self._llm.stream_speech(
                    runtime.topic,
                    persona,
                    runtime.dialogue(),
                    decision.speech_type,
                )
                await self._deliver_speech(
                    runtime,
                    persona,
                    decision.speech_type,
                    chunks,
                    validate=True,
                )
                runtime.speeches += 1

                if runtime.speeches % INSIGHT_INTERVAL == 0:
                    await self._refresh_insights(runtime)

            await self._refresh_insights(runtime)
            await self._finish(runtime)
        except asyncio.CancelledError:
            logger.info("房间 %s 讨论任务被取消", runtime.room_id)
            raise
        except Exception:
            logger.exception("房间 %s 讨论任务异常终止", runtime.room_id)
            await self._broadcast(
                runtime, "done", {"room_id": runtime.room_id, "status": "error"}
            )
        finally:
            runtime.finished = True

    async def _deliver_host_intro(self, runtime: RoomRuntime) -> None:
        host = runtime.host
        short_topic = runtime.topic if len(runtime.topic) <= 40 else runtime.topic[:39] + "…"
        intro = f"欢迎来到演播厅。本场议题是「{short_topic}」，请各位用一两句话亮明立场。"

        async def chunks():
            for index in range(0, len(intro), 2):
                yield intro[index : index + 2]
                await asyncio.sleep(MOCK_TOKEN_DELAY)

        await self._deliver_speech(runtime, host, "intro", chunks(), validate=False)

    async def _deliver_speech(
        self,
        runtime: RoomRuntime,
        persona: dict[str, Any],
        speech_type: str,
        chunks,
        validate: bool,
    ) -> None:
        """消费流式增量：逐 token 广播，落库后以 speech_end 定稿。"""
        await self._set_status(
            runtime, persona, "speaking", persona.get("focus") or None
        )
        runtime.sequence_no += 1
        sequence = runtime.sequence_no

        buffer: list[str] = []
        token_index = 0
        async for delta in chunks:
            if not delta:
                continue
            buffer.append(delta)
            await self._broadcast(
                runtime,
                "token",
                {
                    "room_id": runtime.room_id,
                    "persona_id": int(persona["id"]),
                    "sequence_no": sequence,
                    "speech_type": speech_type,
                    "delta": delta,
                    "token_index": token_index,
                },
                event_id=sequence,
            )
            token_index += 1

        raw = sanitize_transcript("".join(buffer))
        if validate:
            try:
                content = runtime.scheduler.validate_speech(raw)
            except SpeechValidationError:
                content = self._safe_fallback(raw, persona)
        else:
            content = raw or "欢迎来到演播厅，本场讨论正式开始。"
        content = sanitize_transcript(content) or self._safe_fallback("", persona)

        row = await database.insert_transcript(
            runtime.room_id, int(persona["id"]), sequence, content, speech_type
        )
        runtime.history.append(
            SpeechRecord(
                persona_id=int(persona["id"]),
                sequence_no=sequence,
                speech_type=speech_type,
                content=content,
            )
        )

        await self._broadcast(
            runtime,
            "speech_end",
            {
                "room_id": runtime.room_id,
                "transcript_id": int(row["id"]),
                "persona_id": int(persona["id"]),
                "sequence_no": sequence,
                "speech_type": speech_type,
                "content": content,
                "sentence_count": content.count("。") + content.count("！") + content.count("？") or 1,
                "char_count": len(content),
                "created_at": row["created_at"],
            },
            event_id=sequence,
        )
        await self._set_status(runtime, persona, "idle", persona.get("focus") or None)

    @staticmethod
    def _safe_fallback(raw: str, persona: dict[str, Any]) -> str:
        text = sanitize_transcript(raw) or f"{persona['name']}认为需要更多数据才能判断。"
        if len(text) < 20:
            text = f"{text}，这是我基于当前信息能给出的判断。"
        if len(text) > 80:
            text = text[:79].rstrip("，,、；;：: ") + "。"
        return text

    # ------------------------------------------------------------------ #
    # 洞察与总结
    # ------------------------------------------------------------------ #
    async def _refresh_insights(self, runtime: RoomRuntime) -> None:
        turns = [
            DialogueTurn(speaker=item["speaker"], content=item["content"])
            for item in runtime.dialogue()
        ]
        board = await self._llm.extract_insights(runtime.topic, turns)
        if not board.consensus and not board.divergence:
            return

        runtime.insight_version += 1
        runtime.board = board
        items = [
            {"type": "consensus", "content": text}
            for text in (sanitize_insight(item) for item in board.consensus)
            if text
        ]
        items += [
            {"type": "divergence", "content": text}
            for text in (sanitize_insight(item) for item in board.divergence)
            if text
        ]
        if not items:
            return
        saved = await database.save_insights(runtime.room_id, runtime.insight_version, items)

        await self._broadcast(
            runtime,
            "insight_update",
            {
                "room_id": runtime.room_id,
                "version": runtime.insight_version,
                "items": [
                    {**item, "version": runtime.insight_version} for item in saved
                ],
                "updated_at": database.utc_now(),
            },
            event_id=runtime.insight_version,
        )

    async def _finish(self, runtime: RoomRuntime) -> None:
        host = runtime.host
        result = await self._llm.generate_summary(
            runtime.topic, runtime.dialogue(), runtime.board
        )
        summary_text = sanitize_summary(result.get("summary") or "")
        consensus = [
            text
            for text in (sanitize_insight(item) for item in result.get("consensus") or [])
            if text
        ] or list(runtime.board.consensus)
        divergence = [
            text
            for text in (sanitize_insight(item) for item in result.get("divergence") or [])
            if text
        ] or list(runtime.board.divergence)
        suggestions = [
            text
            for text in (sanitize_insight(item) for item in result.get("suggestions") or [])
            if text
        ]

        await database.finish_room(runtime.room_id, summary_text)
        await self._set_status(runtime, host, "speaking", "收束全场观点")

        runtime.sequence_no += 1
        sequence = runtime.sequence_no
        row = await database.insert_transcript(
            runtime.room_id, int(host["id"]), sequence, summary_text, "summary"
        )
        runtime.history.append(
            SpeechRecord(
                persona_id=int(host["id"]),
                sequence_no=sequence,
                speech_type="summary",
                content=summary_text,
            )
        )

        # 总结文本同样以 token 推送，前端在气泡中看到主持人陈词
        token_index = 0
        for index in range(0, len(summary_text), 3):
            delta = summary_text[index : index + 3]
            await self._broadcast(
                runtime,
                "token",
                {
                    "room_id": runtime.room_id,
                    "persona_id": int(host["id"]),
                    "sequence_no": sequence,
                    "speech_type": "summary",
                    "delta": delta,
                    "token_index": token_index,
                },
                event_id=sequence,
            )
            token_index += 1
            await asyncio.sleep(MOCK_TOKEN_DELAY)

        await self._broadcast(
            runtime,
            "speech_end",
            {
                "room_id": runtime.room_id,
                "transcript_id": int(row["id"]),
                "persona_id": int(host["id"]),
                "sequence_no": sequence,
                "speech_type": "summary",
                "content": summary_text,
                "sentence_count": summary_text.count("。") or 1,
                "char_count": len(summary_text),
                "created_at": row["created_at"],
            },
            event_id=sequence,
        )

        await self._broadcast(
            runtime,
            "summary",
            {
                "room_id": runtime.room_id,
                "persona_id": int(host["id"]),
                "transcript_id": int(row["id"]),
                "summary": summary_text,
                "consensus": consensus,
                "divergence": divergence,
                "suggestions": suggestions,
                "finished_at": database.utc_now(),
            },
            event_id=sequence,
        )
        await self._broadcast(
            runtime,
            "done",
            {"room_id": runtime.room_id, "status": "finished"},
            event_id=sequence,
        )


room_manager = RoomManager()
