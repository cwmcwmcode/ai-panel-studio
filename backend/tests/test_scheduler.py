"""TDD 红灯用例：专家非机械轮流发言调度器。

本阶段只定义契约，不提供任何业务实现，因此测试预期全部失败。

被测对象（待实现的 backend/app/scheduler.py）：

- ``Persona``：参演角色，含立场与立场阵营（pro / con / neutral）。
- ``SpeechRecord``：一条已发生的发言记录。
- ``ScheduleDecision``：调度决策，含下一位发言人、发言类型与候选评分。
- ``SpeechScheduler``：调度器，对外提供
  - ``decide_next(history) -> ScheduleDecision``
  - ``validate_speech(text) -> str``
- ``SpeechValidationError``：发言文本违反 1-2 句 / 20-80 字硬约束时抛出。

覆盖的 PRD 硬规则：
- HR-1 单次发言 1-2 句、20-80 字（测试项 D）
- HR-2 非机械轮流：冷却 + 冲突度择优 + 均衡（测试项 A / B）
- 主持人控场介入（测试项 C）
"""

from __future__ import annotations

from collections import Counter

import pytest


def load_scheduler_module():
    """延迟导入被测模块。

    实现尚未落地时，每个用例以 FAILED 红灯呈现，而不是在收集阶段整体 ERROR，
    便于 TDD 红-绿-重构循环逐条点亮。
    """
    import app.services.scheduler as scheduler_module

    return scheduler_module


# --------------------------------------------------------------------------- #
# 测试夹具（显式构造，避免跨用例共享可变状态）
# --------------------------------------------------------------------------- #
def _experts(module):
    """4 位专家：2 位支持、1 位反对、1 位中立，构成可辩论光谱。"""
    return [
        module.Persona(
            id=1,
            name="林岸",
            stance="支持立即拆分，组织规模已到临界点",
            stance_side="pro",
            color_theme="#E4572E",
        ),
        module.Persona(
            id=2,
            name="周砚",
            stance="反对过早拆分，分布式复杂度代价过高",
            stance_side="con",
            color_theme="#2E86AB",
        ),
        module.Persona(
            id=3,
            name="许听",
            stance="先改组织结构，再谈架构拆分",
            stance_side="pro",
            color_theme="#7A9E3F",
        ),
        module.Persona(
            id=4,
            name="顾临",
            stance="关注运维成本与故障面的扩大",
            stance_side="neutral",
            color_theme="#B565A7",
        ),
    ]


def _host(module):
    return module.Persona(
        id=101,
        name="沈知远",
        stance="中立引导，负责串联观点与收束结论",
        stance_side="neutral",
        is_host=True,
        color_theme="#6C7A89",
    )


def _simulate(module, scheduler, turns):
    """驱动调度器产生 turns 次决策，并把每次决策回写为历史记录。"""
    history = []
    decisions = []
    for index in range(turns):
        decision = scheduler.decide_next(history)
        decisions.append(decision)
        history.append(
            module.SpeechRecord(
                persona_id=decision.persona_id,
                sequence_no=index + 1,
                speech_type=decision.speech_type,
                content="用于测试的占位发言内容，仅提供调度上下文。",
            )
        )
    return decisions


def _count_sentences(text):
    """按中文/英文句末标点统计句数。"""
    endings = "。！？!?"
    count = 0
    in_sentence = False
    for char in text.strip():
        if char in endings:
            count += 1
            in_sentence = False
        elif not char.isspace():
            in_sentence = True
    if in_sentence:
        count += 1
    return count


# --------------------------------------------------------------------------- #
# 测试项 A：防自言自语 / Cooldown 约束
# --------------------------------------------------------------------------- #
def test_cooldown_forbids_same_expert_speaking_twice_in_a_row():
    """同一专家绝对不能连续发言两次（冷却周期 >= 1）。"""
    module = load_scheduler_module()
    scheduler = module.SpeechScheduler(
        personas=_experts(module),
        cooldown=1,
        host_intervention_after=None,
        seed=11,
    )

    decisions = _simulate(module, scheduler, turns=20)
    speaker_ids = [decision.persona_id for decision in decisions]

    assert len(speaker_ids) == 20

    # 相邻两次发言不能是同一人
    for previous, current in zip(speaker_ids, speaker_ids[1:]):
        assert previous != current, f"专家 {current} 出现了连续发言：{speaker_ids}"

    # 冷却周期 >= 1：同一专家两次发言之间至少间隔 1 次他人发言
    last_seen = {}
    for index, persona_id in enumerate(speaker_ids):
        if persona_id in last_seen:
            gap = index - last_seen[persona_id]
            assert gap >= 2, f"专家 {persona_id} 的发言间隔为 {gap}，违反冷却约束"
        last_seen[persona_id] = index


# --------------------------------------------------------------------------- #
# 测试项 B：拒绝机械轮流发言
# --------------------------------------------------------------------------- #
def test_scheduler_rejects_mechanical_rotation():
    """20 次调度不得呈现周期性循环，且必须由立场冲突动态加权。"""
    module = load_scheduler_module()
    personas = _experts(module)
    scheduler = module.SpeechScheduler(
        personas=personas,
        cooldown=1,
        host_intervention_after=None,
        seed=7,
    )

    decisions = _simulate(module, scheduler, turns=20)
    speaker_ids = [decision.persona_id for decision in decisions]

    # 1) 绝对不得是周期性循环序列（含 1->2->3->4->1->2->3->4 这类机械轮转）
    def is_periodic(sequence, period):
        return all(
            sequence[index] == sequence[index - period]
            for index in range(period, len(sequence))
        )

    for period in range(1, len(speaker_ids) // 2 + 1):
        assert not is_periodic(speaker_ids, period), (
            f"发言序列呈现周期 {period} 的机械轮转：{speaker_ids}"
        )

    # 2) 均衡：至少 3 位专家参与，且单人占比不超过 40%
    counts = Counter(speaker_ids)
    assert len(counts) >= 3, f"参与专家过少，疑似固定小圈轮流：{counts}"
    assert max(counts.values()) / len(speaker_ids) <= 0.4, (
        f"存在发言垄断，分布不符合均衡约束：{counts}"
    )

    # 3) 动态加权：调度决策必须公开候选评分，且选中者即为最高分
    for decision in decisions:
        assert decision.candidate_scores, "调度决策必须给出候选评分，以证明其非随机轮转"
        best_score = max(decision.candidate_scores.values())
        assert decision.candidate_scores[decision.persona_id] == best_score, (
            "被选中的专家并非候选评分最高者，无法体现冲突度动态加权"
        )

    # 4) 立场对立驱动：相邻发言中「支持 vs 反对」的交锋占比达到下限
    sides = {persona.id: persona.stance_side for persona in personas}
    opposing_pairs = sum(
        1
        for previous, current in zip(speaker_ids, speaker_ids[1:])
        if {sides[previous], sides[current]} == {"pro", "con"}
    )
    assert opposing_pairs >= (len(speaker_ids) - 1) * 0.3, (
        f"立场对立交锋仅 {opposing_pairs} 次，未体现基于立场冲突的动态加权"
    )


# --------------------------------------------------------------------------- #
# 测试项 C：主持人强制控场介入
# --------------------------------------------------------------------------- #
def test_host_intervenes_after_consecutive_expert_exchanges():
    """专家连续交锋达到阈值后，下一位发言人必须被强制切换为主持人。"""
    module = load_scheduler_module()
    host = _host(module)
    scheduler = module.SpeechScheduler(
        personas=_experts(module) + [host],
        cooldown=1,
        host_intervention_after=3,
        seed=5,
    )

    # 专家已连续发言 3 轮，第 4 次调度必须交给主持人控场
    history = [
        module.SpeechRecord(
            persona_id=persona_id,
            sequence_no=sequence_no,
            speech_type="speech",
            content="用于测试的占位发言内容，仅提供调度上下文。",
        )
        for sequence_no, persona_id in enumerate((1, 2, 3), start=1)
    ]
    decision = scheduler.decide_next(history)
    assert decision.persona_id == host.id, (
        f"专家连续交锋 3 轮后应强制主持人介入，实际选中 {decision.persona_id}"
    )

    # 连续模拟时，任意时刻的专家连续发言数都不得超过阈值
    decisions = _simulate(module, scheduler, turns=15)
    consecutive_experts = 0
    host_turns = 0
    for item in decisions:
        if item.persona_id == host.id:
            host_turns += 1
            consecutive_experts = 0
        else:
            consecutive_experts += 1
            assert consecutive_experts <= 3, (
                f"专家连续交锋 {consecutive_experts} 轮仍未触发主持人介入"
            )
    assert host_turns >= 3, "主持人控场次数不足，未形成阶段推进"


# --------------------------------------------------------------------------- #
# 测试项 D：发言长度硬约束（1-2 句，20-80 字）
# --------------------------------------------------------------------------- #
def test_validated_speech_stays_within_one_or_two_sentences():
    """通过校验的发言必须落在 1-2 句、20-80 字区间内。"""
    module = load_scheduler_module()
    scheduler = module.SpeechScheduler(personas=_experts(module), seed=3)

    # 合规发言：原样通过
    valid_text = "拆分的门槛不是技术，而是团队边界是否清晰，这一点必须优先确认。"
    validated = scheduler.validate_speech(valid_text)
    assert validated == valid_text.strip()
    assert 20 <= len(validated) <= 80
    assert 1 <= _count_sentences(validated) <= 2

    # 超长发言：4 句、约 120 字，必须被压缩到 2 句 / 80 字以内
    overlong_text = (
        "拆分当然有好处，但分布式系统的复杂度会成倍上升！"
        "如果团队边界本身不清晰，拆完只会把耦合从代码里搬到服务之间。"
        "更何况现在的运维能力还跟不上，贸然拆分会带来大量线上故障。"
        "所以我建议先把组织理顺，再谈架构演进。"
    )
    truncated = scheduler.validate_speech(overlong_text)
    assert 20 <= len(truncated) <= 80, f"截断后仍超限：{len(truncated)} 字"
    assert _count_sentences(truncated) <= 2, "截断后仍超过 2 句"

    # 过短发言：不足 20 字，必须报错而不是静默放行
    with pytest.raises(module.SpeechValidationError):
        scheduler.validate_speech("我同意。")
