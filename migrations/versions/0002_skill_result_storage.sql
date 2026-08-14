-- GOAI Skill 结果、冻结输入与可读投影的持久化契约。
-- 此 migration 只定义未来运行的结果存储，不将当前预制模型或关系伪造为 Skill 执行结果。
-- 所有表仅面向 profilemesh_goai_demo；不包含 AgentTeams runtime 状态。

BEGIN;

CREATE TABLE IF NOT EXISTS skill_input_manifests (
    input_manifest_id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    request_input JSONB,
    request_input_sha256 TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, snapshot_date)
        REFERENCES organization_snapshots (organization_id, snapshot_date)
        ON DELETE RESTRICT,
    CHECK (
        (request_input IS NULL AND request_input_sha256 IS NULL)
        OR (request_input IS NOT NULL AND request_input_sha256 ~ '^[0-9a-f]{64}$')
    )
);

-- 原始组织数据的冻结引用。具体 ref_type 的解析由 GOAI 运行宿主负责，
-- 以便同一张表能够引用档案、人物模型、关系快照和未来项目材料。
CREATE TABLE IF NOT EXISTS skill_input_raw_references (
    input_manifest_id TEXT NOT NULL,
    reference_index INTEGER NOT NULL CHECK (reference_index >= 1),
    ref_type TEXT NOT NULL CHECK (ref_type IN (
        'organization_snapshot',
        'organization_unit',
        'person_profile',
        'person_model',
        'relationship_snapshot',
        'project_material',
        'project_state_snapshot'
    )),
    ref_id TEXT NOT NULL,
    ref_version TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (input_manifest_id, reference_index),
    FOREIGN KEY (input_manifest_id)
        REFERENCES skill_input_manifests (input_manifest_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS skill_results (
    result_id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL CHECK (skill_name IN (
        'modeling-roles',
        'modeling-collaboration-relationships',
        'modeling-project-state',
        'assessing-team-role-ecology',
        'assessing-team-health',
        'diagnosing-collaboration-structure',
        'analyzing-project-collaboration-risk',
        'designing-intervention-options',
        'simulating-team-interactions'
    )),
    result_type TEXT NOT NULL CHECK (result_type IN (
        'person_role_model',
        'collaboration_relationship_snapshot',
        'project_state_snapshot',
        'team_role_ecology_assessment',
        'team_health_assessment',
        'collaboration_structure_diagnosis',
        'project_collaboration_risk_analysis',
        'intervention_option_design',
        'team_interaction_simulation'
    )),
    subject_type TEXT NOT NULL CHECK (subject_type IN (
        'person',
        'organization_scope',
        'project',
        'management_request',
        'simulation'
    )),
    subject_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version >= 1),
    input_manifest_id TEXT NOT NULL,
    output_json JSONB NOT NULL,
    confidence NUMERIC(4, 3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status TEXT NOT NULL CHECK (status IN (
        'pending_validation',
        'accepted',
        'rejected',
        'superseded',
        'archived'
    )),
    supersedes_result_id TEXT,
    model_document_id TEXT UNIQUE,
    producer_trace_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    accepted_at TIMESTAMPTZ,
    FOREIGN KEY (organization_id, snapshot_date)
        REFERENCES organization_snapshots (organization_id, snapshot_date)
        ON DELETE RESTRICT,
    FOREIGN KEY (input_manifest_id)
        REFERENCES skill_input_manifests (input_manifest_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (supersedes_result_id)
        REFERENCES skill_results (result_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (model_document_id)
        REFERENCES model_documents (model_document_id)
        ON DELETE RESTRICT,
    CHECK (
        (skill_name = 'modeling-roles'
            AND result_type = 'person_role_model'
            AND subject_type = 'person')
        OR (skill_name = 'modeling-collaboration-relationships'
            AND result_type = 'collaboration_relationship_snapshot'
            AND subject_type = 'organization_scope')
        OR (skill_name = 'modeling-project-state'
            AND result_type = 'project_state_snapshot'
            AND subject_type = 'project')
        OR (skill_name = 'assessing-team-role-ecology'
            AND result_type = 'team_role_ecology_assessment'
            AND subject_type = 'organization_scope')
        OR (skill_name = 'assessing-team-health'
            AND result_type = 'team_health_assessment'
            AND subject_type = 'organization_scope')
        OR (skill_name = 'diagnosing-collaboration-structure'
            AND result_type = 'collaboration_structure_diagnosis'
            AND subject_type = 'organization_scope')
        OR (skill_name = 'analyzing-project-collaboration-risk'
            AND result_type = 'project_collaboration_risk_analysis'
            AND subject_type = 'project')
        OR (skill_name = 'designing-intervention-options'
            AND result_type = 'intervention_option_design'
            AND subject_type = 'management_request')
        OR (skill_name = 'simulating-team-interactions'
            AND result_type = 'team_interaction_simulation'
            AND subject_type = 'simulation')
    ),
    CHECK (
        (status = 'accepted' AND accepted_at IS NOT NULL)
        OR (status <> 'accepted' AND accepted_at IS NULL)
    )
);

-- 上游结果引用独立保存，以确保下游只能指向已存在的 result_id。
-- 被引用结果是否 accepted，以及引用时版本和内容哈希，由运行宿主在写入时校验。
CREATE TABLE IF NOT EXISTS skill_input_result_references (
    input_manifest_id TEXT NOT NULL,
    reference_index INTEGER NOT NULL CHECK (reference_index >= 1),
    result_id TEXT NOT NULL,
    result_schema_version INTEGER NOT NULL CHECK (result_schema_version >= 1),
    output_sha256 TEXT NOT NULL CHECK (output_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (input_manifest_id, reference_index),
    FOREIGN KEY (input_manifest_id)
        REFERENCES skill_input_manifests (input_manifest_id)
        ON DELETE CASCADE,
    FOREIGN KEY (result_id)
        REFERENCES skill_results (result_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_skill_results_current_lookup
    ON skill_results (organization_id, snapshot_date, skill_name, subject_type, subject_id, status);
CREATE INDEX IF NOT EXISTS idx_skill_results_manifest
    ON skill_results (input_manifest_id);
CREATE INDEX IF NOT EXISTS idx_skill_input_result_refs_result
    ON skill_input_result_references (result_id);

INSERT INTO schema_migrations (version)
VALUES ('0002_skill_result_storage')
ON CONFLICT (version) DO NOTHING;

COMMIT;
