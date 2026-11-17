# Prompt 执行日志 · PROMPT_LOG

| 项目 | 内容 |
| --- | --- |
| 项目 | AI Panel Studio（AI 圆桌讨论演播厅） |
| 记录时间 | 2026-11-17 |
| 阶段标记 | 第一阶段：【SDD 阶段】数据建模与 API 契约生成<br/>第二阶段：【TDD 阶段】核心调度逻辑的测试用例编写与业务实现<br/>第三阶段：【DDD 阶段】前端组件与页面生成 |
| 产出物 | PRD.md · schema.sql · ARCHITECTURE.md · API.md · tests/test_scheduler.py · tests/test_insight.py · services/scheduler.py · services/insight_extractor.py · frontend/src/components/* · frontend/src/stores/studioStore.js |

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

---

# 第二阶段记录

## 1. 阶段标记

**【TDD 阶段】核心调度逻辑的测试用例编写与业务实现**

本阶段分两步走：先在零实现状态下用 Pytest 锁定 7 条断言（调度器 A/B/C/D 四项 + 提炼器三例），全部红灯；再实现 `app/services/scheduler.py` 与 `app/services/insight_extractor.py`，直至 100% 绿灯。

| 状态 | 结果 |
| --- | --- |
| 红灯 | `7 failed`（`ModuleNotFoundError: No module named 'app'`） |
| 绿灯 | `7 passed in 0.85s` |

---

## 2. 原始 Prompt（完整原文）

### 2.1 测试用例编写

```text
你现在是一个严谨的软件测试架构师。我们进入第二阶段：【TDD 阶段（测试驱动开发）】。
我们必须攻克核心算法逻辑：『专家非机械轮流发言调度器』 与 『实时共识分歧提炼器』。按照 TDD 原则，必须先写单元测试，严禁直接跳去写业务实现。
请在内置终端与工程目录中执行以下操作：
1.D 盘虚拟环境搭建（防 C 盘污染）：
在 backend/ 目录下创建独立的虚拟环境：python -m venv backend/venv；
在 backend/requirements.txt 中写入：pytest>=7.4.0、pytest-asyncio>=0.21.0、pydantic>=2.0.0；
使用该虚拟环境安装依赖（Windows 下调用 backend\venv\Scripts\pip install -r backend\requirements.txt）。
2.编写核心调度算法测试用例 backend/tests/test_scheduler.py：
测试项 A（防自言自语 / Cooldown 约束）：断言同一个专家绝对不能连续发言两次（冷却周期 Cooldown ≥ 1）；
测试项 B（拒绝机械轮流发言）：模拟 20 次发言调度，统计发言序列，断言其绝对不是周期性的循环序列（如 1->2->3->4->1->2->3->4），必须呈现基于立场冲突的动态加权分布；
测试项 C（主持人强制控场介入）：当专家连续交锋达到指定轮次（如 3-4 轮），断言下一个发言人强制为主持人（负责追问、串联或推向下一阶段）；
测试项 D（发言长度约束）：断言通过调度器校验的发言文本必须被严格约束在 1-2 句话内（字数在 20~80 字之间，杜绝冗长长文）。
3.编写共识与分歧提取测试 backend/tests/test_insight.py：
传入一段模拟对白，测试结构化提取器能准确输出 consensus（共识）和 divergence（分歧）两组结构化列表，且不含大模型原始未清洗标记。
4.在终端运行测试 backend\venv\Scripts\pytest backend/tests。
预期结果：因为此时还没有编写业务实现，测试应该全部报错红脸（FAILED）。这正是 TDD 流程的正确开局。
```

### 2.2 业务实现

```text
TDD 第一步测试用例已全部就绪（当前为红脸 FAILED）。现在开始编写核心业务逻辑，使测试全部变绿：
1.实现自主发言调度器 backend/app/services/scheduler.py：
核心算法：基于立场的加权优先级状态机（Weighted Priority State Machine）；
规则：
每个嘉宾维护一个 priority_score（发言欲望值）和 cooldown（冷却计数）；
若上一轮发言人表达了立场 A，与其立场对立（Stance Opposed）的嘉宾获得高额『反驳欲望加权』；
刚刚发言完毕的嘉宾进入强制冷却（cooldown = 2），期间欲望值清零；
主持人维护一个连续专家发言计数器，当计数 ≥ 3 时，主持人权重置为无穷大，强制接管发言权（进行追问或串场）；
提供文本截断校验工具，将超长发言自动收敛至 1-2 句核心观点。
2.实现共识分歧提炼引擎 backend/app/services/insight_extractor.py：
结构化提取器：解析对话流，利用规则和 Prompt 模板提取高内聚的共识点与矛盾对立点，输出干净的 Pydantic 模型。
3.在终端再次运行测试：backend\venv\Scripts\pytest backend/tests。
修正代码直至所有测试用例 100% 全部通过（PASSED 绿脸）！
```

---

## 3. 设计意图

本阶段严格遵循测试驱动开发，针对作业强调的「非机械轮流发言」与「1-2 句短发言」核心规则，先在零实现状态下用 Pytest 断言锁死逻辑边界，再以红灯用例倒逼算法实现，确保代码不是「先写出来再补测试」。测试同时承担契约文档的职责：`Persona`、`SpeechRecord`、`InsightBoard` 等模型字段与 `validate_speech` 的截断语义均由断言反向定义，任何后续重构只要破坏语义就会立刻被红灯拦截。

---

## 4. 挑战与 AI 引导过程

挑战在于 AI 初版代码容易退化为「简单随机循环调度」——看似不重复，实则既无法证明立场冲突加权，也可能在特定 seed 下形成隐性周期；为此补充了反序列化测试（逐一否定周期 1–10、校验 20 轮内是否出现重复块）与连续发言断言（同一专家索引间隔 ≥ 2、单人占比 ≤ 40%），成功引导 AI 从随机轮转升级为「立场冲突加权 + 冷静期衰减」的加权状态机算法。另一处引导点在于提炼器：单纯要求「输出结构化列表」会得到带代码围栏与 Markdown 标签的脏数据，于是将「注入假模型输出 → 断言禁用标记零残留 → 断言解析失败不回显原文」写成三条用例，倒逼清洗链与安全异常成为实现的必要组成，而非事后补丁。

---

# 第三阶段记录

## 1. 阶段标记

**【DDD 阶段】前端组件与页面生成**

本阶段在 `frontend/` 下从零搭建 Vue 3 + Vite + Tailwind CSS 工程，按领域边界拆分出演播厅大屏、专家状态小窗、对白速记瀑布流、实时共识看板与议题配置弹窗，并以内存 Mock 状态驱动完整交互。

| 校验项 | 结果 |
| --- | --- |
| 生产构建 | `npm run build` 成功，16 modules，产物 92.39 kB JS / 19.25 kB CSS |
| 首屏三栏渲染 | 左侧 5 张阵容卡、中间对白气泡、右侧共识/分歧卡片全部可见 |
| 全局滚动约束 | 文档 `scrollHeight = clientHeight`，无文档级横竖向滚动条 |

---

## 2. 原始 Prompt（完整原文）

```text
你现在是一个资深前端架构师与 UI/UX 设计专家。我们进入第三阶段：【DDD 阶段（领域组件驱动开发）】。
我们需要为『AI Panel Studio』构建一个具备专业电视台演播厅质感的现代化前端 Web 应用。
请在当前项目的 frontend/ 目录下完成前端脚手架与领域组件拆分：
1.前端工程初始化：
检查本地是否可用 Node/npm；
初始化基于 Vue 3 + Vite + Tailwind CSS 的工程结构（若需安装依赖，依赖必须严格限制在 frontend/node_modules 下）；
配置 Tailwind CSS，确立暗夜演播厅色系（背景 bg-slate-950、卡片 bg-slate-900/80、边框 border-slate-800）。
2.核心页面布局（演播厅大屏 Dashboard）：
必须遵守作业硬性规则：根节点 h-screen overflow-hidden flex flex-col，全局禁止出现主滚动条！
页面采用上中下三层流式响应结构：
顶部栏（StudioHeader.vue）：展示当前讨论议题、会议进行时间、状态标签（未开始/讨论中/已总结）、以及『发起新讨论』和『主持人总结』操作按钮；
核心交互区（三栏网格式工作台）：
左侧（专家阵容席 25%）：垂直排列 1 位主持人 + N 位专家小窗，内部独立滚动；
中间（现场实况流 LiveTranscript.vue 50%）：大屏对白滚动瀑布流，自动吸底，发言人专属色标气泡，只显示对话正文；
右侧（实时共识与分歧看板 InsightBoard.vue 25%）：动态卡片双栏流，绿色高亮共识点，橙色高亮分歧争论点，实时刷新，内部独立滚动；
3.领域组件细化与防翻车设计：
PersonaCard.vue（专家状态小窗）：
动态接收专属颜色十六进制色标，呈现边框微光；
状态机呼吸灯：idle（灰暗待机）、thinking（脉冲黄光，提示‘正在构思’）、speaking（高亮绿光，提示‘正在发言’）；
包含一行 15 字内的『关注焦点/公开摘要』，严禁暴露底层隐藏思维链；
DiscussionSetupModal.vue（议题配置弹窗）：
用户输入议题文本与专家人数选择器（默认 4 人）；
生成后的主持人与专家卡片预览与确认按钮。
4.组件 Mock 状态自测：
在 Vue Store 或状态层预置一套完整的模拟数据（模拟一位专家正在发言、实时对白流动态追加、共识面板动态卡片），确保直接启动前端时即可肉眼核验演播厅交互与自适应效果。
请创建并完整编写上述前端代码，确保 npm run build 或 npm run dev 能顺利启动。
```

---

## 3. 设计意图

本阶段按照领域驱动设计理念，把演播厅拆分为「专家状态小窗」「对白速记瀑布流」「实时共识看板」三大核心领域组件，各自持有独立的数据视图与滚动边界，使状态机、转录流与洞察流可以独立演进，避免退化为一个巨型页面组件。视觉上通过 Tailwind 统一暗夜演播厅色系（`bg-slate-950` 底、`bg-slate-900/80` 卡片、`border-slate-800` 描边）叠加径向光晕与网格底纹，用专属十六进制色标与呼吸灯把「谁在说话、谁在构思」变成可一眼扫读的导播台信息层级。

---

## 4. 挑战与 AI 引导过程

初版页面最容易出现的问题是内容随对白增长把整个文档撑高，产生全局主滚动条并导致三栏布局塌陷、头部与按钮被顶出视口。引导时明确施加 `h-screen overflow-hidden flex flex-col` 的根容器约束，并让三栏各自成为 `min-h-0` 的独立滚动容器（`overflow-y-auto` + 细滚动条），中间对白流再叠加自动吸底与「回到最新」逻辑，最终用浏览器实测确认 `scrollHeight == clientHeight`，达成电视台导播台级别的全屏响应式交互。


