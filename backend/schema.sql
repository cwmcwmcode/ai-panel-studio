-- =============================================================================
-- AI Panel Studio · SQLite 数据库定义脚本
-- 版本: v1.0
-- 方言: SQLite 3 (>= 3.35.0，依赖 STRICT 语义的可选项在下方注释说明)
-- 说明: 本脚本为一期 MVP 的完整数据库基线，可重复执行（幂等）。
-- 关联: docs/PRD.md · docs/ARCHITECTURE.md · docs/API.md
-- 存放: backend/data/panel_studio.db
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- -----------------------------------------------------------------------------
-- 0. 清理（仅开发期重建使用，生产迁移请勿直接执行本节）
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS insights;
DROP TABLE IF EXISTS transcripts;
DROP TABLE IF EXISTS personas;
DROP TABLE IF EXISTS rooms;

-- -----------------------------------------------------------------------------
-- 1. rooms · 讨论房间表（聚合根）
--    状态机: draft -> active -> finished（单向，不可回退）
-- -----------------------------------------------------------------------------
CREATE TABLE rooms (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    topic         TEXT    NOT NULL
                          CHECK (length(trim(topic)) BETWEEN 1 AND 200),
    status        TEXT    NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft', 'active', 'finished')),
    expert_count  INTEGER NOT NULL DEFAULT 4
                          CHECK (expert_count BETWEEN 1 AND 8),
    summary       TEXT    NULL,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    finished_at   TEXT    NULL,

    -- 业务约束：房间结束必须同时具备结束时间与总结内容
    CHECK (status <> 'finished' OR (finished_at IS NOT NULL AND summary IS NOT NULL)),
    -- 业务约束：未结束的房间不得存在结束时间
    CHECK (status =  'finished' OR finished_at IS NULL)
);

-- 历史列表：按创建时间倒序分页
CREATE INDEX idx_rooms_created_at ON rooms (created_at DESC);
-- 状态筛选（活跃房间扫描）
CREATE INDEX idx_rooms_status     ON rooms (status);

-- -----------------------------------------------------------------------------
-- 2. personas · 角色表（主持人 + 专家）
--    is_host = 1 有且仅有一位（由下方部分唯一索引保证）
--    color_theme 必须为 6 位十六进制色值，如 #E4572E
-- -----------------------------------------------------------------------------
CREATE TABLE personas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id         INTEGER NOT NULL,
    name            TEXT    NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 40),
    title           TEXT    NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 60),
    stance          TEXT    NOT NULL CHECK (length(trim(stance)) BETWEEN 1 AND 200),
    color_theme     TEXT    NOT NULL
                            CHECK (color_theme GLOB '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]'),
    is_host         INTEGER NOT NULL DEFAULT 0 CHECK (is_host IN (0, 1)),
    current_status  TEXT    NOT NULL DEFAULT 'idle'
                            CHECK (current_status IN ('idle', 'thinking', 'speaking')),
    current_focus   TEXT    NULL CHECK (current_focus IS NULL OR length(current_focus) <= 120),
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (room_id) REFERENCES rooms (id) ON DELETE CASCADE
);

-- 房间 → 角色 的批量读取
CREATE INDEX idx_personas_room          ON personas (room_id);
-- 房间内色标唯一，保证大屏视觉可区分
CREATE UNIQUE INDEX uq_personas_room_color ON personas (room_id, color_theme);
-- 每个房间只允许一位主持人（SQLite 部分索引）
CREATE UNIQUE INDEX uq_personas_room_host  ON personas (room_id) WHERE is_host = 1;

-- -----------------------------------------------------------------------------
-- 3. transcripts · 现场实时速记表
--    sequence_no 在房间内严格单调递增且唯一，保证回放顺序确定
--    speech_type: intro(开场) / speech(陈述) / counter(交锋) / summary(总结)
-- -----------------------------------------------------------------------------
CREATE TABLE transcripts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id      INTEGER NOT NULL,
    persona_id   INTEGER NOT NULL,
    sequence_no  INTEGER NOT NULL CHECK (sequence_no > 0),
    content      TEXT    NOT NULL
                         CHECK (content IS NOT NULL AND length(trim(content)) > 0),
    speech_type  TEXT    NOT NULL
                         CHECK (speech_type IN ('intro', 'speech', 'counter', 'summary')),
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (room_id)    REFERENCES rooms (id)    ON DELETE CASCADE,
    FOREIGN KEY (persona_id) REFERENCES personas (id) ON DELETE CASCADE,

    -- 同一房间内序号唯一，杜绝并发写入造成顺序歧义
    CONSTRAINT uq_transcripts_room_seq UNIQUE (room_id, sequence_no)
);

-- 回放主查询：按房间取全部速记并有序返回
CREATE INDEX idx_transcripts_room_seq ON transcripts (room_id, sequence_no ASC);
-- 按角色检索（统计发言分布 / 均衡校验）
CREATE INDEX idx_transcripts_persona  ON transcripts (persona_id);

-- -----------------------------------------------------------------------------
-- 4. insights · 共识与分歧看板表
--    type: consensus(共识) / divergence(分歧)
--    version 为「房间级看板版本号」，从 1 开始单调递增；同一次刷新写入的多条
--    条目共享同一 version，形成该时刻的完整看板快照，历史版本保留可追溯。
-- -----------------------------------------------------------------------------
CREATE TABLE insights (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id     INTEGER NOT NULL,
    type        TEXT    NOT NULL CHECK (type IN ('consensus', 'divergence')),
    content     TEXT    NOT NULL CHECK (length(trim(content)) BETWEEN 1 AND 300),
    version     INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (room_id) REFERENCES rooms (id) ON DELETE CASCADE
);

-- 看板读取：按房间取最新版本
CREATE INDEX idx_insights_room_type ON insights (room_id, type, version DESC);
CREATE INDEX idx_insights_room       ON insights (room_id);
