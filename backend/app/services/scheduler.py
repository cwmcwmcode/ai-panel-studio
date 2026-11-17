"""基于立场的加权优先级发言调度器（Weighted Priority State Machine）。

设计要点：
- 每位专家维护「发言欲望值」：闲置越久欲望越高，已发言占比越高欲望越低。
- 立场对立加权：上一位发言人立场为 A 时，持有相反立场的专家获得高额反驳加权。
- 强制冷却：刚发言完毕的专家进入冷却期，冷却期内不参与候选。
- 主持人控场：专家连续发言达到阈值后，主持人权重置为无穷大，强制接管发言权。
- 防机械轮转：若某候选会让发言序列形成短周期循环，则施加周期性惩罚。
- 文本收敛：把超长发言压缩到 1-2 句、20-80 字的硬约束区间内。

所有状态均由 history 推导，调度器本身无隐藏可变状态（仅随机数发生器），
保证同一 history 在给定 seed 下可复现。
"""

from __future__ import annotations

import random
import re
from typing import Literal, Sequence

from pydantic import BaseModel, Field

StanceSide = Literal["pro", "con", "neutral"]
SpeechType = Literal["intro", "speech", "counter", "summary"]

_OPPOSITE_SIDE = {"pro": "con", "con": "pro"}
_SENTENCE_PATTERN = re.compile(r"[^。！？!?；;…]+[。！？!?；;…]*")


class Persona(BaseModel):
    """参演角色：主持人或专家。"""

    id: int
    name: str
    stance: str
    stance_side: StanceSide = "neutral"
    is_host: bool = False
    color_theme: str = "#999999"


class SpeechRecord(BaseModel):
    """一条已经发生的发言记录，作为调度上下文。"""

    persona_id: int
    sequence_no: int = Field(ge=1)
    speech_type: SpeechType
    content: str


class ScheduleDecision(BaseModel):
    """一次调度决策：下一位发言人、发言类型与全部候选的评分明细。"""

    persona_id: int
    speech_type: SpeechType
    candidate_scores: dict[int, float]


class SpeechValidationError(ValueError):
    """发言文本违反 1-2 句 / 20-80 字硬约束。"""


class SpeechScheduler:
    """专家非机械轮流发言调度器。"""

    #: 立场对立时的反驳欲望加权
    CONFLICT_BONUS = 3.0
    #: 上一发言人为中立时，所有专家的基础加权
    NEUTRAL_BONUS = 1.0
    #: 发言占比越高，欲望衰减越强（均衡约束）
    BALANCE_PENALTY = 5.0
    #: 会形成短周期轮转时的惩罚
    ROTATION_PENALTY = -8.0
    #: 主持人强制接管时的权重（视为无穷大）
    HOST_TAKEOVER_SCORE = 1e9

    def __init__(
        self,
        personas: Sequence[Persona],
        cooldown: int = 1,
        host_intervention_after: int | None = 3,
        min_speech_chars: int = 20,
        max_speech_chars: int = 80,
        seed: int | None = None,
    ) -> None:
        self._personas: dict[int, Persona] = {persona.id: persona for persona in personas}
        self._host = next((persona for persona in personas if persona.is_host), None)
        self._experts = [persona for persona in personas if not persona.is_host]
        self._cooldown = max(cooldown, 0)
        self._host_intervention_after = host_intervention_after
        self._min_speech_chars = min_speech_chars
        self._max_speech_chars = max_speech_chars
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ #
    # 调度主入口
    # ------------------------------------------------------------------ #
    def decide_next(self, history: Sequence[SpeechRecord]) -> ScheduleDecision:
        """根据历史发言决定下一位发言人。"""
        records = list(history)

        if self._should_host_take_over(records):
            return ScheduleDecision(
                persona_id=self._host.id,
                speech_type="intro" if not records else "speech",
                candidate_scores={self._host.id: self.HOST_TAKEOVER_SCORE},
            )

        eligible = {
            persona.id: self._score(persona, records)
            for persona in self._experts
            if not self._is_cooling_down(persona.id, records)
        }
        if not eligible:
            # 极端兜底：全员处于冷却期时临时放开限制，避免调度停摆
            eligible = {
                persona.id: self._score(persona, records)
                for persona in self._experts
            }

        best_id = max(eligible, key=lambda persona_id: eligible[persona_id])
        return ScheduleDecision(
            persona_id=best_id,
            speech_type=self._speech_type(best_id, records),
            candidate_scores=eligible,
        )

    # ------------------------------------------------------------------ #
    # 评分细则
    # ------------------------------------------------------------------ #
    def _score(self, persona: Persona, history: Sequence[SpeechRecord]) -> float:
        score = 1.0 + 0.6 * min(self._idle_turns(persona.id, history), 5)

        if history:
            last_speaker = self._personas.get(history[-1].persona_id)
            if last_speaker is not None and last_speaker.stance_side in ("pro", "con"):
                if _OPPOSITE_SIDE.get(last_speaker.stance_side) == persona.stance_side:
                    score += self.CONFLICT_BONUS
                elif persona.stance_side == "neutral":
                    score += self.NEUTRAL_BONUS

            share = sum(1 for record in history if record.persona_id == persona.id) / len(history)
            score -= self.BALANCE_PENALTY * share

        score += self._rng.uniform(0.0, 0.9)
        score += self._rotation_penalty(persona.id, history)
        return round(score, 6)

    def _rotation_penalty(self, persona_id: int, history: Sequence[SpeechRecord]) -> float:
        """若加入该候选人会让序列形成 2-5 长度的重复周期，则重罚。"""
        sequence = [record.persona_id for record in history] + [persona_id]
        for period in range(2, 6):
            if len(sequence) < period * 2:
                continue
            if sequence[-period:] == sequence[-2 * period : -period]:
                return self.ROTATION_PENALTY
        return 0.0

    def _idle_turns(self, persona_id: int, history: Sequence[SpeechRecord]) -> int:
        """距离该专家上次发言已过去多少条他人发言。"""
        for offset, record in enumerate(reversed(history)):
            if record.persona_id == persona_id:
                return offset
        return len(history)

    def _is_cooling_down(self, persona_id: int, history: Sequence[SpeechRecord]) -> bool:
        """冷却期：刚发言的专家需至少间隔 cooldown + 1 次他人发言。"""
        blocked_turns = self._cooldown + 1
        for offset, record in enumerate(reversed(history)):
            if record.persona_id == persona_id:
                return offset < blocked_turns
        return False

    def _should_host_take_over(self, history: Sequence[SpeechRecord]) -> bool:
        """专家连续发言达到阈值时，主持人强制接管。"""
        if self._host is None or self._host_intervention_after is None:
            return False

        streak = 0
        for record in reversed(history):
            if record.persona_id == self._host.id:
                break
            streak += 1
        return streak >= self._host_intervention_after

    def _speech_type(self, persona_id: int, history: Sequence[SpeechRecord]) -> SpeechType:
        """立场对立时标记为 counter，否则为普通 speech。"""
        if not history:
            return "speech"

        last_speaker = self._personas.get(history[-1].persona_id)
        current = self._personas[persona_id]
        if (
            last_speaker is not None
            and last_speaker.stance_side in ("pro", "con")
            and _OPPOSITE_SIDE.get(last_speaker.stance_side) == current.stance_side
        ):
            return "counter"
        return "speech"

    # ------------------------------------------------------------------ #
    # 文本收敛校验
    # ------------------------------------------------------------------ #
    def validate_speech(self, text: str) -> str:
        """把发言收敛到 1-2 句、20-80 字；无法满足时抛出校验异常。"""
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        if not cleaned:
            raise SpeechValidationError("发言内容为空")

        sentences = [
            sentence.strip()
            for sentence in _SENTENCE_PATTERN.findall(cleaned)
            if sentence.strip()
        ]
        if not sentences:
            raise SpeechValidationError("发言内容缺少有效句子")

        candidate = "".join(sentences[:2])
        if len(candidate) > self._max_speech_chars:
            candidate = sentences[0]
        if len(candidate) > self._max_speech_chars:
            candidate = candidate[: self._max_speech_chars - 1].rstrip("，,、；;：: ") + "。"

        candidate = candidate.strip()
        if len(candidate) < self._min_speech_chars:
            raise SpeechValidationError(
                f"发言过短：{len(candidate)} 字，至少需要 {self._min_speech_chars} 字"
            )
        return candidate
