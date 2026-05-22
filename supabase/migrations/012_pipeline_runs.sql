-- Pipeline run audit log.
--
-- Stores the status and result of every manual or scheduled clustering and
-- card generation run. Enables status polling after background tasks are
-- fired - callers no longer need to block waiting for the pipeline to finish.

CREATE TABLE pipeline_runs (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- 'clustering' | 'card_generation'
    type         TEXT        NOT NULL,
    -- 'running' | 'completed' | 'failed'
    status       TEXT        NOT NULL DEFAULT 'running',
    started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    -- Populated on success: {"clusters_written": N} or {"cards_written": N}
    result       JSONB,
    -- Populated on failure - message only, no internal detail
    error        TEXT
);

-- Primary access pattern: list recent runs by type, newest first
CREATE INDEX idx_pipeline_runs_type_started ON pipeline_runs (type, started_at DESC);
