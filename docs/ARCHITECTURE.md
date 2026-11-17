# AI Panel Studio 架构设计文档

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v1.0 |
| 适用范围 | MVP 一期（单机房单体部署） |
| 技术栈 | Python 3.11 + FastAPI · SQLite（WAL）· Vue 3 + Vite · SSE |
| 关联文档 | [PRD.md](./PRD.md) · [API.md](./API.md) · [schema.sql](../backend/schema.sql) |

---

## 1. 架构目标与设计原则

| 目标 | 说明 |
| --- | --- |
| 职责单一 | 生成、调度、渲染、持久化四类关注点物理分离，互不越界 |
| 契约先行 | 前后端仅通过 [API.md](./API.md) 定义的领域契约通信，禁止透传模型结构 |
| 单向数据流 | 后端是唯一事实源，前端只做投影与渲染 |
| 可观测 | 房间、状态、发言、洞察全部落库，任意时刻可重放 |
| 渐进演进 | 一期单进程即可运行，后续可将调度器与 LLM 调用拆为独立 Worker |

**架构红线（对应 PRD 硬规则）**

1. 任何 LLM 原始输出在进入 SSE 通道前必须完成解析、校验、领域映射（HR-4）。
2. 调度器日志、思维链、内部打分只写本地日志，永不进入出站载荷（HR-3）。
3. 发言长度在「入库前」校验与截断，而非在渲染时（HR-1）。

---

## 2. 系统分层

```mermaid
flowchart TB
    subgraph FE["前端 · Vue 3 (frontend/)"]
        A1["议题输入视图"]
        A2["阵容确认视图"]
        A3["演播厅大屏视图"]
        A4["共识分歧看板组件"]
        A5["历史回看视图"]
        A6["SSE 客户端<br/>EventSource · 断线重连"]
    end

    subgraph BE["后端 · FastAPI (backend/)"]
        B1["REST 路由层<br/>/api/rooms"]
        B2["SSE 事件网关<br/>/api/rooms/{id}/events"]
        B3["房间状态机服务"]
        B4["阵容生成器<br/>Persona Generator"]
        B5["发言调度器<br/>Scheduler（竞争式）"]
        B6["发言编排器<br/>Turn Orchestrator"]
        B7["洞察抽取器<br/>Insight Extractor"]
        B8["契约层<br/>Pydantic 领域模型"]
    end

    subgraph CORE["基础设施"]
        C1[("SQLite · WAL<br/>backend/data/panel_studio.db")]
        C2["LLM Provider<br/>（文本流式）"]
        C3["进程内事件总线<br/>asyncio.Queue"]
    end

    A1 --> B1
    A2 --> B1
    A3 --> A6
    A5 --> B1
    A6 <--> B2

    B1 --> B3
    B3 --> B4
    B4 --> C2
    B2 --> C3
    B3 --> B5
    B5 --> B6
    B6 --> C2
    B6 --> B7
    B6 --> B8
    B7 --> B8
    B8 --> C1
    B6 --> C3
    C3 --> B2
```

**分层说明**

| 层 | 组成 | 职责 | 禁止事项 |
| --- | --- | --- | --- |
| 表现层 | Vue 3 视图与组件 | 渲染、交互、SSE 消费 | 不得解析模型 JSON、不得持有 CoT |
| 接入层 | FastAPI 路由 / SSE 网关 | 鉴权占位、参数校验、协议转换 | 不得包含业务规则 |
| 领域层 | 状态机 / 调度器 / 编排器 / 抽取器 | 硬规则执行、发言决策、洞察归并 | 不得直接操作 HTTP 上下文 |
| 适配层 | LLM Provider / 仓储 Repository | 外部依赖隔离、SQL 封装 | 不得向上抛出原始响应 |
| 存储层 | SQLite（WAL 模式） | 单一事实源 | 不得绕过仓储层写入 |

---

## 3. 核心模块职责

| 模块 | 输入 | 输出 | 关键约束 |
| --- | --- | --- | --- |
| 房间状态机服务 | 创建 / 确认 / 结束指令 | 状态迁移结果 | 仅允许 draft→active→finished |
| 阵容生成器 | 议题 + 风格 | 1 主持 + 4 专家 | 立场需构成光谱；色标房间内唯一 |
| 发言调度器 | 速记尾部 + 各专家状态 | 下一位发言人及意图 | 非机械轮流：冷却 + 冲突度择优 + 均衡 |
| 发言编排器 | 发言人 + 意图 + 上下文 | token 流 → 完整发言 | 1–2 句、≤ 80 字；超限截断 |
| 洞察抽取器 | 最近 N 轮速记 | 共识/分歧条目 + 新版本 | 版本号房间内单调递增 |
| SSE 事件网关 | 进程内事件总线 | 标准 5 类事件 | 心跳保活、Last-Event-ID 续传 |

---

## 4. 数据实体关系（ER 图）

```mermaid
erDiagram
    ROOMS ||--o{ PERSONAS : "拥有 1 主持 + N 专家"
    ROOMS ||--o{ TRANSCRIPTS : "包含全部速记"
    ROOMS ||--o{ INSIGHTS : "沉淀共识与分歧"
    PERSONAS ||--o{ TRANSCRIPTS : "产出单条发言"

    ROOMS {
        INTEGER id PK "自增主键"
        TEXT topic "议题，1-200 字"
        TEXT status "draft / active / finished"
        INTEGER expert_count "专家数量，默认 4"
        TEXT summary "主持人总结"
        TEXT created_at "ISO8601 UTC"
        TEXT finished_at "结束时间"
    }

    PERSONAS {
        INTEGER id PK "自增主键"
        INTEGER room_id FK "所属房间"
        TEXT name "姓名"
        TEXT title "头衔"
        TEXT stance "核心立场"
        TEXT color_theme "专属色标 #RRGGBB"
        INTEGER is_host "1=主持人"
        TEXT current_status "idle / thinking / speaking"
        TEXT current_focus "当前关注点"
    }

    TRANSCRIPTS {
        INTEGER id PK "自增主键"
        INTEGER room_id FK "所属房间"
        INTEGER persona_id FK "发言人"
        INTEGER sequence_no "房间内单调递增"
        TEXT content "发言正文"
        TEXT speech_type "intro / speech / counter / summary"
        TEXT created_at "ISO8601 UTC"
    }

    INSIGHTS {
        INTEGER id PK "自增主键"
        INTEGER room_id FK "所属房间"
        TEXT type "consensus / divergence"
        TEXT content "洞察内容"
        INTEGER version "房间级看板版本"
        TEXT created_at "ISO8601 UTC"
    }
```

**关系说明**

| 关系 | 基数 | 约束 |
| --- | --- | --- |
| rooms → personas | 1 : N（N = expert_count + 1） | 级联删除；每房间仅 1 位 is_host=1 |
| rooms → transcripts | 1 : N | 级联删除；(room_id, sequence_no) 唯一 |
| rooms → insights | 1 : N | 级联删除；version 房间内递增 |
| personas → transcripts | 1 : N | 级联删除；发言必须归属本房间角色 |

> 数据完整性由数据库约束（CHECK / UNIQUE / FOREIGN KEY）兜底，应用层做语义校验，形成双重防护。

---

## 5. 系统交互时序（发起议题 → 总结收束）

```mermaid
sequenceDiagram
    autonumber
    actor U as 用户
    participant FE as 前端 Vue 3
    participant API as FastAPI REST
    participant SM as 房间状态机
    participant GEN as 阵容生成器
    participant LLC as LLM Provider
    participant DB as SQLite
    participant SSE as SSE 网关
    participant SCH as 发言调度器
    participant ORC as 发言编排器
    participant INS as 洞察抽取器

    Note over U,DB: 阶段一 · 议题输入与阵容生成
    U->>FE: 输入议题并提交
    FE->>API: POST /api/rooms {topic}
    API->>SM: 创建房间
    SM->>DB: INSERT rooms (status=draft)
    SM-->>API: room_id
    API->>GEN: 基于议题生成阵容
    GEN->>LLC: 请求 1 主持 + 4 专家定义
    LLC-->>GEN: 结构化角色提案
    GEN->>GEN: 校验立场光谱 / 色标唯一 / 字段完整性
    GEN->>DB: INSERT personas × 5
    API-->>FE: 201 {room_id, personas[]}
    FE-->>U: 渲染阵容确认页

    Note over U,DB: 阶段二 · 确认进入演播厅
    U->>FE: 点击「进入演播厅」
    FE->>API: POST /api/rooms/{id}/activate
    API->>SM: 执行 draft → active
    SM->>DB: UPDATE rooms SET status='active'
    API-->>FE: 200 {status:'active'}
    FE->>SSE: GET /api/rooms/{id}/events (EventSource)
    SSE->>DB: 校验房间为 active，读取已有最大 sequence_no
    SSE-->>FE: 200 text/event-stream · 建立长连接
    SSE->>ORC: 触发讨论启动（仅首次连接）
    ORC->>SSE: event: status_change（主持人 thinking）
    SSE-->>FE: 推送事件
    ORC->>LLC: 生成主持人开场
    loop 逐 token
        ORC->>SSE: event: token
        SSE-->>FE: 打字机渲染
    end
    ORC->>DB: INSERT transcripts (speech_type='intro')
    ORC->>SSE: event: speech_end
    ORC->>INS: 抽取首轮洞察
    INS->>DB: INSERT insights (version=1)
    INS->>SSE: event: insight_update

    Note over SCH,DB: 阶段三 · 竞争式发言循环（非机械轮流）
    loop 直到达到收敛条件
        SCH->>DB: 读取速记尾部 + 发言分布 + 冷却表
        SCH->>SCH: 打分 = 话题相关性 × 立场冲突度 × 均衡因子<br/>过滤冷却未到期者
        SCH-->>ORC: 选定发言人与意图（speech / counter）
        ORC->>SSE: event: status_change（选中者 thinking，其余保持）
        ORC->>LLC: 带上下文生成 1-2 句发言
        loop 逐 token
            ORC->>SSE: event: token
        end
        ORC->>ORC: 长度与句数校验（≤80 字），超限截断
        ORC->>DB: INSERT transcripts (sequence_no+1)
        ORC->>SSE: event: speech_end
        ORC->>INS: 增量更新洞察
        INS->>DB: INSERT insights (version+1)
        INS->>SSE: event: insight_update
    end

    Note over ORC,SSE: 阶段四 · 主持人总结与收束
    ORC->>SCH: 判定自然收敛
    SCH-->>ORC: 指派主持人输出总结
    ORC->>SSE: event: status_change（主持人 thinking）
    ORC->>LLC: 请求总结（共识 / 分歧 / 建议）
    loop 逐 token
        ORC->>SSE: event: token
    end
    ORC->>DB: INSERT transcripts (speech_type='summary')
    ORC->>DB: UPDATE rooms SET status='finished', summary=?, finished_at=?
    ORC->>SSE: event: summary（终结载荷）
    SSE-->>FE: 关闭事件流
    FE-->>U: 展示总结卡片，进入可回看状态
```

---

## 6. 关键机制设计

### 6.1 竞争式发言调度（对应 HR-2）

每次派发前计算候选分数，取 Top-1：

```
score(p) = w1 · relevance(p, recent_context)
         + w2 · conflict(p.stance, last_speaker.stance)
         + w3 · balance(1 - p.speak_count / total_speaks)
         - w4 · cooldown_penalty(p)
```

| 约束 | 实现方式 | 否决条件 |
| --- | --- | --- |
| 冷却 | 记录每位专家上次发言的 sequence_no | 间隔 < 1 次他人发言则剔除 |
| 冲突度 | 立场向量/标签化对立关系 | 连续两次同立场者不成对出现 |
| 均衡 | 实时统计发言占比 | 某人占比 > 40% 时大幅降权 |
| 防死循环 | 单场上限（≤ 20 轮） | 达上限强制进入总结 |

### 6.2 流式发言与长度硬约束（对应 HR-1 / HR-4）

1. LLM 以流式返回**纯文本片段**，经编排器聚合缓冲区。
2. 缓冲区按句末标点切分句数；超过 2 句或 80 字时立即截断并终止后续生成。
3. 仅将校验后的 `content` 落库，再向 SSE 推送 `speech_end`。
4. 任何模型原始 JSON 在解析后即丢弃，仅保留领域字段。

### 6.3 SSE 通道设计（对应 HR-3）

- 单房间单通道，事件类型固定 5 种（见 [API.md](./API.md)）。
- 心跳：每 15s 发送注释行 `: ping`，防止代理层超时断链。
- 续传：客户端携带 `Last-Event-ID`，服务端从该 `sequence_no` 之后补发。
- 背压：进程内 `asyncio.Queue` 有界（如 256），溢出时丢弃最旧的 token 事件并补发 `speech_end`，保证终态一致。

### 6.4 洞察版本管理

- `version` 为房间级看板版本，每次刷新 +1，同批写入的多条条目共享该版本。
- 前端按最大 version 渲染当前看板，历史版本可用于「观点演化」回放。

---

## 7. 目录与部署形态

```
D:\ai-panel-studio\
├── docs/
│   ├── PRD.md              # 产品需求
│   ├── ARCHITECTURE.md     # 架构设计（本文）
│   └── API.md              # REST + SSE 契约
├── backend/
│   ├── data/               # SQLite 数据文件目录
│   │   └── panel_studio.db # 运行时生成
│   └── schema.sql          # 数据库基线脚本
└── frontend/               # Vue 3 应用
```

**一期部署**：单机单进程，FastAPI 同时承载 REST 与 SSE；SQLite 开启 WAL 以支持「写发言 + 读回放」并发。

**演进路径**

| 阶段 | 变化点 |
| --- | --- |
| 二期 | 调度器与 LLM 调用拆为独立 Worker，事件总线换 Redis Pub/Sub |
| 三期 | SQLite → PostgreSQL；新增用户体系与房间权限 |
| 四期 | 引入向量检索做立场相关性打分；支持语音与数字人渲染 |

---

## 8. 非功能设计对照

| 需求（PRD §5） | 架构手段 |
| --- | --- |
| TTFT ≤ 3s | 开场发言与连接建立并行触发；LLM 流式直出 |
| 断线零丢失 | `Last-Event-ID` + 速记全量落库 |
| 状态一致 | 数据库约束 + 状态机服务单点收口 |
| 敏感信息不泄漏 | 出站 DTO 白名单构造，禁止模型对象直传 |
| 单场 ≤ 20 轮 | 调度器轮次预算与收敛判定 |

---

## 9. 架构决策记录（ADR 摘要）

| 编号 | 决策 | 备选方案 | 结论与理由 |
| --- | --- | --- | --- |
| ADR-001 | SSE 而非 WebSocket | WebSocket | 讨论为服务端单向推送，SSE 更简单、天然支持断点续传与 HTTP 生态 |
| ADR-002 | SQLite + WAL | PostgreSQL | MVP 单机、零运维；WAL 满足读写并发；后续平滑迁移 |
| ADR-003 | 进程内事件总线 | 消息队列 | 一期单进程，避免过度设计；接口抽象保留替换空间 |
| ADR-004 | 后端硬截断发言 | 前端截断 | 事实源必须是干净的，避免脏数据入库与回放不一致 |
| ADR-005 | 版本化洞察快照 | 原地更新 | 保留演化过程，支撑「观点如何形成」的可解释性 |
