-- OrgSight 的首个组织记忆 PostgreSQL schema。
-- 本 schema 承载组织、模型、关系和项目快照；不包含 AgentTeams runtime 数据。

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_snapshots (
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    display_name TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (organization_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS organization_units (
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    unit_id TEXT NOT NULL,
    name TEXT NOT NULL,
    parent_unit_id TEXT,
    manager_person_id TEXT,
    PRIMARY KEY (organization_id, snapshot_date, unit_id),
    FOREIGN KEY (organization_id, snapshot_date)
        REFERENCES organization_snapshots (organization_id, snapshot_date)
        ON DELETE CASCADE
);

-- 早期本地库曾保存开发参考说明；该说明不属于正式组织记录。
ALTER TABLE organization_snapshots DROP COLUMN IF EXISTS reference_baseline;

CREATE TABLE IF NOT EXISTS people (
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    person_id TEXT NOT NULL,
    name TEXT NOT NULL,
    formal_title TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    formal_manager_person_id TEXT,
    functional_manager TEXT,
    employment_type TEXT NOT NULL,
    formal_structure_note TEXT,
    PRIMARY KEY (organization_id, snapshot_date, person_id),
    FOREIGN KEY (organization_id, snapshot_date, unit_id)
        REFERENCES organization_units (organization_id, snapshot_date, unit_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS person_profiles (
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    person_id TEXT NOT NULL,
    profile_json JSONB NOT NULL,
    source_status TEXT NOT NULL,
    PRIMARY KEY (organization_id, snapshot_date, person_id),
    FOREIGN KEY (organization_id, snapshot_date, person_id)
        REFERENCES people (organization_id, snapshot_date, person_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS model_documents (
    model_document_id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    model_type TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    source_json_sha256 TEXT NOT NULL,
    content_sha256 TEXT,
    document_status TEXT NOT NULL,
    generated_at TIMESTAMPTZ,
    CHECK (subject_type IN ('person', 'team', 'project', 'analysis'))
);

CREATE TABLE IF NOT EXISTS person_models (
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    person_id TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    model_document_id TEXT NOT NULL UNIQUE,
    model_json JSONB NOT NULL,
    model_status TEXT NOT NULL,
    PRIMARY KEY (organization_id, snapshot_date, person_id, model_version),
    FOREIGN KEY (organization_id, snapshot_date, person_id)
        REFERENCES people (organization_id, snapshot_date, person_id)
        ON DELETE CASCADE,
    FOREIGN KEY (model_document_id)
        REFERENCES model_documents (model_document_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS relationship_snapshots (
    relationship_snapshot_id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    status TEXT NOT NULL,
    usage_note TEXT NOT NULL,
    FOREIGN KEY (organization_id, snapshot_date)
        REFERENCES organization_snapshots (organization_id, snapshot_date)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relationship_edges (
    relationship_snapshot_id TEXT NOT NULL,
    relationship_index INTEGER NOT NULL,
    member_a_person_id TEXT NOT NULL,
    member_b_person_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    valence TEXT NOT NULL CHECK (valence IN ('positive', 'neutral', 'negative')),
    salience SMALLINT NOT NULL CHECK (salience BETWEEN 1 AND 5),
    summary TEXT NOT NULL,
    risk TEXT NOT NULL,
    CHECK (member_a_person_id <> member_b_person_id),
    PRIMARY KEY (relationship_snapshot_id, relationship_index),
    UNIQUE (relationship_snapshot_id, member_a_person_id, member_b_person_id),
    FOREIGN KEY (relationship_snapshot_id)
        REFERENCES relationship_snapshots (relationship_snapshot_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    project_json JSONB NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (organization_id, snapshot_date)
        REFERENCES organization_snapshots (organization_id, snapshot_date)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_events (
    event_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    occurred_at DATE NOT NULL,
    event_json JSONB NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects (project_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_people_by_unit
    ON people (organization_id, snapshot_date, unit_id);
CREATE INDEX IF NOT EXISTS idx_person_models_by_person
    ON person_models (organization_id, snapshot_date, person_id);
CREATE INDEX IF NOT EXISTS idx_relationship_edges_endpoints
    ON relationship_edges (relationship_snapshot_id, member_a_person_id, member_b_person_id);

INSERT INTO schema_migrations (version)
VALUES ('0001_organization_memory')
ON CONFLICT (version) DO NOTHING;
