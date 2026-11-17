"""TDD 红灯用例：实时共识与分歧提炼器。

本阶段只定义契约，不提供任何业务实现，因此测试预期全部失败。

被测对象（待实现的 backend/app/insight.py）：

- ``DialogueTurn``：一条对白，含发言人 ``speaker`` 与内容 ``content``。
- ``InsightBoard``：结构化看板，含 ``consensus`` 与 ``divergence`` 两个字符串列表。
- ``InsightExtractor``：提炼器，构造时注入大模型调用 ``llm(prompt) -> str``。
- ``InsightExtractionError``：模型输出无法解析时抛出，且异常信息不得回显原始输出。

覆盖的 PRD 硬规则：
- HR-4 严禁前端暴露大模型原始 JSON：所有条目必须是清洗后的纯文本。
- insights 表约束：type 仅 consensus / divergence，content 不超过 300 字。
"""

from __future__ import annotations

import pytest

# 用于验证长度截断的超长条目（远超 insights.content 的 300 字上限）
LONG_ITEM = (
    "这是一段用于验证长度截断的冗长共识描述，它刻意写得很啰嗦，"
    "用来模拟大模型在没有约束时输出的大段说明性文字，"
) * 8

# 模拟大模型的「脏」输出：代码围栏、前后寒暄、Markdown 加粗标签、重复条目、超长文本
MESSY_MODEL_OUTPUT = (
    "好的，以下是我整理的结构化结果：\n"
    "```json\n"
    "{\n"
    '  "consensus": [\n'
    '    "拆分必须以团队边界清晰为前提",\n'
    '    "拆分必须以团队边界清晰为前提",\n'
    '    "**共识**：大家一致认为拆分不能脱离组织现状",\n'
    f'    "{LONG_ITEM}"\n'
    "  ],\n"
    '  "divergence": [\n'
    '    "当前规模下是否应立即动手",\n'
    '    "分歧点：预算与人力由谁承担"\n'
    "  ]\n"
    "}\n"
    "```\n"
    "如需进一步细化，我可以继续补充。"
)


def load_insight_module():
    """延迟导入被测模块，使未实现时呈现逐条 FAILED 而非收集期 ERROR。"""
    import app.services.insight_extractor as insight_module

    return insight_module


def _dialogue(module):
    """一段包含共识信号与分歧信号的模拟对白。"""
    return [
        module.DialogueTurn(
            speaker="林岸",
            content="拆分的门槛不是技术，而是团队边界是否清晰。",
        ),
        module.DialogueTurn(
            speaker="周砚",
            content="现在拆只会把耦合从代码搬到服务之间。",
        ),
        module.DialogueTurn(
            speaker="许听",
            content="我同意边界优先，但时机和预算还需要再讨论。",
        ),
    ]


def test_extractor_returns_structured_consensus_and_divergence():
    """提炼器必须输出 consensus / divergence 两组结构化字符串列表。"""
    module = load_insight_module()
    captured = {}

    def fake_llm(prompt):
        captured["prompt"] = prompt
        return MESSY_MODEL_OUTPUT

    extractor = module.InsightExtractor(llm=fake_llm)
    board = extractor.extract(_dialogue(module))

    # 结构契约：两组列表均已提取且非空
    assert isinstance(board.consensus, list) and board.consensus
    assert isinstance(board.divergence, list) and board.divergence

    # 内容准确性：关键结论落在正确的分组里
    assert any("团队边界" in item for item in board.consensus)
    assert any("立即动手" in item for item in board.divergence)

    # 去重
    assert len(board.consensus) == len(set(board.consensus))
    assert len(board.divergence) == len(set(board.divergence))

    # 分类不串档
    assert not set(board.consensus) & set(board.divergence)

    # 对白确实被送入模型，而非返回硬编码结果
    assert "林岸" in captured["prompt"]
    assert "周砚" in captured["prompt"]


def test_extracted_items_are_clean_plain_text():
    """条目必须是清洗后的纯文本，不得残留任何模型原始标记。"""
    module = load_insight_module()
    extractor = module.InsightExtractor(llm=lambda prompt: MESSY_MODEL_OUTPUT)
    board = extractor.extract(_dialogue(module))

    forbidden_tokens = (
        "```",
        "{",
        "}",
        "**",
        "consensus",
        "divergence",
        "assistant",
        "<|",
    )

    for item in board.consensus + board.divergence:
        assert isinstance(item, str)
        assert item == item.strip(), f"条目未去除首尾空白：{item!r}"
        assert item, "不得输出空条目"
        assert len(item) <= 300, f"条目超过 300 字上限：{len(item)}"
        for token in forbidden_tokens:
            assert token not in item, f"条目残留模型原始标记 {token!r}：{item!r}"


def test_unparsable_model_output_raises_safe_error():
    """模型返回无法解析的文本时，必须抛出安全异常且不回显原文。"""
    module = load_insight_module()
    raw_output = "抱歉，我无法完成这个请求，请稍后再试。"
    extractor = module.InsightExtractor(llm=lambda prompt: raw_output)

    with pytest.raises(module.InsightExtractionError) as excinfo:
        extractor.extract(_dialogue(module))

    message = str(excinfo.value)
    assert "抱歉" not in message, "异常信息不得回显大模型原始输出"
    assert "{" not in message and "}" not in message
