# AI Panel Studio · AI 圆桌讨论演播厅

> 输入一个议题，自动组建「1 位主持人 + 4 位立场鲜明的专家」，在演播厅大屏上实时交锋，并同步产出共识、分歧与一段纯自然语言的主持总结。

**技术栈**：Python 3.11 · FastAPI · aiosqlite / SQLite · Vue 3.5 · Vite 5 · Tailwind CSS 3.4 · SSE

---

## 1. 项目简介

AI Panel Studio 是一款面向深度观点讨论的 Web 应用 MVP。它不是「一问一答」的聊天机器人，而是一个**有角色、有立场、有节奏、有收束**的圆桌演播厅：

| 核心特性 | 说明 |
| --- | --- |
| 动态阵容生成 | 围绕议题生成 1 位中立主持人与 4 位立场互相对立的专家，并分配唯一十六进制色标 |
| 非机械轮流发言 | 基于「立场冲突加权 + 冷却期衰减」的加权状态机选拔发言人，呈现真实的交锋节奏 |
| 1–2 句短交锋 | 单次发言强制收敛在 20–80 字，杜绝长篇大论，保证大屏可读性 |
| 实时共识看板 | 讨论过程中周期性提炼共识与分歧，右侧看板随版本号平滑刷新 |
| 自然语言总结 | 达到预设轮次后，主持人输出一段去 JSON 化、可直接上屏的纯自然语言陈词 |
| 独立状态小窗 | 每位专家拥有 idle / thinking / speaking 呼吸灯，仅展示 15 字以内公开摘要，不暴露思维链 |
| 多房间并发隔离 | 以 `room_id` 为键隔离运行态、历史与广播队列，多场讨论可同时进行互不干扰 |
| 往期演播厅回放 | 5 场预置经典讨论以卡片归档，点击即可只读回看完整对白、专家小窗、共识分歧与总结词 |
| 议题克隆重演 | 已结题房间提供「基于此议题重新推演」，一键克隆议题、重新生成阵容并进入实时讨论 |
| 真实大模型可插拔 | 配置 DeepSeek Key 即全量真实生成；Key 缺失、仍为占位符或网络异常时自动降级 Mock |

---

## 2. 技术选型理由

### 2.1 FastAPI —— 原生异步与 SSE 长连接

演播厅的核心交互是**服务端主动推送**：token 逐字抵达、状态灯切换、看板刷新、总结落屏。FastAPI 基于 ASGI，天然支持 `async/await` 与 `StreamingResponse`，可以在同一条 `text/event-stream` 连接上稳定推送六类事件，无需额外引入 WebSocket 基础设施或消息中间件；配合 Pydantic 的数据契约，接口字段在入口处即完成校验。

### 2.2 SQLite（aiosqlite）—— 轻量嵌入式、单文件隔离

MVP 阶段的数据规模以「房间级」为单位，读多写少、结构固定。SQLite 无需独立服务进程，整个数据库就是一个可随项目迁移的单文件，配合 `schema.sql` 中的 CHECK、UNIQUE 与级联约束，可以把「每个房间只有一位主持人」「房间内色标唯一」「结束房间必须有总结」等硬规则下沉到存储层。`aiosqlite` 提供非阻塞访问，避免阻塞事件循环。

### 2.3 Vue 3 + Tailwind CSS —— 演播厅级暗夜沉浸感

Vue 3 的响应式系统适合处理高频流式增量：SSE token 到达即更新当前发言气泡，无需手动操作 DOM。Tailwind 的原子化样式让暗夜色系（`bg-slate-950` / `bg-slate-900/80` / `border-slate-800`）与呼吸灯、微光边框、三栏独立滚动等视觉细节可以快速迭代，最终实现「全局无主滚动条」的全屏导播台布局。

---

## 3. 极速启动指南

### 3.0 前置要求

- Python 3.11+
- Node.js 18+ 与 npm

### 3.1 后端

```bash
# 1) 创建并激活虚拟环境（Windows PowerShell）
python -m venv backend/venv
backend\venv\Scripts\Activate.ps1

# 2) 安装依赖
pip install -r backend/requirements.txt

# 3) 一键灌入 5 场高质量样例讨论（幂等，可反复执行）
python backend/scripts/seed_data.py

# 4) 启动服务（必须进入 backend 目录，模块名才可解析）
cd backend
uvicorn app.main:app --port 8000 --reload
```

- 服务地址：`http://127.0.0.1:8000`，健康检查：`GET /health`
- 数据库文件：`backend/data/panel_studio.db`，首次启动自动建表
- 大模型配置：复制 `backend/.env.example` 为 `backend/.env`，填入 `LLM_API_KEY`，并按需设置：
  - `LLM_BASE_URL=https://api.deepseek.com`
  - `LLM_MODEL=deepseek-chat`

  填入有效 Key 后，阵容生成、流式交锋、共识提炼与总结均调用真实 DeepSeek；**Key 留空、仍是占位符或调用异常时自动降级为 Mock**，无需网络也能完整演示

### 3.2 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。Vite 已将 `/api` 代理到 `http://127.0.0.1:8000`，后端同时开启 CORS，形成双保险。

### 3.3 5 场预置讨论怎么看

1. 打开演播厅后点击顶栏 **「往期演播厅」**。
2. 抽屉列出 5 场「已结题」讨论，卡片含议题、专家人数与完成时间。
3. 点击任意卡片进入 `REPLAY` 只读回放：完整对白流、专家小窗、共识/分歧看板与主持人总结词。
4. 点击 **「基于此议题重新推演」** 可克隆该议题，生成新阵容并进入实时讨论。

样例数据幂等灌入：

```bash
backend\venv\Scripts\python backend/scripts/seed_data.py
```

### 3.4 一键验收

```bash
backend\venv\Scripts\pytest backend/tests -q
npm --prefix frontend run build
```

预期输出 `8 passed` 且前端构建成功。测试细节见 [docs/TESTING.md](docs/TESTING.md)。

---

## 4. 主要 API

统一响应信封：成功为 `{"data": ..., "meta": {...}}`，失败为 `{"error": {"code", "message", "details"}, "meta": {...}}`。

### 4.1 REST

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/rooms` | 房间列表，支持 `status`、`page`、`page_size` |
| `POST` | `/api/rooms` | 创建议题并生成 1 主持 + N 专家阵容 |
| `GET` | `/api/rooms/{room_id}` | 房间详情：阵容、完整速记、进度、最新共识/分歧看板 |
| `POST` | `/api/rooms/{room_id}/start` | 启动讨论，返回 SSE 订阅地址 |
| `POST` | `/api/rooms/{room_id}/finish` | 提前收束，触发主持人总结 |
| `GET` | `/health` | 健康检查 |

创建请求示例：

```json
{
  "topic": "AI 是否应参与公共政策制定？",
  "expert_count": 4,
  "style": "balanced"
}
```

### 4.2 SSE 事件流

`GET /api/rooms/{room_id}/events`，`Content-Type: text/event-stream`。

| 事件 | 触发时机 | 关键载荷 |
| --- | --- | --- |
| `token` | 逐字流式输出 | `persona_id`、`sequence_no`、`speech_type`、`delta`、`token_index` |
| `status_change` | 专家状态切换 | `persona_id`、`status`（idle/thinking/speaking）、`current_focus` |
| `insight_update` | 看板刷新 | `version`、`items[]`（type + content） |
| `speech_end` | 单次发言定稿 | `transcript_id`、`content`、`char_count`、`sentence_count` |
| `summary` | 主持人总结 | `summary`、`consensus[]`、`divergence[]`、`suggestions[]` |
| `done` | 全场结束 | `status: "finished"` |

事件帧格式：

```text
id: 12
event: token
data: {"room_id":1,"persona_id":3,"sequence_no":12,"speech_type":"counter","delta":"成本","token_index":0}
```

连接内置 `: connected` / `: ping` 注释帧用于握手与心跳保活；服务端每 15 秒无事件时主动心跳，客户端断开后自动释放订阅队列。

---

## 5. 已完成能力与演进方向

### 5.1 已完成

- **规范先行工程**：PRD、SQLite schema、Mermaid 架构图、REST/SSE 契约完整落盘
- **测试兜底**：调度器、洞察提炼器单元测试 + 系统级 E2E 测试，共 8 条断言全绿
- **非轮流加权调度**：立场冲突加权、冷静期衰减、主持人强制控场、发言长度校验
- **去 JSON 化清洗**：正则 + 解析器 + 降级容错，总结词 100% 纯自然语言，对白零控制字符，公开摘要 ≤ 15 字
- **多房间并发隔离**：`room_id` 维度独立队列与运行态，双房间并发事件零错配
- **5 组高质量预置数据**：覆盖科技伦理、商业战略、教育科技、劳动力市场、前沿哲学，一键灌库即可展示
- **往期演播厅**：5 场已结题讨论卡片化归档，支持只读回放完整对白、看板与总结，并可按原议题重新推演
- **真实大模型接入**：DeepSeek `deepseek-chat` 全量真实调用（阵容 / 交锋 / 洞察 / 总结），异常自动降级 Mock
- **演播厅前端**：三栏全屏布局、打字机、自动吸底、呼吸灯、看板平滑刷新、总结大卡片、回放/实时双模式

### 5.2 未来演进

- **语音合成（TTS）**：为每位角色绑定音色，把文字流转化为播音级双工对白，形成可听的圆桌节目
- **用户中途举手插话**：开放人类席位，支持在讨论进行中举手加入、补充观点或直接反驳某位专家
- 其他方向：讨论时间轴拖动、角色人格模板库、多模态议题材料（文档/图表）导入

---

## 6. 文档索引

| 文档 | 内容 |
| --- | --- |
| [docs/PRD.md](docs/PRD.md) | 产品需求、用户旅程与业务硬规则 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | ER 图与系统交互时序图 |
| [docs/API.md](docs/API.md) | REST 与 SSE 完整契约 |
| [docs/TESTING.md](docs/TESTING.md) | 测试分层、覆盖范围与运行指南 |
| [docs/WORKFLOW_REVIEW.md](docs/WORKFLOW_REVIEW.md) | 开发过程复盘与 AI 协同工作流 |
| [docs/PROMPT_LOG.md](docs/PROMPT_LOG.md) | 各阶段原始 Prompt 与设计意图记录 |
| [DELIVERY_CHECKLIST.md](DELIVERY_CHECKLIST.md) | 启动、验收与交付物对账手册 |
| [backend/schema.sql](backend/schema.sql) | SQLite 数据库基线脚本 |
