"""实时共识与分歧提炼引擎。

职责：把对话流交给大模型，按 Prompt 模板要求返回结构化结果，再对结果做
「解析 → 清洗 → 校验 → 领域映射」，最终输出干净、可直接出站的 Pydantic 模型。

安全红线（对应 PRD HR-4）：
- 大模型原始输出（代码围栏、Markdown 标记、寒暄语）绝不进入返回值。
- 解析失败时抛出 InsightExtractionError，异常信息不回显原始文本。
"""

from __future__ import annotations

import json
import re
from typing import Callable, Sequence

from pydantic import BaseModel, Field

#: insights.content 的硬上限（与 backend/schema.sql 对齐）
MAX_CONTENT_LENGTH = 300

#: 大模型输出中可能出现的条目前缀（中英文标签）
_LABEL_PREFIX = re.compile(
    r"^(?:共识点?|分歧点?|consensus|divergence)\s*[:：]\s*",
    re.IGNORECASE,
)

#: 列表符号（- / • / 1. / 1、）
_BULLET_PREFIX = re.compile(r"^(?:[-•·]|\d+[.、)])\s*")

#: Markdown 强调与代码标记
_MARKUP_PATTERN = re.compile(r"[`*_]{1,3}")

#: 必须清除的模型原始结构字符
_RAW_STRUCTURE_CHARS = ("{", "}", "<|", "|>")


PROMPT_TEMPLATE = """你是圆桌讨论的洞察提炼器。请阅读下面的对白，提炼出两类结论：

1. consensus（共识）：多位专家明确认同或未被反驳的共同判断。
2. divergence（分歧）：存在立场对立、尚未收敛的争议点。

要求：
- 每条结论只表达一个观点，尽量精炼，不超过 300 字。
- 只描述观点本身，不要复述发言人姓名，不要输出任何解释过程。
- 严格输出 JSON，形如 {{"consensus": ["..."], "divergence": ["..."]}}。

对白：
{dialogue}
"""


class DialogueTurn(BaseModel):
    """一条对白。"""

    speaker: str
    content: str


class InsightBoard(BaseModel):
    """结构化看板：共识与分歧两组纯文本条目。"""

    consensus: list[str] = Field(default_factory=list)
    divergence: list[str] = Field(default_factory=list)


class InsightExtractionError(RuntimeError):
    """模型输出无法解析为结构化洞察。"""


class InsightExtractor:
    """共识与分歧提炼器。"""

    def __init__(self, llm: Callable[[str], str]) -> None:
        self._llm = llm

    def extract(self, dialogue: Sequence[DialogueTurn]) -> InsightBoard:
        """把对话流提炼为结构化看板。"""
        turns = list(dialogue)
        if not turns:
            return InsightBoard()

        raw_output = self._llm(self._build_prompt(turns))
        payload = self._parse_payload(raw_output)

        return InsightBoard(
            consensus=self._clean_items(payload.get("consensus")),
            divergence=self._clean_items(payload.get("divergence")),
        )

    # ------------------------------------------------------------------ #
    # 内部实现
    # ------------------------------------------------------------------ #
    def _build_prompt(self, turns: Sequence[DialogueTurn]) -> str:
        transcript = "\n".join(f"{turn.speaker}：{turn.content}" for turn in turns)
        return PROMPT_TEMPLATE.format(dialogue=transcript)

    def _parse_payload(self, raw_output: str) -> dict:
        """从可能夹杂寒暄与代码围栏的文本中截取 JSON 对象。"""
        text = raw_output or ""
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise InsightExtractionError("模型输出无法解析为结构的共识与分歧")

        try:
            payload = json.loads(text[start : end + 1])
        except (TypeError, ValueError) as exc:
            raise InsightExtractionError("模型输出无法解析为结构的共识与分歧") from exc

        if not isinstance(payload, dict):
            raise InsightExtractionError("模型输出结构不符合洞察契约")

        for key in ("consensus", "divergence"):
            if key in payload and not isinstance(payload[key], list):
                raise InsightExtractionError("模型输出结构不符合洞察契约")

        return payload

    def _clean_items(self, items: object) -> list[str]:
        """清洗条目：去标记、去标签、截断、去重。"""
        if not isinstance(items, list):
            return []

        cleaned: list[str] = []
        for item in items:
            text = self._clean_item(item)
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def _clean_item(self, item: object) -> str:
        if not isinstance(item, str):
            return ""

        text = item.strip()
        text = _BULLET_PREFIX.sub("", text)
        text = _MARKUP_PATTERN.sub("", text)
        for token in _RAW_STRUCTURE_CHARS:
            text = text.replace(token, "")
        text = re.sub(r"\s+", " ", text).strip()

        # 标签可能叠加出现，最多剥离两层
        for _ in range(2):
            stripped = _LABEL_PREFIX.sub("", text).strip()
            if stripped == text:
                break
            text = stripped

        text = text.strip(" ：:，,；;")
        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH].rstrip()
        return text
