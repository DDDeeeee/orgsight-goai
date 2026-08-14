-- Rename the original descriptive field without changing authorization semantics.
-- 0003 may already have been applied to local GOAI Demo databases.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_task_grants'
          AND column_name = 'purpose'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'mcp_task_grants'
          AND column_name = 'task_objective'
    ) THEN
        ALTER TABLE mcp_task_grants
            RENAME COLUMN purpose TO task_objective;
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('0004_rename_task_objective')
ON CONFLICT (version) DO NOTHING;

COMMIT;
