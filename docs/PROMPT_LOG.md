# Prompt 执行日志 · PROMPT_LOG

| 项目 | 内容 |
| --- | --- |
| 项目 | AI Panel Studio（AI 圆桌讨论演播厅） |
| 记录时间 | 2026-11-17 |
| 阶段标记 | 第一阶段：【SDD 阶段】数据建模与 API 契约生成<br/>第二阶段：【TDD 阶段】核心调度逻辑的测试用例编写与业务实现<br/>第三阶段：【DDD 阶段】前端组件与页面生成<br/>第四阶段：【Integration 阶段】流式全链路联调与并发隔离<br/>第五阶段：【E2E 阶段】系统级端到端测试与质量闭环 |
| 产出物 | PRD.md · schema.sql · ARCHITECTURE.md · API.md · tests/test_scheduler.py · tests/test_insight.py · tests/test_e2e.py · scripts/seed_data.py · services/scheduler.py · services/insight_extractor.py · services/llm_service.py · services/room_manager.py · utils/sanitizer.py · api/routes.py · db/database.py · main.py · frontend/src/api/client.js · frontend/src/components/* · frontend/src/stores/studioStore.js |

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

---

# 第四阶段记录

## 1. 阶段标记

**【Integration 阶段】流式全链路联调与并发隔离**

本阶段把 TDD 阶段测通的调度器与洞察提炼器接入 FastAPI，通过 SSE 长连接把真实讨论进程推送到 Vue 3 演播厅，并以 `room_id` 为键隔离多个房间的运行态与广播队列。

| 校验项 | 结果 |
| --- | --- |
| 后端单元测试 | `pytest -q`：`7 passed` |
| 单房间流式全链路 | 248 个 `token` / 10 次 `speech_end` / 3 次 `insight_update` / 1 次 `summary` + `done` |
| 双房间并发隔离 | 两场讨论同时运行，事件 `room_id` 错配数 `wrong_room = 0` |
| 前端生产构建 | `npm run build` 成功 |
| 浏览器实操 | 发起讨论 → 速记增长 → 洞察刷新 → 总结大卡片，全流程 PASS |

---

## 2. 原始 Prompt（完整原文）

```text
你现在是一个精通异步高并发与 LLM 流式通信的全栈技术专家。我们进入第四阶段：【Integration 阶段（前后端流式联调与并发隔离）】。
请将已在 TDD 阶段测通的核心调度逻辑（scheduler.py、insight_extractor.py）与前端演播厅界面（Vue 3）通过 FastAPI 和 SSE 流式通道全面打通：
1.后端数据库与环境配置：
在 backend/requirements.txt 中追加：fastapi>=0.100.0、uvicorn>=0.23.0、aiosqlite>=0.19.0、python-dotenv>=1.0.0、openai>=1.0.0、httpx>=0.24.0；
创建 backend/.env.example 与 backend/.env（配置 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL）；
编写 backend/app/db/database.py：基于 aiosqlite 异步连接 SQLite（数据文件存放在 backend/data/panel_studio.db），启动时自动执行 schema.sql 建表。
2.后端核心服务与 SSE 引擎（支持多房间隔离）：
编写 backend/app/services/llm_service.py：
封装动态生成阵容（主持人 + N 位鲜明立场专家，按颜色规范生成色标）；
封装根据当前讨论上下文流式生成单次短发言（严格限制 1-2 句核心观点）；
针对无 API Key 场景内置自测演示模式（Mock Stream），保证离线状态也能跑通完整流式打字机交互；
编写 backend/app/services/room_manager.py：
维护房间运行状态机，以 room_id 为键维护独立的 asyncio.Queue 广播队列，确保多个讨论房间并发运行完全物理隔离、互不干扰；
调度循环：主持人开场 -> 调度器选拔专家交锋 -> 实时提取共识分歧 -> 达到预设轮次由主持人自然语言陈词总结 -> 广播 done 结束事件。
3.后端 REST 与 SSE 路由（backend/app/api/routes.py）：
实现 GET /api/rooms、POST /api/rooms、GET /api/rooms/{id}、POST /api/rooms/{id}/start；
实现 GET /api/rooms/{id}/events：返回 StreamingResponse(..., media_type='text/event-stream')，严格发送符合 SDD 规范的 5 种标准事件（token, status_change, insight_update, speech_end, summary, done），并处理客户端异常断开时的协程优雅释放。
4.前端状态联调与流式打字机消费：
替换前端原有的静态 Mock 数据，编写 frontend/src/api/ 网络请求层；
在演播厅页面中使用 fetch 结合流式读取器（response.body.getReader()）解析 SSE 流：
收到 token 事件：在当前发言专家气泡中呈现流畅打字机效果，中间对白流自动平滑滚动吸底；
收到 status_change 事件：即时更新对应专家的呼吸灯状态（idle/thinking/speaking）；
收到 insight_update 事件：右侧共识与分歧卡片以动画平滑更新；
收到 summary 事件：弹出演播厅终结大卡片，展示主持人的自然语言总结词。
请在当前工程中完整编写并更新前后端代码，解决 CORS 跨域问题，确保启动后可以真正发起一场实时圆桌讨论。
```

---

## 3. 设计意图

本阶段将 FastAPI 的异步 SSE 事件流与 Vue 3 前端的流式读取渲染器直接对接，让 token、状态、洞察与总结事件在同一条长连接内按序抵达并由前端即时呈现。后端以 `room_id` 为键维护独立的 `asyncio.Queue` 与运行态，使多场圆桌讨论在调度、历史与广播层面完全物理隔离、并发互不干扰。

---

## 4. 挑战与 AI 引导过程

初版实现中，客户端刷新或断线后生成器未被及时释放，容易造成后端协程挂死；同时 SSE 响应缺少强制刷新与心跳，代理缓冲会让文字出现明显卡顿。通过引导 AI 在事件生成器中加入异步心跳保活、断开检测与 `finally` 释放逻辑，并统一关闭响应缓冲，最终保证了长链路流式交互的稳定性。

---

# 第五阶段记录

## 1. 阶段标记

**【E2E 阶段】系统级端到端测试与质量闭环**

本阶段补齐交付前的质量闭环：用纯自然语言脱敏器清洗全链路输出，预置 5 场开箱即用的深度圆桌样例，并以 `pytest` + `httpx.AsyncClient` 跑通「创建议题 → 阵容契约 → SSE 事件流 → 数据库终态」的完整验收链路。

| 校验项 | 结果 |
| --- | --- |
| 样例数据注入 | 新增 5 个房间，每场 1 主持 + 4 专家、10 条速记、4 条看板；重复执行输出「跳过 5 场（幂等）」 |
| 端到端测试 | `pytest backend/tests/test_e2e.py -v`：`1 passed in 4.63s` |
| 全量回归 | `pytest backend/tests -q`：`8 passed in 5.06s`（原有 7 条无回归） |
| 输出脱敏 | 脏输入（json 代码围栏 + `{"summary": ...}`）清洗后仅剩纯自然语言；`[举手]`、`系统通知:` 零残留；公开摘要 ≤ 15 字 |

---

## 2. 原始 Prompt（完整原文）

```text
你现在是一个资深全栈 QA 专家与数据架构师。我们进入第五阶段：【E2E 阶段（端到端测试与质量闭环）】。
请针对作业要求的验收标准，完成输出清洗、5 组样例数据注入以及端到端集成测试：
1.全链路输出脱敏与去 JSON 化过滤器（backend/app/utils/sanitizer.py）：
总结词清洗：编写鲁棒的自然语言提取函数。若大模型总结返回了带 markdown 标记的代码块（如 json {"summary": "..."}）或带有 JSON 键值对，通过正则与解析器强行剥离，100% 确保返回给前端的是一段富有演播厅感染力的纯自然语言总结陈词；
对白流净化：过滤掉大模型可能夹带的内部控制字符（如 [举手]、[反驳]、系统通知: 等），确保现场 Transcript 只呈现干净的发言正文；
思维链隐藏：专家小窗的思考状态只保留 15 字以内的公开观点摘要，严禁暴露大模型的原始推理思维链（CoT）。
2.预置 5 组高质量演播厅样例数据（backend/scripts/seed_data.py）：
编写独立的数据库初始化灌库脚本，向 SQLite 中注入 5 场高深度、高对抗性的真实完整圆桌讨论（包含完整的房间、主持人 + 4 位专家、至少 8~10 轮精彩对白速记、以及提取好的共识与分歧看板数据）：
样例 1（科技伦理）：《通用人工智能（AGI）若具备自主意识，是否应享有基础数字人权？》
样例 2（商业战略）：《中小企业自研垂直大模型是自寻死路，还是建立护城河的唯一解？》
样例 3（教育科技）：《当 AI 能秒解考题并提供 1 对 1 教学，公立学校教育体系该去向何方？》
样例 4（劳动力市场）：《程序员职业的黄昏？初级开发人员在 3 年内会被 AI Agent 彻底替代吗？》
样例 5（前沿哲学）：《脑机接口全面普及后，“记忆共享与重组”是否会终结人类个体的独立存在？》
确保新部署的数据库一键运行 python backend/scripts/seed_data.py 即可拥有开箱即用的完整展示数据。
3.系统级端到端测试（backend/tests/test_e2e.py）：
使用 pytest 和 httpx.AsyncClient 编写异步端到端测试：
完整测试链：创建议题 -> 验证生成的 1 主持人 + 4 专家数据契约 -> 启动房间 -> 校验 SSE 事件流各消息包格式（token、status_change、insight_update、summary、done）无乱码与 JSON 泄露 -> 校验数据库最终持久化状态。
4.在终端执行数据注入并在虚拟环境中运行测试：
执行 backend\venv\Scripts\python backend/scripts/seed_data.py
执行 backend\venv\Scripts\pytest backend/tests/test_e2e.py，确保端到端测试全部通过（PASSED）。
请创建并编写上述代码，完成数据灌装与端到端质检。
```

---

## 3. 设计意图

执行系统级端到端验收测试，以临时 SQLite 与真实 SSE 长连接串起 REST 契约、事件帧格式与数据库终态的完整闭环；同时编写严格的数据清洗过滤器杜绝 JSON 泄露与思维链暴露，并注入 5 组覆盖科技、商业与哲学的深度圆桌数据作为开箱即用样例。

---

## 4. 挑战与 AI 引导过程

大模型在执行阶段总结时极易输出 markdown 代码块包裹的 JSON 字符串，直接透传会破坏前端终结卡片的排版；引导 AI 在后端设计基于正则与降级容错的 Sanitizer 清洗器，先提取 `summary` 字段再逐层剥离围栏、键名与结构符号，并对空结果回退到演播厅陈词。清洗器同时接入阵容、流式发言、洞察与总结四条出站路径，成功保障了演播厅总结 100% 呈现富有演讲感的纯自然语言。



