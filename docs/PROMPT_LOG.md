# Prompt 执行日志 · PROMPT_LOG

| 项目 | 内容 |
| --- | --- |
| 项目 | AI Panel Studio（AI 圆桌讨论演播厅） |
| 记录时间 | 2026-11-17 |
| 阶段标记 | 【SDD 阶段】数据建模与 API 契约生成 |
| 产出物 | docs/PRD.md · backend/schema.sql · docs/ARCHITECTURE.md · docs/API.md |

---

## 1. 阶段标记

**【SDD 阶段】数据建模与 API 契约生成**

本阶段处于规范驱动开发（Specification-Driven Development）的第一阶段，只产出规范与契约，不编写任何业务逻辑代码。

---

## 2. 原始 Prompt（完整原文）

```text
你是一个大厂资深架构师。我们正在从 0 到 1 打造一款名为『AI Panel Studio（AI 圆桌讨论演播厅）』的 Web 应用 MVP。
按照规范驱动开发（SDD）范式，现在严禁编写任何业务逻辑代码，请严格完成第一阶段的规范设计与架构落地：
1.创建基础工程目录结构：
Text
D:\ai-panel-studio\
├── docs/                  # 存放设计文档与评测记录
├── backend/               # Python FastAPI 后端
│   └── data/              # 存放 SQLite 本地文件
└── frontend/              # Vue 3 前端
2.落地 docs/PRD.md（产品需求文档）：
详细定义：核心价值主张、用户旅程（议题输入 -> 动态生成 1 主持人 + 4 专家 -> 阵容确认 -> 演播厅大屏交锋 -> 实时共识分歧 -> 主持人总结）；
核心业务硬规则：单次发言 1-2 句（杜绝长篇大论）、非机械轮流发言、专家状态独立小窗（不展示隐私 CoT 思维链）、严禁前端直接暴露大模型原始 JSON。
3.落地 backend/schema.sql（SQLite 专属数据库脚本）：
必须完全采用 SQLite 语法标准，设计 4 张核心表：
rooms（讨论房间表：id, topic, status[draft/active/finished], expert_count, summary, created_at, finished_at）；
personas（角色表：id, room_id, name, title, stance[核心立场], color_theme[专属色标十六进制], is_host, current_status[idle/thinking/speaking], current_focus）；
transcripts（现场实时速记表：id, room_id, persona_id, sequence_no, content, speech_type[intro/speech/counter/summary], created_at）；
insights（共识与分歧看板表：id, room_id, type[consensus/divergence], content, version, created_at）。
4.落地 docs/ARCHITECTURE.md（架构设计文档）：
必须使用 Mermaid 代码块 绘制完整的 ER 数据实体关系图（体现房间与各实体的 1 对多关联）；
必须使用 Mermaid 代码块 绘制从『用户发起议题 -> 阵容确认 -> SSE 长连接建立 -> 调度器竞争发言 -> 实时更新共识 -> 自然语言总结』的 系统交互时序图。
5.落地 docs/API.md（RESTful 与 SSE 事件契约）：
规范定义 REST 接口（创建房间、拉取历史、确认进入演播厅）；
规范定义 SSE（Server-Sent Events）事件通道 GET /api/rooms/{id}/events 的数据载荷结构，包含 5 种标准事件载荷：
event: token（发言打字机单字流）
event: status_change（专家呼吸灯状态切换）
event: insight_update（实时共识分歧动态刷新）
event: speech_end（单次发言结束）
event: summary（主持人终结发言）
请在本地创建并完整写入上述文件，排版必须专业严谨。
```

---

## 3. 设计意图

本阶段坚持规范先行，用 PRD 锁定「1 主持 + 4 专家、单次发言 1–2 句、非机械轮流」等业务硬规则，再用 `schema.sql` 把这些规则下沉为数据库级的 CHECK、UNIQUE 与级联约束，使约束在执行层无法被绕过。同时以 `API.md` 冻结 SSE 的 5 种强类型事件载荷，让前后端在写第一行业务代码之前就对齐字段语义、枚举取值与断线续传行为，避免后期因契约漂移导致的返工。

---

## 4. 挑战与 AI 引导过程

挑战一在于 SQLite 与 MySQL 语法极易混用，例如自增主键、时间默认值、部分索引和布尔表达式的写法差异；引导时明确要求采用 `INTEGER PRIMARY KEY AUTOINCREMENT`、`strftime` 生成 ISO8601 时间戳与 SQLite 专有的部分唯一索引（`WHERE is_host = 1`），并在交付前用内存数据库实际执行脚本，以 `integrity_check` 与外键检查验证语法确实成立。挑战二在于原始需求中的 SSE 事件仍是自由文本描述，无法直接指导编码；引导过程中将每个事件拆解为「触发时机、频率、固定字段、客户端处理契约」四要素，统一为单行压缩 JSON 的强类型载荷，并补充事件 `id` 续传语义、心跳保活与 `speech_end` 终态对齐机制，使 5 类事件成为可直接落地为 Pydantic 模型的可验证协议。
