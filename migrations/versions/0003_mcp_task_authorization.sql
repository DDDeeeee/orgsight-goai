-- GOAI MCP 只读服务的 Worker 身份映射与 Task 授权范围。
-- 该表属于 OrgSight；不保存 AgentTeams 的 Task/Room runtime 数据。

BEGIN;

-- 存储的是 Bearer 凭证的 SHA-256，不保存明文凭证。
-- 部署接入时由受控运维流程写入与 AgentTeams Worker 对应的凭证哈希。
CREATE TABLE IF NOT EXISTS mcp_worker_credentials (
    credential_id TEXT PRIMARY KEY,
    worker_id TEXT NOT NULL UNIQUE,
    token_sha256 TEXT NOT NULL UNIQUE CHECK (token_sha256 ~ '^[0-9a-f]{64}$'),
    status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 一条 Grant 只授权一个已分派的 Worker 在一个冻结的组织快照范围内读取资料。
-- Task 本体仍由 AgentTeams 保存；这里仅保存 GOAI 进行权限判断所需的最小投影。
CREATE TABLE IF NOT EXISTS mcp_task_grants (
    task_id TEXT PRIMARY KEY,
    worker_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    -- 仅记录 AgentTeams Task 的自然语言业务目标，不参与授权判断。
    purpose TEXT NOT NULL,
    allowed_tools JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_person_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_unit_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_project_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL CHECK (status IN ('active', 'revoked', 'expired', 'completed')),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(allowed_tools) = 'array'),
    CHECK (jsonb_typeof(allowed_person_ids) = 'array'),
    CHECK (jsonb_typeof(allowed_unit_ids) = 'array'),
    CHECK (jsonb_typeof(allowed_project_ids) = 'array'),
    CHECK (NOT jsonb_path_exists(allowed_tools, '$[*] ? (@.type() != "string")')),
    CHECK (NOT jsonb_path_exists(allowed_person_ids, '$[*] ? (@.type() != "string")')),
    CHECK (NOT jsonb_path_exists(allowed_unit_ids, '$[*] ? (@.type() != "string")')),
    CHECK (NOT jsonb_path_exists(allowed_project_ids, '$[*] ? (@.type() != "string")')),
    FOREIGN KEY (organization_id, snapshot_date)
        REFERENCES organization_snapshots (organization_id, snapshot_date)
        ON DELETE RESTRICT,
    FOREIGN KEY (worker_id)
        REFERENCES mcp_worker_credentials (worker_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_mcp_task_grants_worker
    ON mcp_task_grants (worker_id, status);

INSERT INTO schema_migrations (version)
VALUES ('0003_mcp_task_authorization')
ON CONFLICT (version) DO NOTHING;

COMMIT;
