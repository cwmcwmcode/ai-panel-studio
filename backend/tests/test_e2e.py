"""系统级端到端测试：创建议题 -> 阵容契约 -> SSE 全链路 -> 数据库终态。

测试完全跑在临时 SQLite 与 Mock 流式模式下，不依赖真实 LLM 与外部网络。

覆盖的验收标准：
- 1 位主持人 + 4 位专家，色标为合法且互不重复的十六进制值。
- SSE 六类事件（token / status_change / insight_update / speech_end / summary /
  done）载荷均为合法 JSON，且不含代码围栏、JSON 键值或控制字符。
- 总结词为纯自然语言；专家公开摘要不超过 15 字，不暴露思维链。
- 房间终态、速记、看板均正确持久化到 SQLite。
"""

from __future__ import annotations

import json
import re

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
FORBIDDEN_TEXT = ("```", "{", "}", '"summary"', "系统通知", "[举手]", "[反驳]")
SSE_EVENTS = {"token", "status_change", "insight_update", "speech_end", "summary", "done"}


async def _parse_sse(response: httpx.Response) -> list[tuple[str, dict]]:
    """把 SSE 字节流解析为 (event, data) 列表。"""
    frames: list[tuple[str, dict]] = []
    event: str | None = None
    data_lines: list[str] = []

    async for line in response.aiter_lines():
        if line == "":
            if event is not None and data_lines:
                frames.append((event, json.loads("\n".join(data_lines))))
            event, data_lines = None, []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())

    if event is not None and data_lines:
        frames.append((event, json.loads("\n".join(data_lines))))
    return frames


@pytest.mark.asyncio
async def test_e2e_round_table_stream_and_persistence(tmp_path, monkeypatch):
    from app.db import database
    from app.main import app
    from app.services import llm_service as llm_module
    from app.services import room_manager as rm_module
    from app.services.room_manager import room_manager

    # 临时数据库 + 零延迟 Mock 流，保证测试隔离且快速
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "e2e.db")
    monkeypatch.setattr(database, "_init_lock", None)
    monkeypatch.setattr(llm_module, "MOCK_TOKEN_DELAY", 0.0)
    monkeypatch.setattr(rm_module, "MOCK_TOKEN_DELAY", 0.0)
    room_manager._rooms.clear()
    room_manager._lineups.clear()

    # ASGITransport 不执行 lifespan，需手动建表
    await database.init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", timeout=httpx.Timeout(30.0)
    ) as client:
        # -------------------------------------------------------------- #
        # 1. 创建议题：校验 1 主持 + 4 专家的数据契约
        # -------------------------------------------------------------- #
        topic = "AI 圆桌讨论端到端验收：AGI 是否应享有基础数字人权"
        created = await client.post(
            "/api/rooms", json={"topic": topic, "expert_count": 4}
        )
        assert created.status_code == 201, created.text
        payload = created.json()["data"]
        room = payload["room"]
        personas = payload["personas"]
        room_id = room["id"]

        assert room["topic"] == topic
        assert room["status"] == "draft"
        assert len(personas) == 5

        hosts = [item for item in personas if item["is_host"]]
        experts = [item for item in personas if not item["is_host"]]
        assert len(hosts) == 1 and len(experts) == 4

        colors = [item["color_theme"] for item in personas]
        assert len(set(colors)) == 5
        assert all(COLOR_PATTERN.match(color) for color in colors)

        for persona in personas:
            assert persona["name"] and persona["title"] and persona["stance"]
            assert persona["current_status"] == "idle"
            assert len(persona["current_focus"] or "") <= 15

        # -------------------------------------------------------------- #
        # 2. 启动房间
        # -------------------------------------------------------------- #
        started = await client.post(f"/api/rooms/{room_id}/start")
        assert started.status_code == 200, started.text
        assert started.json()["data"]["status"] == "active"

        # -------------------------------------------------------------- #
        # 3. 消费 SSE 全链路
        # -------------------------------------------------------------- #
        async with client.stream("GET", f"/api/rooms/{room_id}/events") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            frames = await _parse_sse(response)

        assert frames, "SSE 事件流为空"
        seen = {event for event, _ in frames}
        assert SSE_EVENTS <= seen, f"缺失事件：{SSE_EVENTS - seen}"

        token_count = 0
        summary_payload: dict | None = None
        for event, data in frames:
            # 任何事件都不得出现乱码
            dumped = json.dumps(data, ensure_ascii=False)
            assert "\ufffd" not in dumped, f"{event} 事件出现乱码"

            if event == "token":
                token_count += 1
                assert data["room_id"] == room_id
                assert isinstance(data["delta"], str) and data["delta"]
                assert data["speech_type"] in {"intro", "speech", "counter", "summary"}
                assert isinstance(data["token_index"], int)
                for marker in ("系统通知", "[举手]", "[反驳]"):
                    assert marker not in data["delta"]

            elif event == "status_change":
                assert data["status"] in {"idle", "thinking", "speaking"}
                focus = data.get("current_focus")
                if focus is not None:
                    assert isinstance(focus, str) and 0 < len(focus) <= 15
                    assert "思维链" not in focus and "关注焦点:" not in focus

            elif event == "insight_update":
                assert data["version"] >= 1
                assert data["items"], "洞察更新不得为空"
                for item in data["items"]:
                    assert item["type"] in {"consensus", "divergence"}
                    assert item["content"] and len(item["content"]) <= 300
                    for marker in FORBIDDEN_TEXT:
                        assert marker not in item["content"]

            elif event == "speech_end":
                assert data["content"] and data["char_count"] == len(data["content"])
                for marker in ("系统通知", "[举手]", "[反驳]"):
                    assert marker not in data["content"]

            elif event == "summary":
                summary_payload = data
                text = data["summary"]
                assert isinstance(text, str) and text
                # 总结词必须是纯自然语言：无 JSON 结构、无代码围栏、无键名
                for marker in FORBIDDEN_TEXT:
                    assert marker not in text
                assert text.endswith(("。", "！", "？", "…"))
                assert isinstance(data["consensus"], list)
                assert isinstance(data["divergence"], list)
                assert isinstance(data["suggestions"], list)

            elif event == "done":
                assert data["status"] == "finished"

        assert token_count >= 50, f"token 数量异常：{token_count}"
        assert summary_payload is not None

        # -------------------------------------------------------------- #
        # 4. 校验数据库最终持久化状态
        # -------------------------------------------------------------- #
        detail = await client.get(f"/api/rooms/{room_id}")
        assert detail.status_code == 200
        body = detail.json()["data"]
        assert body["room"]["status"] == "finished"
        assert body["room"]["summary"]
        assert body["room"]["finished_at"]
        assert body["progress"]["transcript_count"] >= 9
        assert body["progress"]["insight_version"] >= 1

    stored_room = await database.fetch_room(room_id)
    assert stored_room is not None
    assert stored_room["status"] == "finished"
    assert stored_room["summary"] and stored_room["finished_at"]
    assert len(stored_room["summary"]) <= 600

    stored_personas = await database.fetch_personas(room_id)
    assert len(stored_personas) == 5
    assert sum(1 for item in stored_personas if item["is_host"]) == 1

    transcripts = await database.fetch_transcripts(room_id)
    assert len(transcripts) >= 9
    assert transcripts[-1]["speech_type"] == "summary"
    assert transcripts[-1]["content"] == stored_room["summary"]
    sequences = [row["sequence_no"] for row in transcripts]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)
    for row in transcripts:
        assert row["content"].strip()
        for marker in ("系统通知", "[举手]", "[反驳]"):
            assert marker not in row["content"]

    version, insights = await database.fetch_latest_insights(room_id)
    assert version >= 1
    assert insights
    assert {item["type"] for item in insights} <= {"consensus", "divergence"}
    for item in insights:
        assert 0 < len(item["content"]) <= 300
        for marker in FORBIDDEN_TEXT:
            assert marker not in item["content"]
