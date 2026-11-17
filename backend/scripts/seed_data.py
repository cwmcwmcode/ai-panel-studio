"""预置 5 场演播厅样例数据。

一键运行：
    backend\\venv\\Scripts\\python backend/scripts/seed_data.py

脚本会向 backend/data/panel_studio.db 注入 5 场「已完成」的高对抗圆桌讨论：
每场包含 1 位主持人 + 4 位专家、开场 + 8 轮交锋 + 主持人总结、以及共识/分歧看板。

幂等策略：按议题判重，已存在的样例直接跳过，可反复执行而不产生重复数据。
所有文本在落库前统一经过 sanitizer，保证样例本身就是干净的纯自然语言。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import database  # noqa: E402
from app.utils.sanitizer import (  # noqa: E402
    sanitize_focus,
    sanitize_insight,
    sanitize_summary,
    sanitize_transcript,
)

HOST_COLOR = "#8B93A7"
EXPERT_COLORS = ("#E4572E", "#2E86AB", "#7A9E3F", "#B565A7")

# 对话元组：(发言方序号, speech_type, 正文)；0 为主持人，1-4 为对应专家
Dialogue = tuple[int, str, str]

SAMPLES: list[dict[str, Any]] = [
    {
        "topic": "《通用人工智能（AGI）若具备自主意识，是否应享有基础数字人权？》",
        "host": {
            "name": "沈知远",
            "title": "圆桌主持人 · 科技观察者",
            "stance": "中立引导，负责串联观点与收束结论",
            "focus": "串联观点并收束结论",
        },
        "experts": [
            {
                "name": "林觉",
                "title": "技术伦理学者",
                "stance": "主张赋予 AGI 有限的数字人格权，以约束人类滥用",
                "focus": "以赋权对冲滥用风险",
            },
            {
                "name": "何弦",
                "title": "AI 安全工程师",
                "stance": "反对先行赋权，意识不可验证且责任链条会断裂",
                "focus": "警惕责任链条断裂",
            },
            {
                "name": "苏黎",
                "title": "比较法学者",
                "stance": "支持设立第三种法律主体，但权利必须可撤回",
                "focus": "设计可撤回的法律主体",
            },
            {
                "name": "顾承",
                "title": "认知科学家",
                "stance": "强调当前没有任何意识判据，主张先立可验证标准",
                "focus": "先立可验证的意识判据",
            },
        ],
        "dialogue": [
            (
                0,
                "intro",
                "欢迎来到演播厅。本场议题是「AGI 若具备自主意识，是否应享有基础数字人权」，请各位亮明立场。",
            ),
            (
                1,
                "speech",
                "我主张赋予有限数字人格权：不是为了抬高机器，而是让人类滥用算力时有一个明确的追责对象。",
            ),
            (
                2,
                "counter",
                "我反对先行赋权。意识无法从外部验证，一旦承认主体地位，事故责任会被稀释到无人承担。",
            ),
            (
                3,
                "speech",
                "法律史上法人本就是拟制主体，AGI 可以走同一条路：权利清单化、可撤回、可监管。",
            ),
            (
                4,
                "counter",
                "问题在于判据。我们至今没有可复现的意识检测，先立法等于把定义权交给最会营销的实验室。",
            ),
            (
                1,
                "counter",
                "判据可以边立边修，医疗伦理也是先有原则再补细则，不能因为测量困难就放弃保护边界。",
            ),
            (
                2,
                "counter",
                "保护边界不等于赋予权利。给机器权利，人类受害者反而更难获得赔偿，这是本末倒置。",
            ),
            (
                3,
                "speech",
                "折中方案应当分层：先给不可剥夺的最小保护，再按能力等级逐级开放，而不是一次性全给。",
            ),
            (
                4,
                "speech",
                "我接受分层，但每一层都必须绑定可审计的行为证据，否则这套权利体系只会变成公关话术。",
            ),
        ],
        "summary": (
            "本场围绕 AGI 是否应享有基础数字人权展开。多数意见认同需要为高自主系统建立可审计的责任边界，"
            "但对是否以「权利」形式落地仍存根本分歧：一方认为赋权是对抗滥用的制度工具，"
            "另一方坚持意识不可验证、赋权会稀释人类追责。可推进的路径是分层、可撤回、绑定行为证据的最小保护框架。"
        ),
        "consensus": [
            "各方都认为高自主 AI 系统需要更清晰的责任与审计边界。",
            "分层、可撤回的制度设计被视为比一次性赋权更现实的路径。",
        ],
        "divergence": [
            "应以「数字人权」还是「责任义务」的形式落地，尚未收敛。",
            "意识判据缺失时能否先行立法，双方立场仍然对立。",
        ],
    },
    {
        "topic": "《中小企业自研垂直大模型是自寻死路，还是建立护城河的唯一解？》",
        "host": {
            "name": "沈知远",
            "title": "圆桌主持人 · 科技观察者",
            "stance": "中立引导，负责串联观点与收束结论",
            "focus": "串联观点并收束结论",
        },
        "experts": [
            {
                "name": "罗其",
                "title": "中小企业 CTO",
                "stance": "反对自研，认为算力与人才是无底洞",
                "focus": "警惕算力与人才黑洞",
            },
            {
                "name": "韩冬",
                "title": "垂直模型创业者",
                "stance": "主张自研是数据护城河的唯一解",
                "focus": "押注数据护城河",
            },
            {
                "name": "沈弦",
                "title": "产业投资合伙人",
                "stance": "条件性支持，关键看数据密度与场景闭环",
                "focus": "衡量数据密度与闭环",
            },
            {
                "name": "白芨",
                "title": "开源社区维护者",
                "stance": "认为微调开源模型比从零自研更务实",
                "focus": "以微调替代从零自研",
            },
        ],
        "dialogue": [
            (
                0,
                "intro",
                "欢迎来到演播厅。本场议题是「中小企业自研垂直大模型，是自寻死路还是护城河唯一解」，请各位亮明立场。",
            ),
            (
                1,
                "speech",
                "自研是自寻死路。基座模型按季度迭代，中小企业追一轮就耗尽一年利润，最后连主业都被拖垮。",
            ),
            (
                2,
                "counter",
                "通用模型永远听不懂行业黑话。垂直数据只在业务现场产生，不自研就永远在给别人做语料。",
            ),
            (
                3,
                "speech",
                "关键不是自研与否，而是数据密度：单场景年调用过百万次，自研的边际成本才可能收回来。",
            ),
            (
                4,
                "counter",
                "我反对从零自研，但支持深度微调：开源权重加行业数据，成本只有基座训练的百分之一。",
            ),
            (
                1,
                "counter",
                "微调也有隐性成本，推理集群、评测体系、版本回滚，哪一样都不是小团队能长期扛住的。",
            ),
            (
                2,
                "counter",
                "所以要用产品收入反哺模型，而不是把它当成本中心；护城河从来是场景闭环，不是参数规模。",
            ),
            (
                3,
                "speech",
                "我提醒一点，数据合规与客户授权是硬约束，很多行业数据根本拿不到训练许可，这条护城河未必挖得动。",
            ),
            (
                4,
                "speech",
                "那就把模型做小做专，用检索和工具调用补能力，别幻想用一个模型通吃所有流程。",
            ),
        ],
        "summary": (
            "本场围绕中小企业是否应自研垂直大模型展开。反对者强调基座迭代速度与算力成本会把中小企业拖入无底洞，"
            "支持者则认为行业数据只在现场产生，自研是唯一可持续的护城河。讨论逐渐收敛到「数据密度与场景闭环」"
            "这一判据：高调用频次、高授权确定性的场景值得投入，其余场景更适合微调开源模型并以检索补足能力。"
        ),
        "consensus": [
            "是否自研应由数据密度与场景闭环决定，而非技术潮流。",
            "数据合规与客户授权是自研路径绕不开的硬约束。",
        ],
        "divergence": [
            "深度微调开源模型能否形成真正的护城河，仍有争议。",
            "自研应作为成本中心还是收入引擎，双方判断不同。",
        ],
    },
    {
        "topic": "《当 AI 能秒解考题并提供 1 对 1 教学，公立学校教育体系该去向何方？》",
        "host": {
            "name": "沈知远",
            "title": "圆桌主持人 · 科技观察者",
            "stance": "中立引导，负责串联观点与收束结论",
            "focus": "串联观点并收束结论",
        },
        "experts": [
            {
                "name": "唐宁",
                "title": "教育政策研究者",
                "stance": "认为学校承担社会化与公平托底，不可被替代",
                "focus": "守住公平托底职能",
            },
            {
                "name": "陆遥",
                "title": "AI 教育产品负责人",
                "stance": "主张个性化教学将重构学习效率",
                "focus": "押注个性化学习效率",
            },
            {
                "name": "温言",
                "title": "公立中学校长",
                "stance": "反对技术替代，强调师生关系与同伴协作",
                "focus": "捍卫师生关系价值",
            },
            {
                "name": "江叙",
                "title": "学习科学教授",
                "stance": "条件性支持，主张混合式与教师增强",
                "focus": "设计混合式教学",
            },
        ],
        "dialogue": [
            (
                0,
                "intro",
                "欢迎来到演播厅。本场议题是「AI 能秒解考题并提供 1 对 1 教学，公立学校该去向何方」，请各位亮明立场。",
            ),
            (
                1,
                "speech",
                "学校从来不只是知识传输。它承担社会化、同伴协作与公平托底，这三件事 AI 一秒解题都替代不了。",
            ),
            (
                2,
                "counter",
                "但知识传输正是学校效率最低的环节。一个老师面对五十个学生，AI 却能给每个孩子定制路径和反馈。",
            ),
            (
                3,
                "counter",
                "定制路径听起来很美，可教育不是刷题。孩子需要被看见、被期待，这种关系是算法给不了的。",
            ),
            (
                4,
                "speech",
                "我不同意非此即彼。真正的问题是教师角色要不要重写：从讲授者变成学习设计师与情绪支持者。",
            ),
            (
                1,
                "counter",
                "重写角色说起来轻巧，县域学校连专职心理老师都没有，AI 反而可能是缩小差距的唯一机会。",
            ),
            (
                2,
                "counter",
                "机会取决于接入成本。如果个性化教学按家庭付费分层，它只会放大差距，而不是缩小差距。",
            ),
            (
                3,
                "speech",
                "所以我主张学校保留公共供给的底座，AI 作为课堂内的辅助工具，而不是把教育责任外包给家庭。",
            ),
            (
                4,
                "speech",
                "可以落地的是混合式：AI 负责诊断与练习，教师负责设计协作任务与价值引导，评价体系也要同步改写。",
            ),
        ],
        "summary": (
            "本场围绕 AI 一对一教学冲击下公立学校的去向展开。争论焦点不在于 AI 能否提效，"
            "而在于教育中不可让渡的部分：社会化、同伴协作与公平托底。讨论逐步收敛到「角色重写」而非「体系替代」："
            "AI 承担诊断与练习，教师转向学习设计与情感支持，同时必须守住公共供给底座，避免个性化教学按付费能力分层。"
        ),
        "consensus": [
            "AI 可以显著提升诊断与练习环节的效率，这一点没有争议。",
            "学校的社会化与公平托底职能不应被技术替代。",
        ],
        "divergence": [
            "个性化教学会缩小还是放大教育差距，双方判断相反。",
            "教师角色重写的边界与配套评价体系，尚未形成方案。",
        ],
    },
    {
        "topic": "《程序员职业的黄昏？初级开发人员在 3 年内会被 AI Agent 彻底替代吗？》",
        "host": {
            "name": "沈知远",
            "title": "圆桌主持人 · 科技观察者",
            "stance": "中立引导，负责串联观点与收束结论",
            "focus": "串联观点并收束结论",
        },
        "experts": [
            {
                "name": "程野",
                "title": "初级开发工程师",
                "stance": "担忧三年内被 Agent 替代，岗位入口正在消失",
                "focus": "担忧岗位入口消失",
            },
            {
                "name": "邵川",
                "title": "AI Agent 平台负责人",
                "stance": "主张替代不可避免且已经在发生",
                "focus": "判断替代已在进行",
            },
            {
                "name": "温岭",
                "title": "技术招聘负责人",
                "stance": "认为替代是分层发生的，并非一刀切",
                "focus": "观察分层替代现象",
            },
            {
                "name": "孟舟",
                "title": "软件工程教授",
                "stance": "反对彻底替代，强调复杂度与责任归属",
                "focus": "强调复杂度与责任",
            },
        ],
        "dialogue": [
            (
                0,
                "intro",
                "欢迎来到演播厅。本场议题是「初级开发人员三年内是否会被 AI Agent 彻底替代」，请各位亮明立场。",
            ),
            (
                2,
                "speech",
                "替代不是未来时，是现在进行时。需求拆解、样板代码、单测补全，Agent 已经能把初级岗位的交付吃下一大半。",
            ),
            (
                1,
                "counter",
                "我每天就在用 Agent，但我看到的是入口在消失。企业不再招初级，三年后谁来成长为能担责任的高级工程师？",
            ),
            (
                3,
                "speech",
                "招聘数据确实在分层：可被清晰描述的编码任务在收缩，但系统设计、跨团队协调与线上救火反而更缺人。",
            ),
            (
                4,
                "counter",
                "我反对「彻底替代」。软件复杂度在持续上升，Agent 生成得越多，理解与审计的负担就越重，最后仍要人来兜底。",
            ),
            (
                2,
                "counter",
                "兜底的人不需要那么多。一个高级工程师加十个 Agent，产出可能超过过去五个初级加一个高级。",
            ),
            (
                1,
                "counter",
                "那职业阶梯就断了。没有初级岗位练手，判断力从哪来？这不是效率问题，是行业再生产的问题。",
            ),
            (
                3,
                "speech",
                "所以我更愿意谈「重构入口」：企业需要把初级培养成 Agent 编排与评审者，而不是继续让他们手写样板代码。",
            ),
            (
                4,
                "speech",
                "结论我部分同意，但责任归属必须写清楚：Agent 产出的缺陷由谁签字，决定了这个职业会不会真的消失。",
            ),
        ],
        "summary": (
            "本场围绕初级开发人员三年内是否会被 AI Agent 彻底替代展开。多数意见承认可被清晰描述的编码任务正在快速收缩，"
            "但对「彻底替代」保持怀疑：系统复杂度、线上责任与职业阶梯的再生产，仍需要人类工程师承担。"
            "讨论收敛到一个更现实的判断：替代是分层发生的，行业需要把初级岗位重构为 Agent 编排、评审与兜底能力的培养入口。"
        ),
        "consensus": [
            "可被清晰描述的编码任务正在被 Agent 快速接管。",
            "复杂系统的审计、救火与责任签字仍需要人类工程师。",
        ],
        "divergence": [
            "三年内初级岗位是整体消失还是完成职能重构，判断不同。",
            "Agent 产出缺陷的责任归属，尚无行业共识。",
        ],
    },
    {
        "topic": "《脑机接口全面普及后，“记忆共享与重组”是否会终结人类个体的独立存在？》",
        "host": {
            "name": "沈知远",
            "title": "圆桌主持人 · 科技观察者",
            "stance": "中立引导，负责串联观点与收束结论",
            "focus": "串联观点并收束结论",
        },
        "experts": [
            {
                "name": "谢临",
                "title": "神经伦理学家",
                "stance": "认为记忆共享将终结个体独立存在",
                "focus": "警惕个体边界消融",
            },
            {
                "name": "谷雨",
                "title": "脑机接口工程师",
                "stance": "强调技术边界与带宽限制，短期内难以普及",
                "focus": "评估带宽与技术边界",
            },
            {
                "name": "齐岸",
                "title": "哲学家",
                "stance": "反对决定论，认为共享不等于同化",
                "focus": "辨析共享与同化",
            },
            {
                "name": "沈墨",
                "title": "记忆研究学者",
                "stance": "主张需要重新定义「主体」而非宣告终结",
                "focus": "重写主体定义",
            },
        ],
        "dialogue": [
            (
                0,
                "intro",
                "欢迎来到演播厅。本场议题是「记忆共享与重组是否会终结人类个体的独立存在」，请各位亮明立场。",
            ),
            (
                1,
                "speech",
                "我判断会。个体之所以是边界，正因记忆不可复制；一旦记忆可以共享与重组，「我」就失去了唯一性。",
            ),
            (
                2,
                "counter",
                "先把技术边界说清楚。现有接口带宽连稳定传一段高清视觉都吃力，谈全面记忆共享更像是科幻设定。",
            ),
            (
                3,
                "counter",
                "带宽只是工程问题，伦理问题不能等技术成熟才讨论。但共享不等于同化，人也可以选择保留私人记忆。",
            ),
            (
                4,
                "speech",
                "我倾向不说「终结」，而说「重写」。人格从来在关系中形成，记忆共享只是把关系密度推到了新量级。",
            ),
            (
                1,
                "counter",
                "关系密度推到极限就是消融。当你能随时调用他人的创伤记忆，共情会变成一种可购买的体验，主体性被商品化。",
            ),
            (
                3,
                "counter",
                "商品化是制度问题，不是记忆共享的必然结果。语言、文字、互联网都曾被认为会消解个体，结果并没有。",
            ),
            (
                2,
                "speech",
                "工程上更可能的形态是「读写不对称」：读取容易、写入困难，那会先制造权力不平等，而不是人人融合。",
            ),
            (
                4,
                "speech",
                "所以我主张把问题改成：如何在共享网络中保留不可让渡的私人记忆层，并用法律固定这条边界。",
            ),
        ],
        "summary": (
            "本场围绕脑机接口普及后记忆共享是否终结个体独立存在展开。悲观一方认为记忆可复制会抽掉「我」的唯一性，"
            "并担心共情被商品化；乐观一方强调共享不等于同化，人格本就在关系中形成。讨论把问题从「是否终结」"
            "推进到「如何重写主体定义」：更现实的关切是读写不对称带来的权力不平等，以及必须为私人记忆保留不可让渡的边界。"
        ),
        "consensus": [
            "记忆共享会深刻改变人格形成与关系结构，这一点没有分歧。",
            "需要为不可让渡的私人记忆层建立明确的法律与伦理边界。",
        ],
        "divergence": [
            "共享究竟会消融主体，还是只是重写主体定义，双方立场相反。",
            "读写不对称造成的权力不平等，尚无可行的治理方案。",
        ],
    },
]


def _persona_payload(
    data: dict[str, str], color: str, is_host: bool
) -> dict[str, Any]:
    return {
        "name": data["name"],
        "title": data["title"],
        "stance": data["stance"],
        "color_theme": color,
        "is_host": is_host,
        "current_focus": sanitize_focus(data.get("focus") or data["stance"]),
    }


async def _room_exists(topic: str) -> bool:
    async with database.get_connection() as conn:
        cursor = await conn.execute(
            "SELECT 1 FROM rooms WHERE topic = ? LIMIT 1", (topic,)
        )
        row = await cursor.fetchone()
    return row is not None


async def seed_sample(sample: dict[str, Any]) -> int | None:
    """写入单场样例，返回 room_id；已存在则返回 None。"""
    topic = sample["topic"]
    if await _room_exists(topic):
        return None

    room = await database.create_room(topic, len(sample["experts"]))
    room_id = int(room["id"])

    lineup = [_persona_payload(sample["host"], HOST_COLOR, True)]
    lineup += [
        _persona_payload(expert, EXPERT_COLORS[index], False)
        for index, expert in enumerate(sample["experts"])
    ]
    personas = await database.insert_personas(room_id, lineup)

    sequence = 0
    for speaker_index, speech_type, content in sample["dialogue"]:
        sequence += 1
        await database.insert_transcript(
            room_id,
            int(personas[speaker_index]["id"]),
            sequence,
            sanitize_transcript(content),
            speech_type,
        )

    summary_text = sanitize_summary(sample["summary"])
    sequence += 1
    await database.insert_transcript(
        room_id, int(personas[0]["id"]), sequence, summary_text, "summary"
    )

    items = [
        {"type": "consensus", "content": sanitize_insight(text)}
        for text in sample["consensus"]
        if sanitize_insight(text)
    ]
    items += [
        {"type": "divergence", "content": sanitize_insight(text)}
        for text in sample["divergence"]
        if sanitize_insight(text)
    ]
    await database.save_insights(room_id, 1, items)
    await database.finish_room(room_id, summary_text)
    return room_id


async def main() -> None:
    await database.init_db()

    created: list[tuple[int, str]] = []
    skipped = 0
    for sample in SAMPLES:
        room_id = await seed_sample(sample)
        if room_id is None:
            skipped += 1
        else:
            created.append((room_id, sample["topic"]))

    rows, total = await database.list_rooms(limit=50)
    print("=" * 72)
    print("AI Panel Studio · 样例数据注入完成")
    print("=" * 72)
    for room_id, topic in created:
        personas = await database.fetch_personas(room_id)
        transcripts = await database.fetch_transcripts(room_id)
        version, insights = await database.fetch_latest_insights(room_id)
        print(
            f"[新增] room_id={room_id} 角色={len(personas)}(主持人 1 + 专家 4) "
            f"速记={len(transcripts)} 看板v{version}={len(insights)}条"
        )
        print(f"       议题：{topic}")
    if skipped:
        print(f"[跳过] 已存在同议题样例 {skipped} 场（幂等）")
    print("-" * 72)
    print(f"数据库当前共 {total} 个房间，可直接启动后端展示。")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
