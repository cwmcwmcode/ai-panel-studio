"""大模型服务封装。

三项能力：
1. 动态生成阵容：1 位主持人 + N 位立场鲜明的专家，色标由服务端按调色板分配，
   保证同一房间内颜色唯一（与 schema.sql 的唯一索引一致）。
2. 流式生成单次短发言：严格约束为 1-2 句、20-80 字的核心观点。
3. 实时提炼共识 / 分歧并生成主持人总结。

未配置 LLM_API_KEY 时自动进入 Mock 演示模式：同样按字符分段产出流式 token，
前端无需任何改动即可跑通完整的打字机交互。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, AsyncIterator, Sequence

from app.config import (
    DEMO_MODE,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    MOCK_TOKEN_DELAY,
)
from app.services.insight_extractor import (
    DialogueTurn,
    InsightBoard,
    InsightExtractor,
)
from app.utils.sanitizer import (
    StreamingSanitizer,
    sanitize_focus,
    sanitize_insight,
    sanitize_summary,
    sanitize_transcript,
)

logger = logging.getLogger(__name__)

HOST_COLOR_POOL = ["#8B93A7", "#6C7A89", "#94A3B8"]
EXPERT_COLORS = [
    "#E4572E",
    "#2E86AB",
    "#7A9E3F",
    "#B565A7",
    "#F2A541",
    "#38BDF8",
    "#F97316",
    "#06B6D4",
]
HOST_COLOR_POOL = ["#8B93A7", "#6C7A89", "#94A3B8"]

_FALLBACK_EXPERTS = [
    {
        "name": "林岸",
        "title": "平台架构师",
        "stance": "支持立即拆分，认为组织规模已到临界点",
        "stance_side": "pro",
        "focus": "评估组织边界是否达标",
    },
    {
        "name": "周砚",
        "title": "单体系统维护者",
        "stance": "反对过早拆分，强调分布式复杂度成本",
        "stance_side": "con",
        "focus": "警惕分布式复杂度成本",
    },
    {
        "name": "许听",
        "title": "组织效能顾问",
        "stance": "条件性支持，主张先改组织再谈架构",
        "stance_side": "pro",
        "focus": "先改组织再谈架构",
    },
    {
        "name": "顾临",
        "title": "成本与稳定性工程师",
        "stance": "审慎怀疑，关注运维负担与故障面扩大",
        "stance_side": "neutral",
        "focus": "关注运维负担与故障面",
    },
    {
        "name": "闻舒",
        "title": "交付效率研究员",
        "stance": "拆分收益取决于团队自治程度",
        "stance_side": "pro",
        "focus": "衡量团队自治成熟度",
    },
    {
        "name": "程澈",
        "title": "数据平台负责人",
        "stance": "主张以数据指标驱动拆分决策",
        "stance_side": "neutral",
        "focus": "用指标衡量拆分收益",
    },
    {
        "name": "白桦",
        "title": "一线业务负责人",
        "stance": "担心拆分拖慢业务迭代节奏",
        "stance_side": "con",
        "focus": "关注业务迭代节奏",
    },
    {
        "name": "叶蓁",
        "title": "技术战略顾问",
        "stance": "支持渐进式演进，反对一次性重构",
        "stance_side": "pro",
        "focus": "设计渐进式演进路径",
    },
]

LINEUP_PROMPT = """你是圆桌讨论的选角导演。请围绕议题生成 1 位主持人与 {expert_count} 位专家。

要求：
- 主持人立场中立，负责串联与收束；专家立场必须鲜明且互相对立，覆盖支持、反对、中立三类。
- 姓名使用 2-3 个汉字，title 为职业身份，stance 为不超过 40 字的一句话立场。
- 只输出 JSON 数组，不要 Markdown、不要解释。数组元素形如：
  {{"name":"林岸","title":"平台架构师","stance":"支持立即拆分","stance_side":"pro","is_host":false}}
- stance_side 取值只能是 pro / con / neutral；必须恰有一位 is_host 为 true。

议题：{topic}
"""

SPEECH_PROMPT = """你是圆桌讨论的嘉宾，正在参与议题「{topic}」。
你的身份：{title}。你的立场：{stance}（{side}）。
{type_hint}
请用 1-2 句话表达你的核心观点，总长度控制在 20-80 字。
不要寒暄，不要复述他人姓名，不要使用列表或 Markdown，只输出发言正文。

最近对白：
{context}
"""

SUMMARY_PROMPT = """你是圆桌讨论的主持人，议题是「{topic}」。讨论已经结束，请做收束陈词。

请严格输出 JSON 对象：
{{"summary":"不超过 300 字的自然语言总结","consensus":["共识1","共识2"],"divergence":["分歧1","分歧2"],"suggestions":["建议1","建议2"]}}

要求：总结只陈述已发生的观点，不编造事实；共识与分歧各不超过 3 条。

本场洞察：
{insights}

讨论摘录：
{context}
"""


class LLMService:
    """对外暴露阵容生成、流式发言、洞察提炼与总结四项能力。"""

    def __init__(self) -> None:
        self.demo_mode = DEMO_MODE
        self._async_client = None
        if self.demo_mode:
            logger.info("LLM_API_KEY 为空或仍为占位符，已启用 Mock 流式演示模式")
            return

        try:
            from openai import AsyncOpenAI

            # DeepSeek 与 OpenAI Chat Completions 协议兼容，仅需替换 base_url 与模型名
            self._async_client = AsyncOpenAI(
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                timeout=30.0,
                max_retries=1,
            )
            logger.info("已启用真实大模型调用：%s @ %s", LLM_MODEL, LLM_BASE_URL)
        except Exception:  # pragma: no cover - 依赖缺失时退回演示模式
            logger.warning("初始化 LLM 客户端失败，已降级为演示模式", exc_info=True)
            self.demo_mode = True

    # ------------------------------------------------------------------ #
    # 阵容生成
    # ------------------------------------------------------------------ #
    async def generate_lineup(
        self, topic: str, expert_count: int, style: str = "balanced"
    ) -> list[dict[str, Any]]:
        """生成 1 位主持人 + expert_count 位专家，色标由服务端统一分配。"""
        expert_count = max(1, min(int(expert_count), 8))
        candidates: list[dict[str, Any]] = []

        if not self.demo_mode and self._async_client is not None:
            try:
                raw = await self._complete(
                    LINEUP_PROMPT.format(topic=topic, expert_count=expert_count),
                    temperature=0.8,
                )
                candidates = self._parse_lineup(raw)
            except Exception:
                logger.warning("LLM 阵容生成失败，使用模板阵容", exc_info=True)

        if not candidates:
            candidates = self._fallback_lineup(expert_count, style)

        return self._normalize_lineup(candidates, expert_count)

    def _parse_lineup(self, raw: str) -> list[dict[str, Any]]:
        text = raw or ""
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end <= start:
            return []
        try:
            payload = json.loads(text[start : end + 1])
        except (TypeError, ValueError):
            return []
        if not isinstance(payload, list):
            return []

        result: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict) and item.get("name"):
                result.append(item)
        return result

    def _fallback_lineup(self, expert_count: int, style: str) -> list[dict[str, Any]]:
        host = {
            "name": "沈知远",
            "title": "圆桌主持人 · 科技观察者",
            "stance": "中立引导，负责串联观点与收束结论",
            "stance_side": "neutral",
            "is_host": True,
            "focus": "串联观点并收束结论",
        }
        experts = [dict(item) for item in _FALLBACK_EXPERTS[:expert_count]]
        while len(experts) < expert_count:
            template = _FALLBACK_EXPERTS[len(experts) % len(_FALLBACK_EXPERTS)]
            experts.append({**template, "name": f"{template['name']}（观察员）"})
        if style == "debate":
            experts = list(reversed(experts))
        return [host, *experts]

    def _normalize_lineup(
        self, candidates: Sequence[dict[str, Any]], expert_count: int
    ) -> list[dict[str, Any]]:
        """清洗模型输出：字段长度、立场枚举、人数与色标唯一。"""
        hosts = [item for item in candidates if item.get("is_host")]
        experts = [item for item in candidates if not item.get("is_host")]

        host_source = hosts[0] if hosts else candidates[0]
        normalized: list[dict[str, Any]] = [
            {
                "name": self._clip(host_source.get("name") or "沈知远", 40),
                "title": self._clip(host_source.get("title") or "圆桌主持人", 60),
                "stance": self._clip(
                    host_source.get("stance") or "中立引导，负责串联观点与收束结论", 200
                ),
                "stance_side": "neutral",
                "is_host": True,
                "focus": sanitize_focus(
                    host_source.get("focus") or "串联观点并收束结论"
                )
                or "串联观点并收束结论",
                "color_theme": HOST_COLOR_POOL[0],
            }
        ]

        used_colors = {HOST_COLOR_POOL[0]}
        for index in range(expert_count):
            source = experts[index % len(experts)] if experts else _FALLBACK_EXPERTS[index]
            side = source.get("stance_side")
            if side not in {"pro", "con", "neutral"}:
                side = "neutral"
            color = next(
                (candidate for candidate in EXPERT_COLORS if candidate not in used_colors),
                EXPERT_COLORS[index % len(EXPERT_COLORS)],
            )
            used_colors.add(color)
            normalized.append(
                {
                    "name": self._clip(source.get("name") or f"专家{index + 1}", 40),
                    "title": self._clip(source.get("title") or "圆桌嘉宾", 60),
                    "stance": self._clip(source.get("stance") or "持中立观察立场", 200),
                    "stance_side": side,
                    "is_host": False,
                    "focus": sanitize_focus(
                        source.get("focus") or "关注议题的关键分歧"
                    )
                    or "关注议题的关键分歧",
                    "color_theme": color,
                }
            )
        return normalized

    # ------------------------------------------------------------------ #
    # 流式发言
    # ------------------------------------------------------------------ #
    async def stream_speech(
        self,
        topic: str,
        persona: dict[str, Any],
        history: Sequence[dict[str, Any]],
        speech_type: str = "speech",
    ) -> AsyncIterator[str]:
        """流式产出一次短发言的增量文本。"""
        if self.demo_mode or self._async_client is None:
            text = sanitize_transcript(
                self._mock_speech(topic, persona, history, speech_type)
            )
            async for chunk in self._chunk_text(text):
                yield chunk
            return

        prompt = SPEECH_PROMPT.format(
            topic=topic,
            title=persona.get("title", "圆桌嘉宾"),
            stance=persona.get("stance", ""),
            side=persona.get("stance_side", "neutral"),
            type_hint=self._type_hint(speech_type),
            context=self._format_context(history),
        )
        sanitizer = StreamingSanitizer()
        started = False
        try:
            stream = await self._async_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=120,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if not delta:
                    continue
                cleaned = sanitizer.feed(delta)
                if cleaned:
                    started = True
                    yield cleaned
        except Exception:
            logger.warning("LLM 流式发言失败，切换为演示文本", exc_info=True)

        if not started:
            text = sanitize_transcript(
                self._mock_speech(topic, persona, history, speech_type)
            )
            async for chunk in self._chunk_text(text):
                yield chunk

    def _type_hint(self, speech_type: str) -> str:
        if speech_type == "counter":
            return "此刻你需要直接回应并反驳上一位发言者的观点。"
        if speech_type == "intro":
            return "此刻你需要做开场陈述。"
        return "此刻你需要提出自己的核心判断。"

    async def _chunk_text(self, text: str) -> AsyncIterator[str]:
        """把整段文本切成 1-2 字的增量，模拟真实模型的流式节奏。"""
        index = 0
        while index < len(text):
            size = 2 if index % 5 else 1
            yield text[index : index + size]
            index += size
            await asyncio.sleep(MOCK_TOKEN_DELAY)

    def _mock_speech(
        self,
        topic: str,
        persona: dict[str, Any],
        history: Sequence[dict[str, Any]],
        speech_type: str,
    ) -> str:
        side = persona.get("stance_side", "neutral")
        persona_id = persona.get("id")
        own_turns = sum(1 for item in history if item.get("persona_id") == persona_id)
        rotation = own_turns % 3

        templates = {
            "pro": [
                "我支持尽快推进：只要边界与评价标准先说清楚，拆分的收益就会大于风险。",
                "从交付效率看，继续等待的代价更高，我主张先选一条业务线小范围试点。",
                "方向我认同，但节奏要稳：先把团队边界理顺，再逐步扩大拆分范围。",
            ],
            "con": [
                "我持保留意见：分布式复杂度一旦放大，运维和排障成本会成倍增加。",
                "现在动手更像在转移问题，耦合只会从代码层搬到服务层，并没有消失。",
                "在组织边界尚不清晰之前，拆分只会把交付链路拉得更长。",
            ],
            "neutral": [
                "关键不在拆或不拆，而在能否量化拆分前后的交付效率与故障恢复时间。",
                "我建议把讨论落到指标上：先定义成功标准，再决定拆分的范围与节奏。",
                "两边都有道理，真正的约束是团队当前能否承担额外的协作成本。",
            ],
        }
        text = templates.get(side, templates["neutral"])[rotation]
        if speech_type == "counter":
            text = f"回应上一位的观点：{text}"
        return self._fit_length(text)

    # ------------------------------------------------------------------ #
    # 洞察提炼
    # ------------------------------------------------------------------ #
    async def extract_insights(
        self, topic: str, turns: Sequence[DialogueTurn]
    ) -> InsightBoard:
        if not turns:
            return InsightBoard()

        if self.demo_mode or self._async_client is None:
            return self._clean_board(self._mock_insights(topic, turns))

        try:
            raw = await self._complete(
                self._insight_prompt(turns), temperature=0.2, max_tokens=500
            )
            # 复用 TDD 阶段已测通的解析与清洗逻辑
            extractor = InsightExtractor(lambda _prompt: raw)
            return self._clean_board(extractor.extract(turns))
        except Exception:
            logger.warning("洞察提炼失败，使用演示结果", exc_info=True)
            return self._clean_board(self._mock_insights(topic, turns))

    @staticmethod
    def _clean_board(board: InsightBoard) -> InsightBoard:
        """对白脱敏后再出站，杜绝舞台提示与模型标记进入看板。"""
        consensus: list[str] = []
        divergence: list[str] = []
        for item in board.consensus:
            cleaned = sanitize_insight(item)
            if cleaned and cleaned not in consensus:
                consensus.append(cleaned)
        for item in board.divergence:
            cleaned = sanitize_insight(item)
            if cleaned and cleaned not in divergence:
                divergence.append(cleaned)
        return InsightBoard(consensus=consensus, divergence=divergence)

    def _insight_prompt(self, turns: Sequence[DialogueTurn]) -> str:
        transcript = "\n".join(f"{turn.speaker}：{turn.content}" for turn in turns)
        return (
            "你是圆桌讨论的洞察提炼器。请阅读对白，提炼共识与分歧。\n"
            "要求：每条只表达一个观点，不超过 300 字；不复述姓名；只输出 JSON，"
            '形如 {"consensus":["..."],"divergence":["..."]}。\n\n'
            f"对白：\n{transcript}\n"
        )

    def _mock_insights(
        self, topic: str, turns: Sequence[DialogueTurn]
    ) -> InsightBoard:
        short_topic = self._clip(topic, 30)
        stage = max(1, min(len(turns) // 2, 3))
        consensus_pool = [
            "多方认同拆分必须以清晰的团队边界为前提。",
            "讨论倾向于先用小范围试点验证，再决定是否扩大范围。",
            "以交付效率与故障恢复时间作为量化评判标准的思路获得支持。",
        ]
        divergence_pool = [
            f"围绕「{short_topic}」，当前规模下是否应立即动手仍存在分歧。",
            "先调整组织结构还是先拆分服务，两种路径尚未收敛。",
            "试点阶段的预算与人力由谁承担，缺少明确结论。",
        ]
        return InsightBoard(
            consensus=consensus_pool[: min(stage, 2)],
            divergence=divergence_pool[: min(stage, 2)],
        )

    # ------------------------------------------------------------------ #
    # 主持人总结
    # ------------------------------------------------------------------ #
    async def generate_summary(
        self,
        topic: str,
        history: Sequence[dict[str, Any]],
        board: InsightBoard,
    ) -> dict[str, Any]:
        if not self.demo_mode and self._async_client is not None:
            try:
                insights_text = json.dumps(
                    {"consensus": board.consensus, "divergence": board.divergence},
                    ensure_ascii=False,
                )
                raw = await self._complete(
                    SUMMARY_PROMPT.format(
                        topic=topic,
                        insights=insights_text,
                        context=self._format_context(history),
                    ),
                    temperature=0.5,
                    max_tokens=700,
                )
                payload = self._parse_object(raw)
                raw_summary = str(payload.get("summary") or "")
                if raw_summary.strip():
                    return {
                        "summary": sanitize_summary(raw_summary),
                        "consensus": [
                            sanitize_insight(item)
                            for item in self._as_text_list(payload.get("consensus"))
                        ],
                        "divergence": [
                            sanitize_insight(item)
                            for item in self._as_text_list(payload.get("divergence"))
                        ],
                        "suggestions": [
                            sanitize_insight(item)
                            for item in self._as_text_list(payload.get("suggestions"))
                        ],
                    }
            except Exception:
                logger.warning("LLM 总结生成失败，使用演示总结", exc_info=True)

        return self._mock_summary(topic, history, board)

    def _mock_summary(
        self,
        topic: str,
        history: Sequence[dict[str, Any]],
        board: InsightBoard,
    ) -> dict[str, Any]:
        consensus = board.consensus or ["讨论仍需更多轮次才能形成稳定共识。"]
        divergence = board.divergence or ["各方尚未暴露核心冲突点。"]
        summary = (
            f"本场围绕「{self._clip(topic, 40)}」展开，各方从边界、成本与交付节奏三个维度交锋。"
            f"正在收敛的共识是：{consensus[0]}"
            f"主要分歧集中在：{divergence[0]}"
            "建议先用一条业务线做小范围试点，用数据验证后再决定下一步。"
        )
        return {
            "summary": sanitize_summary(self._clip(summary, 600)),
            "consensus": [sanitize_insight(item) for item in consensus[:3]],
            "divergence": [sanitize_insight(item) for item in divergence[:3]],
            "suggestions": [
                "先用绞杀者模式试点一条业务线",
                "为拆分设定可量化的成功标准",
                "同步调整团队边界与协作机制",
            ],
        }

    # ------------------------------------------------------------------ #
    # LLM 基础调用
    # ------------------------------------------------------------------ #
    async def _complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 600,
    ) -> str:
        if self._async_client is None:
            raise RuntimeError("LLM 客户端未初始化")
        response = await self._async_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0] if response.choices else None
        return (choice.message.content if choice else "") or ""

    @staticmethod
    def _parse_object(raw: str) -> dict[str, Any]:
        text = raw or ""
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
        except (TypeError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _as_text_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        return cleaned[:limit]

    @staticmethod
    def _fit_length(text: str) -> str:
        """把演示文本收敛到 20-80 字。"""
        cleaned = text.strip()
        if len(cleaned) > 80:
            cleaned = cleaned[:79].rstrip("，,、；;：: ") + "。"
        if len(cleaned) < 20:
            cleaned = f"{cleaned}，这是我基于当前信息能给出的判断。"
        return cleaned

    @staticmethod
    def _format_context(history: Sequence[dict[str, Any]], limit: int = 6) -> str:
        recent = list(history)[-limit:]
        if not recent:
            return "（尚无发言）"
        return "\n".join(
            f"{item.get('speaker', '嘉宾')}：{item.get('content', '')}" for item in recent
        )


llm_service = LLMService()
