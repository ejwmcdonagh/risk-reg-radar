-- Signal clusters: groups of signals that converge on the same threat vector.
--
-- A cluster is the bridge between raw signal ingestion (Step 1) and provocation
-- card generation (Step 3). Each cluster represents a multi-signal pattern that
-- the LLM has judged to be pointing at the same real-world threat.
--
-- signal_ids references signals.id but we store it as UUID[] rather than a
-- junction table because clusters are always read as a unit, and the array
-- makes that read a single row fetch rather than a join.

CREATE TABLE signal_clusters (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- The primary risk domain this cluster sits in. A cluster can span domains
  -- (recorded in metadata.all_domains) but we surface one for filtering/routing.
  risk_domain     TEXT NOT NULL,

  -- UUIDs of every signal that was grouped into this cluster
  signal_ids      UUID[] NOT NULL,

  -- LLM-generated: one-sentence description of what is happening
  cluster_summary TEXT NOT NULL,

  -- LLM-generated: the specific threat vector (e.g. "RCE via unpatched Cisco IOS-XE")
  risk_vector     TEXT NOT NULL,

  -- Additive score — higher is more worth surfacing as a provocation card.
  -- Breakdown stored in metadata.score_breakdown for transparency.
  score           DECIMAL(5,2) NOT NULL,

  signal_count    INTEGER NOT NULL,

  -- Number of distinct sources contributing signals (CISA, NVD, NCSC, etc.).
  -- Cross-source convergence is a strong provocation signal.
  source_count    INTEGER NOT NULL,

  -- Highest severity level across signals in this cluster
  severity_max    TEXT,

  detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Temporal span of the signals in this cluster
  window_start    TIMESTAMPTZ NOT NULL,
  window_end      TIMESTAMPTZ NOT NULL,

  -- Lifecycle: 'pending' until a card is generated, then 'card_generated'.
  -- 'dismissed' is set manually when a cluster is noise.
  status          TEXT NOT NULL DEFAULT 'pending',

  -- Full LLM response + score breakdown stored for auditability and debugging
  metadata        JSONB NOT NULL DEFAULT '{}'
);

-- Fast lookup by domain for the dashboard swim-lane layout (Step 4)
CREATE INDEX idx_clusters_risk_domain  ON signal_clusters (risk_domain);
-- Feed the card generator with the highest-scoring pending clusters
CREATE INDEX idx_clusters_status_score ON signal_clusters (status, score DESC);
-- Chronological listing
CREATE INDEX idx_clusters_detected_at  ON signal_clusters (detected_at DESC);
-- Allow the clustering job to find signals that already belong to a cluster
-- (avoids re-clustering signals that have already been processed)
CREATE INDEX idx_clusters_signal_ids   ON signal_clusters USING GIN (signal_ids);
