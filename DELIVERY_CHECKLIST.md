# 项目全功能验收与交付对账手册

| 项目 | 内容 |
| --- | --- |
| 工程目录 | `D:\ai-panel-studio` |
| 对账基线 | `main` 最新提交（核心修复提交 `867b673`） |
| 更新时间 | 2026-11-19 |
| 验收环境 | Windows / PowerShell 5 / Python venv / Node.js |
| 实测结论 | 后端测试 `8 passed`；前端构建通过；5 场样例完整；真实 DeepSeek 调用返回 HTTP 200 |

---

## 一、本地启动与验收

### 1.1 后端（FastAPI + SQLite）

在项目根目录执行：

```powershell
# ① 幂等灌入 5 场样例（已存在则跳过）
backend\venv\Scripts\python backend/scripts/seed_data.py

# ② 启动 API（--app-dir 指定包根，无需切换目录）
backend\venv\Scripts\python -m uvicorn app.main:app --app-dir backend --port 8000 --reload
```

| 入口 | 地址 |
| --- | --- |
| 健康检查 | `http://127.0.0.1:8000/health` |
| Swagger | `http://127.0.0.1:8000/docs` |
| 房间列表 | `http://127.0.0.1:8000/api/rooms` |

`backend\.env` 已配置真实 `LLM_API_KEY`，启动日志会输出：

```text
已启用真实大模型调用：deepseek-chat @ https://api.deepseek.com
```

### 1.2 前端（Vue 3 + Vite）

另开一个 PowerShell：

```powershell
cd D:\ai-panel-studio\frontend
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`，Vite 已将 `/api` 代理到 8000 端口。

### 1.3 核心验收路径

1. **往期演播厅**：点击顶栏「往期演播厅」→ 抽屉展示 5 张「已结题」卡片（议题、专家人数、完成时间）。
2. **只读回放**：点击任意卡片 → 顶栏显示「只读回放」，速记区显示 `REPLAY`；可查看完整对白、专家小窗、共识/分歧看板与主持人总结词。
3. **克隆重演**：在回放页点击「基于此议题重新推演」→ 生成新阵容并进入 `LIVE` 实时讨论。
4. **新讨论**：点击「发起新讨论」→ 输入议题 → 选择 3/4/5 位专家 → 生成阵容 → 确认进入演播厅。
5. **实时表现**：专家呼吸灯按 `idle → thinking → speaking` 切换；对白逐字输出；看板每 3 次发言刷新；顶栏可提前收束。
6. **总结与沉淀**：总结卡片展示纯自然语言陈词、共识、分歧与建议；结束后的新房间会出现在往期列表。

### 1.4 无有效 Key 时的演示保障

当 `LLM_API_KEY` 为空、仍为占位符，或真实调用异常时：

- `config.py` 自动置 `DEMO_MODE = True`，创建房间返回 `meta.degraded = true`；
- 阵容、发言、洞察与总结全部由内置 Mock 生成，仍走同一套 SSE 六类事件；
- 前端打字机、状态灯、看板与总结卡片表现与真实模型一致，离线也能完整演示。

---

## 二、交付物逐一核对

| 作业要求 | 对应文件 / 目录 | 核对结论 |
| --- | --- | --- |
| 后端完整源码 | `backend/app/`（main、config、api、db、services、utils） | 齐全 |
| 前端完整源码 | `frontend/src/`（App、api、stores、7 个组件） | 齐全 |
| 工程配置 | `backend/requirements.txt`、`backend/pytest.ini`、`frontend/package.json`、`vite.config.js`、`tailwind.config.js` | 齐全 |
| SQLite 脚本 | `backend/schema.sql` | 启动时自动建表 |
| 5 组样例数据 | `backend/scripts/seed_data.py`、`backend/data/panel_studio.db` | 5 房间 × 5 角色 × 10 速记 × 4 看板 |
| PRD | `docs/PRD.md` | 价值主张、用户旅程、业务硬规则 |
| Mermaid ER 图 | `docs/ARCHITECTURE.md` | 架构图、ER 图、时序图齐全 |
| API 文档 | `docs/API.md` | REST 与 SSE 六类事件契约 |
| 测试文档 | `docs/TESTING.md` | 分层覆盖、一键运行、手动验收清单 |
| README | `README.md` | 定位、选型、启动、API、能力与演进 |
| Prompt 记录 | `docs/PROMPT_LOG.md` | 覆盖 SDD / TDD / DDD / Integration / E2E 五阶段 |
| 工作流说明 | `docs/WORKFLOW_REVIEW.md` | 约 1567 汉字，三大模块 + 三个冲突案例 |
| 交付对账 | `DELIVERY_CHECKLIST.md` | 本文件 |

---

## 三、质量实测

| 检查项 | 命令 / 方式 | 结果 |
| --- | --- | --- |
| 单元与 E2E 测试 | `backend\venv\Scripts\pytest backend\tests -q` | `8 passed` |
| 前端构建 | `npm --prefix frontend run build` | 成功 |
| 历史列表与回放 | 浏览器点击「往期演播厅」→ 首张卡片 | 5 张卡片、11 条速记、共识/分歧面板均正常 |
| 真实 DeepSeek | 后端日志 | `POST https://api.deepseek.com/chat/completions "HTTP/1.1 200 OK"` |
| 数据结构 | `GET /api/rooms/{id}` | 返回 `room / personas / transcripts / insights / progress` |

---

## 四、四个差异的修复复核

| 原差异 | 修复内容 | 复核结果 |
| --- | --- | --- |
| 1. 前端缺少历史讨论入口 | 新增「往期演播厅」抽屉，调用 `GET /api/rooms` 展示 5 场已结题卡片 | 已解决 |
| 2. 历史房间无法回放 | 房间详情新增 `transcripts`，前端提供 `REPLAY` 只读回放与「查看总结词」 | 已解决 |
| 3. 工作流文档篇幅超限 | `docs/WORKFLOW_REVIEW.md` 由 1843 字精简至 1567 字（约 -15%） | 已解决 |
| 4. 仅有 Mock，未接真实模型 | 默认 DeepSeek 配置，真实调用全链路验证 HTTP 200，异常自动降级 | 已解决 |

---

## 五、Git 提交历史

```text
867b673 feat(ui): add history discussion list, support replay mode and integrate deepseek api
fb07ef0 docs: finalize readme, testing guide and workflow review for submission
7b5eae9 e2e: add system e2e test, sanitize llm outputs and seed 5 sample roundtable datasets
863b29e feat(api): implement sse streaming pipeline, room concurrency isolation and live typewriter render
20d1963 chore: add comprehensive .gitignore and track pytest.ini for clean clone reproducibility
432c0ba ui-components: implement studio dashboard layout, live transcript and persona widgets
84dd7a3 tests: add unit tests and implement agent speech scheduler and consensus extractor
3c9a25e docs/schema: init prd, sqlite schema, mermaid architecture and sse protocol
```

完整呈现 `docs/schema → tests → ui-components → feat → e2e → docs → 历史回放/真实模型` 的分层递进轨迹。

---

## 六、交付说明

- `backend/.env` 含真实 Key，已被 `.gitignore` 排除，不会进入 Git 与交付压缩包；压缩包仅含 `.env.example`。
- `backend/data/panel_studio.db` 为本地运行数据，可通过 `seed_data.py` 幂等重建。
- 真实 Key 需配合有效余额；若调用失败，系统自动降级 Mock，不影响验收流程。
- 任何前端改动后建议同时执行 `pytest` 与 `npm run build` 两项门禁。
