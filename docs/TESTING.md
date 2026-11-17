# 测试与质量指南 · TESTING

本文档描述 AI Panel Studio 的测试分层、覆盖范围、运行方式与质量门禁，供评审与本机复验使用。

| 项目 | 内容 |
| --- | --- |
| 测试框架 | pytest 9.x + pytest-asyncio（strict 模式） |
| 测试数量 | 8 条（单元 7 + 系统集成 1） |
| 全量耗时 | 约 5 秒（Mock 零延迟 + 临时数据库） |
| 外部依赖 | 无。不依赖真实大模型、网络或已有数据库 |

---

## 1. 环境准备

```powershell
# 在项目根目录执行
python -m venv backend/venv
backend\venv\Scripts\pip install -r backend/requirements.txt
```

测试配置位于 [backend/pytest.ini](../backend/pytest.ini)：

```ini
[pytest]
pythonpath = .
testpaths = tests
asyncio_default_fixture_loop_scope = function
addopts = -ra --strict-markers
```

要点：`pythonpath = .` 让 `app.*` 可直接导入；pytest-asyncio 处于 **strict** 模式，因此所有异步用例必须显式标注 `@pytest.mark.asyncio`。

---

## 2. 一条命令全量运行

```powershell
backend\venv\Scripts\pytest backend/tests -q
```

预期结果：

```text
........                                                                 [100%]
8 passed in ~5s
```

按需运行：

```powershell
# 只看调度器单元测试（TDD 阶段 A/B/C/D 四项）
backend\venv\Scripts\pytest backend/tests/test_scheduler.py -v

# 只看洞察提炼器
backend\venv\Scripts\pytest backend/tests/test_insight.py -v

# 只看系统级端到端
backend\venv\Scripts\pytest backend/tests/test_e2e.py -v

# 运行单条用例
backend\venv\Scripts\pytest backend/tests/test_e2e.py -k persistence -v
```

---

## 3. 测试分层与覆盖范围

### 3.1 单元测试：调度器 `tests/test_scheduler.py`（4 条）

被测对象：[backend/app/services/scheduler.py](../backend/app/services/scheduler.py)

| 用例 | 断言的核心契约 |
| --- | --- |
| `test_cooldown_forbids_same_expert_speaking_twice_in_a_row` | **防自言自语**：同一专家不能连续两次发言，冷却周期 ≥ 1 |
| `test_scheduler_rejects_mechanical_rotation` | **拒绝机械轮流**：逐一否定周期 1–10 的循环序列，校验 20 次调度中无重复块、单人占比受限，并要求出现基于立场冲突的动态加权分布 |
| `test_host_intervenes_after_consecutive_expert_exchanges` | **主持人控场**：专家连续交锋达到阈值（3–4 轮）后，下一位发言人必须被强制设为主持人 |
| `test_validated_speech_stays_within_one_or_two_sentences` | **发言长度硬约束**：通过 `validate_speech` 的文本必须为 1–2 句、20–80 字；越界文本抛出 `SpeechValidationError` |

### 3.2 单元测试：洞察提炼器 `tests/test_insight.py`（3 条）

被测对象：[backend/app/services/insight_extractor.py](../backend/app/services/insight_extractor.py)

模拟模型输出中刻意混入代码围栏、前后寒暄、Markdown 加粗标签、重复条目与超长文本：

| 用例 | 断言的核心契约 |
| --- | --- |
| `test_extractor_returns_structured_consensus_and_divergence` | 正确产出 `consensus` / `divergence` 两组列表；关键结论落入正确分组；条目去重；两组不串档；对白确实进入 Prompt |
| `test_extracted_items_are_clean_plain_text` | 每条均为纯文本：无 ` ``` `、`{}`、`**`、`consensus`、`<|` 等原始标记，无首尾空白，长度 ≤ 300 字 |
| `test_unparsable_model_output_raises_safe_error` | 无法解析时抛出 `InsightExtractionError`，且异常信息**不回显**模型原文 |

### 3.3 系统级集成测试 `tests/test_e2e.py`（1 条）

被测链路：真实 FastAPI 应用 + 临时 SQLite + Mock 流式大模型，使用 `httpx.AsyncClient` 与 `ASGITransport` 在进程内完成 HTTP 与 SSE 全链路，不启动端口。

```text
创建议题 → 校验 1 主持 + 4 专家契约 → 启动房间
        → 解析 SSE 六类事件帧 → 校验载荷与文本洁净度
        → 校验数据库最终持久化状态
```

具体断言：

1. **阵容契约**：`POST /api/rooms` 返回 5 位角色；有且仅有 1 位 `is_host`；色标全部匹配 `^#[0-9A-Fa-f]{6}$` 且互不重复；`current_focus ≤ 15` 字。
2. **SSE 帧格式**：`token`、`status_change`、`insight_update`、`speech_end`、`summary`、`done` 六类事件全部出现；每个 `data` 均可被 `json.loads` 解析，且不含替换字符 `\ufffd`（乱码）。
3. **内容洁净度**：`token` / `speech_end` 不含 `[举手]`、`[反驳]`、`系统通知`；`summary.summary` 不含 `{`、`}`、` ``` `、`"summary"` 等 JSON 残留，并以句末标点收束； `status_change.current_focus` ≤ 15 字。
4. **数据库终态**：房间 `status=finished` 且 `summary`、`finished_at` 非空；速记条数 ≥ 9、序号连续唯一、最后一条为 `summary`；看板版本 ≥ 1 且条目类型合法、长度 ≤ 300。

测试隔离手段：

- `monkeypatch` 将 `database.DATA_DIR` / `DATABASE_PATH` 指向 `tmp_path`，并重置初始化锁；
- 将两处 `MOCK_TOKEN_DELAY` 置零，整条链路约 4–5 秒完成；
- `ASGITransport` 不执行 lifespan，测试内显式调用 `database.init_db()`。

---

## 4. 验收标准与测试映射

| 验收标准 | 对应测试 |
| --- | --- |
| 1 主持 + 4 专家、色标唯一 | `test_e2e_round_table_stream_and_persistence` |
| 非机械轮流、立场加权 | `test_scheduler_rejects_mechanical_rotation` |
| 单次发言 1–2 句、20–80 字 | `test_validated_speech_stays_within_one_or_two_sentences` |
| 主持人控场介入 | `test_host_intervenes_after_consecutive_expert_exchanges` |
| 共识 / 分歧结构化且纯文本 | `test_extractor_returns_structured_consensus_and_divergence`、`test_extracted_items_are_clean_plain_text` |
| 解析失败不回显模型原文 | `test_unparsable_model_output_raises_safe_error` |
| SSE 六类事件无乱码、无 JSON 泄露 | `test_e2e_round_table_stream_and_persistence` |
| 数据库最终状态正确持久化 | `test_e2e_round_table_stream_and_persistence` |

---

## 5. 测试设计原则

1. **只断言契约，不绑定实现**：测试关注「冷却、非周期、控场、长度、洁净度」等可观察行为，允许后续重构调度算法而不改测试。
2. **红灯先行**：`test_scheduler.py` 与 `test_insight.py` 在零实现状态下编写，先全红再实现至全绿，避免「先写代码再补测试」。
3. **安全异常可验证**：清洗失败路径同样纳入断言，异常信息不得回显模型原文，防止敏感/脏数据通过报错泄露。
4. **系统测试贴近真实链路**：E2E 使用真实路由、真实数据库访问层与真实 SSE 解析，而非直接调用服务函数。

---

## 6. 质量门禁与常见问题

**门禁**：提交前 `pytest backend/tests -q` 必须退出码为 0 且输出 `8 passed`。

| 现象 | 原因与处理 |
| --- | --- |
| `ModuleNotFoundError: No module named 'app'` | 未从项目根目录运行，或未使用带 `pythonpath = .` 的 pytest.ini；请在根目录执行上述命令 |
| 异步用例被跳过或报 strict 错误 | 缺少 `@pytest.mark.asyncio`；本项目 strict 模式要求显式标注 |
| `database is locked` | 测试使用独立临时库，正常不会发生；若手工并发运行 seed 与后端，等待写事务结束后重试 |
| `LF will be replaced by CRLF` | Windows 下 Git 行尾提示，不影响测试与运行 |
