-- Track how many times card generation has been attempted for each cluster.
--
-- Clusters that fail repeatedly (e.g. because the LLM returns no tool_use block)
-- would otherwise stay in 'pending' forever and be retried on every pipeline run.
-- After MAX_CARD_ATTEMPTS failures the status is set to 'failed' so the cluster
-- is skipped on future runs without manual intervention.

ALTER TABLE signal_clusters
    ADD COLUMN IF NOT EXISTS card_generation_attempts INTEGER NOT NULL DEFAULT 0;
