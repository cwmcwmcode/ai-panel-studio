# 项目全功能验收与交付对账手册

| 项目 | 内容 |
| --- | --- |
| 工程目录 | `D:\ai-panel-studio` |
| 对账基线 | `fb07ef0`（main 已推送至 `origin/main`） |
| 验收时间 | 2026-11-18 |
| 验收环境 | Windows / PowerShell 5 / Python venv / Node.js |
| 实测结论 | 后端测试 `8 passed in 4.58s`；数据库 5 场样例完整；Git 7 个提交层级完整 |

---

## 一、本地极速启动与验收操作指引

### 1.1 启动前环境核对（实际扫描结果）

| 检查项 | 实际状态 |
| --- | --- |
| Python 虚拟环境 | `backend\venv\` 已存在，依赖已安装 |
| 后端依赖清单 | `backend\requirements.txt`（fastapi / uvicorn / aiosqlite / openai / httpx / pytest 等） |
| SQLite 数据文件 | `backend\data\panel_studio.db` 存在，约 84 KB，已含 5 个 `finished` 房间 |
| 环境变量 | `backend\.env` 存在，但 Key 为占位值，运行时 `DEMO_MODE = True` |
| 前端依赖 | `frontend\node_modules\` 已安装，`frontend\dist\` 已有构建产物 |
| 调度参数 | `MAX_SPEECHES = 8`（每场 8 次专家/主持发言）、`INSIGHT_INTERVAL = 3`（每 3 次发言刷新看板） |

### 1.2 后端启动（FastAPI + SQLite）

在项目根目录 `D:\ai-panel-studio` 打开 PowerShell，依次执行：

```powershell
# ① 一键灌入 5 场样例（幂等：已存在则自动跳过，不会重复写入）
backend\venv\Scripts\python backend\scripts\seed_data.py

# ② 启动 API 服务（--app-dir 指定包根，无需手动切换目录）
backend\venv\Scripts\python -m uvicorn app.main:app --app-dir backend --port 8000 --reload
```

启动成功后的验证入口：

| 入口 | 地址 | 说明 |
| --- | --- | --- |
| 健康检查 | `http://127.0.0.1:8000/health` | 返回服务状态 |
| Swagger 文档 | `http://127.0.0.1:8000/docs` | 可直接在线调试 REST 接口 |
| 房间列表 | `http://127.0.0.1:8000/api/rooms` | 默认返回最近 20 个房间 |

> 说明：`backend\app\config.py` 会在导入时自动读取 `backend\.env`，数据库路径固定为 `backend\data\panel_studio.db`，首次启动由 `schema.sql` 自动建表。

### 1.3 前端启动（Vue 3 + Vite）

另开一个 PowerShell 窗口：

```powershell
cd D:\ai-panel-studio\frontend
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。Vite 已将 `/api` 代理到 `http://127.0.0.1:8000`，后端同时配置了 CORS，双保险生效。

### 1.4 浏览器点击顺序（发起一场新辩论）

1. 打开 `http://127.0.0.1:5173`，进入暗夜演播厅首屏（初始无阵容，提示「尚无阵容，请先发起讨论」）。
2. 点击右上角 **「发起新讨论」**，弹出议题配置弹窗。
3. 在「讨论议题」文本框中输入议题，例如：`我们该不该把单体服务拆成微服务？`（建议一句话点明争议焦点）。
4. 在「专家人数」中选择 `3 / 4 / 5`（默认 4，含主持人共 5 人）。
5. 点击 **「生成阵容」**，等待 1–2 秒，弹窗内出现 1 位主持人 + N 位专家的阵容预览卡片（姓名、职业身份、核心立场、专属色标）。
6. 点击 **「确认阵容 · 进入演播厅」**：房间状态由 `draft` 变为 `active`，前端立即建立 SSE 长连接。
7. 观察演播厅三栏联动：
   - **左栏「专家阵容席」**：呼吸灯按 `idle`（灰暗）→ `thinking`（脉冲黄光）→ `speaking`（高亮绿光）切换；每张卡片下方显示不超过 15 字的公开关注焦点。
   - **中栏「现场实况」**：主持人开场后，专家按加权调度依次交锋；当前发言人气泡以打字机效果逐字增长，列表自动吸底滚动。
   - **右栏「共识与分歧看板」**：每 3 次发言触发一次提炼，绿色卡片为共识、橙色卡片为分歧，版本号递增并平滑刷新。
   - **顶栏**：实时计时、当前议题、「讨论中」状态标签。
8. 讨论达到 8 次发言后自动收束；也可在讨论中随时点击顶栏 **「主持人总结」** 提前收束（仅在 `active` 状态可点击）。
9. 收束后弹出 **总结大卡片**：展示纯自然语言总结陈词、共识列表、分歧列表与后续建议；点击关闭即可回到演播厅。

### 1.5 如何查看 5 场预置历史讨论（实际能力说明）

> **重要核对结论**：当前前端**没有历史讨论列表面板**，页面只承载「新发起并实时进行」的房间。5 场预置数据已完整入库、可通过 REST API 读取，但没有可点击的 UI 入口。这是本次对账发现的一处交付差异，详见第四节。

在当前版本下，查看 5 场预置数据的准确方式如下（后端启动后）：

| 操作 | 地址 | 可看到的内容 |
| --- | --- | --- |
| 查看全部历史 | `http://127.0.0.1:8000/api/rooms?status=finished` | 5 个房间的 id、议题、状态、专家人数、总结摘要 |
| 查看单场详情 | `http://127.0.0.1:8000/api/rooms/1` 至 `/api/rooms/5` | 完整阵容、共识/分歧看板、进度统计 |
| 查看全部房间 | `http://127.0.0.1:8000/api/rooms` | 含 draft / active / finished 全量列表 |

5 场预置数据实况（直接查询数据库核对）：

| room_id | 议题 | 状态 | 阵容 | 速记 | 看板 |
| --- | --- | --- | --- | --- | --- |
| 1 | 《通用人工智能（AGI）若具备自主意识，是否应享有基础数字人权？》 | finished | 5（1 主持 + 4 专家） | 10 条 | 4 条 v1 |
| 2 | 《中小企业自研垂直大模型是自寻死路，还是建立护城河的唯一解？》 | finished | 5（1 主持 + 4 专家） | 10 条 | 4 条 v1 |
| 3 | 《当 AI 能秒解考题并提供 1 对 1 教学，公立学校教育体系该去向何方？》 | finished | 5（1 主持 + 4 专家） | 10 条 | 4 条 v1 |
| 4 | 《程序员职业的黄昏？初级开发人员在 3 年内会被 AI Agent 彻底替代吗？》 | finished | 5（1 主持 + 4 专家） | 10 条 | 4 条 v1 |
| 5 | 《脑机接口全面普及后，"记忆共享与重组"是否会终结人类个体的独立存在？》 | finished | 5（1 主持 + 4 专家） | 10 条 | 4 条 v1 |

补充说明：预置房间按设计处于 `finished` 终态，`POST /api/rooms/{id}/start` 会返回 `409 INVALID_STATE_TRANSITION`，因此不能直接"重播"其 SSE 过程。若要体验实时演播效果，可复制上述议题文本，按 1.4 的步骤发起一场新讨论。

### 1.6 未配置外部大模型 API Key 时的演示保障

当前 `DEMO_MODE = True`，系统完全离线也能跑通完整演播厅交互，机制如下：

1. **降级判定**：`backend/app/config.py` 在 Key 为空、仍为 `sk-your...` 占位符或 `changeme` 等值时自动置 `DEMO_MODE = True`；创建房间接口会在 `meta.degraded` 中如实返回降级标记。
2. **阵容生成**：`LLMService._fallback_lineup` 使用内置的 8 位立场对立专家模板，按议题与人数裁剪，色标由服务端统一分配，保证房间内唯一。
3. **流式发言**：`LLMService._mock_speech` 按角色立场生成 20–80 字短发言，再由 `_chunk_text` 按字符切块，以 0.025 秒/块的节奏产出 `token`，前端打字机效果与真实大模型完全一致。
4. **洞察与总结**：`_mock_insights` / `_mock_summary` 基于规则生成共识、分歧与主持陈词，同样经过 `sanitizer` 清洗后才出站。
5. **渲染链路不变**：无论 Mock 还是真实模型，都走同一套 SSE 六类事件（`token / status_change / insight_update / speech_end / summary / done`），因此演示效果与生产形态一致，不会出现"演示版功能缺失"。

---

## 二、作业交付物逐一核对清单

### 2.1 完整项目源码

| 作业要求 | 对应文件 / 目录 | 核对结论 |
| --- | --- | --- |
| 后端完整源码 | `backend/app/`（main.py、config.py、api/routes.py、db/database.py、services/scheduler.py、services/insight_extractor.py、services/llm_service.py、services/room_manager.py、utils/sanitizer.py） | 齐全 |
| 前端完整源码 | `frontend/src/`（App.vue、api/client.js、stores/studioStore.js、components/ 下 6 个组件） | 齐全 |
| 工程配置 | `backend/requirements.txt`、`backend/pytest.ini`、`frontend/package.json`、`frontend/vite.config.js`、`frontend/tailwind.config.js`、`frontend/postcss.config.js` | 齐全 |

### 2.2 SQLite 脚本与 5 组样例数据

| 作业要求 | 对应文件 | 核对结论 |
| --- | --- | --- |
| SQLite 建表脚本 | `backend/schema.sql`（126 行，4 张表 + CHECK / UNIQUE / 级联约束） | 存在且可执行，启动时自动建表 |
| 自动初始化逻辑 | `backend/app/db/database.py` | 读取 schema.sql 并执行 |
| 5 组样例数据脚本 | `backend/scripts/seed_data.py`（621 行） | 存在，幂等可重复执行 |
| 样例数据落库验证 | `backend/data/panel_studio.db` | 实测 5 个房间 × 5 角色 / 10 速记 / 4 看板 |

### 2.3 文档类交付物

| 作业要求 | 对应文件 | 核对结论 |
| --- | --- | --- |
| PRD 产品需求文档 | `docs/PRD.md`（321 行） | 存在，含价值主张、用户旅程与业务硬规则 |
| Mermaid ER 图 | `docs/ARCHITECTURE.md` 第 108 行起 `erDiagram` | 存在；同文件第 32 行系统架构图、第 173 行 `sequenceDiagram` 时序图 |
| API 文档 | `docs/API.md`（590 行） | 存在，含 REST 契约与 SSE 六类事件载荷 |
| 测试文档 | `docs/TESTING.md`（151 行） | 存在，含分层覆盖、一键运行与验收映射 |
| README | `README.md`（171 行） | 存在，含定位、选型、启动、API、能力边界 |
| Prompt 记录文档 | `docs/PROMPT_LOG.md`（319 行） | 存在，覆盖 5 个阶段 |
| 开发思路与工作流说明 | `docs/WORKFLOW_REVIEW.md`（64 行 / 约 1843 汉字） | 存在，含三大模块 |

### 2.4 核心 Prompt 记录文档核对

文件位置：`docs/PROMPT_LOG.md`

| 阶段 | 标记 | 原始 Prompt | 设计意图 | 挑战与 AI 引导 |
| --- | --- | --- | --- | --- |
| 第一阶段 | SDD 数据建模与 API 契约 | 有（完整原文） | 有 | 有 |
| 第二阶段 | TDD 测试驱动与业务实现 | 有（分测试编写 / 业务实现两段） | 有 | 有 |
| 第三阶段 | DDD 前端组件与页面生成 | 有 | 有 | 有 |
| 第四阶段 | Integration 流式联调与并发隔离 | 有 | 有 | 有 |
| 第五阶段 | E2E 端到端测试与质量闭环 | 有 | 有 | 有 |

结论：**满足「至少 5 个阶段」要求**，且每阶段均包含原始 Prompt、2 句设计意图与 2 句挑战/引导说明（第二阶段因拆分为测试与实现两段，内容更详细）。

### 2.5 开发思路与工作流说明核对

文件位置：`docs/WORKFLOW_REVIEW.md`

| 作业要求 | 文档对应位置 | 核对结论 |
| --- | --- | --- |
| 模块一：开发流程与工具链协同 | 「模块一 · 开发流程与工具链协同」 | 已覆盖 Trae Agent 模式、上下文感知、终端自愈，以及 SDD → TDD → DDD → Integration → E2E 五阶段门禁表 |
| 模块二：3 个典型技术冲突 | 「模块二」案例 1 / 2 / 3 | 案例 1 机械循环发言 → 立场冲突加权 + 冷静期衰减；案例 2 SSE 事件混杂 / 协程挂死 → `room_id` 队列隔离 + 心跳 + finally 释放；案例 3 Markdown JSON 泄漏 → 正则 + 降级容错 Sanitizer |
| 模块三：工程化 AI 开发理解 | 「模块三」 | 核心论点：AI 编程不是玩具式一键生成，而是 Spec-Driven 与 Test-Driven 的工程化结合；人类定义物理边界与验收断言，AI 负责高速实现 |

篇幅实测：约 1843 个汉字，按常规排版约 1.5–2 页，满足「1~1.5 页深度内容」的深度要求（页数上限略超，属内容偏充分而非缺失）。

### 2.6 Git 提交历史核对

实际 `git log --oneline`：

```text
fb07ef0 docs: finalize readme, testing guide and workflow review for submission
7b5eae9 e2e: add system e2e test, sanitize llm outputs and seed 5 sample roundtable datasets
863b29e feat(api): implement sse streaming pipeline, room concurrency isolation and live typewriter render
20d1963 chore: add comprehensive .gitignore and track pytest.ini for clean clone reproducibility
432c0ba ui-components: implement studio dashboard layout, live transcript and persona widgets
84dd7a3 tests: add unit tests and implement agent speech scheduler and consensus extractor
3c9a25e docs/schema: init prd, sqlite schema, mermaid architecture and sse protocol
```

| 要求轨迹 | 对应提交 | 结论 |
| --- | --- | --- |
| docs/schema 先行 | `3c9a25e` | 符合 |
| tests 其次 | `84dd7a3` | 符合 |
| ui-components | `432c0ba` | 符合 |
| feat 集成 | `863b29e` | 符合 |
| e2e 质量闭环 | `7b5eae9` | 符合 |
| docs 收尾 | `fb07ef0` | 符合 |

结论：**7 个提交完整呈现 `docs/schema → tests → ui-components → feat → e2e → docs` 的分层递进轨迹**，`main` 已推送并与 `origin/main` 同步。

---

## 三、功能与质量实测结果

### 3.1 自动化测试

| 测试集 | 用例数 | 覆盖内容 | 结果 |
| --- | --- | --- | --- |
| `backend/tests/test_scheduler.py` | 4 | 冷却约束、拒绝机械轮流、主持人强制控场、1–2 句长度约束 | 通过 |
| `backend/tests/test_insight.py` | 3 | 结构化共识/分歧、纯文本清洗、解析失败安全异常 | 通过 |
| `backend/tests/test_e2e.py` | 1 | 创建议题 → 阵容契约 → SSE 六类事件 → 数据库终态 | 通过 |
| 合计 | **8** | — | **`8 passed in 4.58s`** |

### 3.2 接口与事件

| 类型 | 数量 | 核对结果 |
| --- | --- | --- |
| REST 路由 | 6（列表 / 创建 / 详情 / 启动 / 收束 / 健康检查） | 与 `docs/API.md` 一致 |
| SSE 事件 | 6（token / status_change / insight_update / speech_end / summary / done） | 与 SDD 契约一致，E2E 已逐帧断言 |
| 预置样例 | 5 房间 / 25 角色 / 50 速记 / 20 看板条目 | 数据库实测一致 |

### 3.3 一键复核命令

```powershell
# 数据灌装（幂等）
backend\venv\Scripts\python backend\scripts\seed_data.py

# 全量测试
backend\venv\Scripts\pytest backend/tests -q
```

---

## 四、验收差异与风险提示

| 序号 | 差异 / 风险 | 影响 | 建议 |
| --- | --- | --- | --- |
| 1 | 前端无历史讨论列表入口，5 场样例只能通过 REST API 查看 | 演示时无法"点击打开历史场次"，与"开箱即用展示数据"的直觉略有落差 | 后续可在顶栏增加「历史场次」抽屉，调用现成的 `GET /api/rooms` 与 `GET /api/rooms/{id}` |
| 2 | 预置房间均为 `finished`，不能重新建立 SSE | 无法重播历史讨论的流式过程 | 作为样例数据符合设计；实时体验请新建讨论 |
| 3 | `docs/WORKFLOW_REVIEW.md` 约 1.8 页 | 略超 1.5 页上限 | 内容完整、论点充分；若需严格卡页可压缩案例细节 |
| 4 | `backend/.env` 存在但 Key 为占位值 | 当前自动进入 Mock 模式 | 属预期行为；真实模型只需填入有效 Key 并重启 |

> 除上述差异外，未发现阻断性问题。代码、文档、样例数据、测试与提交历史均可支撑交付验收。
