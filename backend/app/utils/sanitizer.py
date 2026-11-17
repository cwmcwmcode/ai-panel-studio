"""输出脱敏与去 JSON 化过滤器。

三条硬规则：
1. 总结词只允许纯自然语言，代码围栏、JSON 键值、Markdown 标记必须被强行剥离。
2. 对白流只保留发言正文，舞台提示、系统通知、控制字符一律过滤。
3. 专家公开摘要不得超过 15 字，绝不携带大模型原始思维链（CoT）。
"""

from __future__ import annotations

import json
import re

#: 公开摘要硬上限（字）
MAX_FOCUS_LENGTH = 15
#: 总结词软上限，避免异常长文撑爆演播厅终结卡片
MAX_SUMMARY_LENGTH = 600
#: 完全无法提取时的兜底陈词
FALLBACK_SUMMARY = "本场讨论已收束，感谢各位嘉宾的坦诚交锋，观点仍在继续生长。"

_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CODE_FENCE = re.compile(r"```[A-Za-z0-9_-]*")
_MARKDOWN_MARKS = re.compile(r"\*{1,3}|`{1,3}|^#{1,6}\s*", re.MULTILINE)

#: 整行系统旁白（含中英文标签）
_SYSTEM_LINE = re.compile(
    r"(?im)^\s*(?:系统通知|系统提示|系统消息|旁白|画外音|内心独白|思维链|思考过程|CoT)"
    r"\s*[:：].*$"
)
#: 行内嵌的系统通知片段
_INLINE_SYSTEM = re.compile(
    r"(?:^|[。！？；;])\s*(?:系统通知|系统提示|系统消息)\s*[:：][^。！？；;\n]*"
)
#: 括号包裹的舞台提示，如 [举手]、【反驳】、（沉默）
_STAGE_DIRECTION = re.compile(
    r"[\[【（(]\s*(?:举手|反驳|点头|摇头|沉默|思考|沉思|掌声|笑声|皱眉|叹气|"
    r"打断|旁白|画外音|系统通知|系统提示|系统)\s*[^\]】）)]*[\]】）)]",
    re.IGNORECASE,
)
#: 带引号或不带引号的 JSON 键标签
_QUOTED_LABEL = re.compile(
    r'["“]?(?:summary|consensus|divergence|suggestions|content|text|总结)["”]?\s*[:：]\s*',
    re.IGNORECASE,
)
_BARE_LABEL = re.compile(
    r"\b(?:summary|consensus|divergence|suggestions)\b\s*[:：]\s*", re.IGNORECASE
)
_LEADING_DECORATION = re.compile(
    r"^(?:好的[，,]?\s*)?(?:以下(?:是|为)[^。！？\n]{0,24}[:：]?|总结|陈词|summary)"
    r"\s*[:：,，]?\s*",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")
_SENTENCE_BREAK = re.compile(r"[。！？!?；;\n]")


def _extract_summary_payload(text: str) -> str | None:
    """从夹带寒暄或代码围栏的文本中提取 summary 字段。"""
    match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if match:
        try:
            value = json.loads(f'"{match.group(1)}"')
        except (TypeError, ValueError):
            value = match.group(1)
        if isinstance(value, str) and value.strip():
            return value.strip()

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            payload = json.loads(text[start : end + 1])
        except (TypeError, ValueError):
            payload = None
        if isinstance(payload, dict):
            for key in ("summary", "content", "text"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def sanitize_summary(raw: str) -> str:
    """把任意模型总结输出清洗为一段纯自然语言陈词。"""
    text = _INVISIBLE.sub("", str(raw or "")).strip()
    if not text:
        return FALLBACK_SUMMARY

    text = _CODE_FENCE.sub(" ", text)
    extracted = _extract_summary_payload(text)
    if extracted:
        text = extracted

    text = _SYSTEM_LINE.sub(" ", text)
    text = _INLINE_SYSTEM.sub("。", text)
    text = _STAGE_DIRECTION.sub(" ", text)
    text = _QUOTED_LABEL.sub("", text)
    text = _BARE_LABEL.sub("", text)

    # JSON 结构残渣：花括号、方括号与英文引号全部移除
    if any(mark in text for mark in "{}[]\""):
        text = re.sub(r'[{}\[\]"]', " ", text)

    text = _MARKDOWN_MARKS.sub("", text)
    text = _WHITESPACE.sub(" ", text).strip()
    text = _LEADING_DECORATION.sub("", text).strip(" ：:，,；;")

    if not text:
        return FALLBACK_SUMMARY
    if len(text) > MAX_SUMMARY_LENGTH:
        text = text[: MAX_SUMMARY_LENGTH - 1].rstrip("，,、；;：: ") + "。"
    if not text.endswith(("。", "！", "？", "…")):
        text += "。"
    return text


def sanitize_transcript(raw: str) -> str:
    """净化单条发言：去除舞台提示、系统通知、控制字符与 Markdown 标记。"""
    text = _INVISIBLE.sub("", str(raw or ""))
    text = _CODE_FENCE.sub(" ", text)
    text = _SYSTEM_LINE.sub(" ", text)
    text = _INLINE_SYSTEM.sub("。", text)
    text = _STAGE_DIRECTION.sub(" ", text)
    text = _MARKDOWN_MARKS.sub("", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text.strip(" ：:，,；;")


def sanitize_focus(raw: str, limit: int = MAX_FOCUS_LENGTH) -> str:
    """生成 15 字以内的公开观点摘要，绝不透出思维链原文。"""
    text = sanitize_transcript(raw)
    text = re.sub(
        r"^(?:关注焦点|公开摘要|焦点|思考|思考过程|内心独白)\s*[:：]\s*", "", text
    )
    text = _SENTENCE_BREAK.split(text, maxsplit=1)[0].strip()
    if len(text) > limit:
        text = text[:limit].rstrip("，,、；;：: ")
    return text


def sanitize_insight(raw: str, limit: int = 300) -> str:
    """净化共识/分歧条目，复用对白清洗并限制最大长度。"""
    text = sanitize_transcript(raw)
    if len(text) > limit:
        text = text[:limit].rstrip("，,、；;：: ")
    return text


class StreamingSanitizer:
    """流式增量清洗器：抑制 [举手]、【反驳】、系统通知等旁白片段。

    对白中合法的方括号极少，遇到未闭合的左括号时会持续抑制，直到右括号出现，
    从而保证 token 流中不会闪现舞台提示。
    """

    def __init__(self) -> None:
        self._suppress = False

    def feed(self, delta: str) -> str:
        output: list[str] = []
        for char in str(delta or ""):
            if char in "[【":
                self._suppress = True
                continue
            if char in "]】":
                self._suppress = False
                continue
            if self._suppress:
                continue
            if char in "`*" or _INVISIBLE.match(char):
                continue
            output.append(char)
        return "".join(output)
