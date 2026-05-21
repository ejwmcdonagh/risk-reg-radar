-- Provocation cards: the user-facing output of Regulatory Radar.
--
-- Each card is generated from one signal cluster and contains the 5 layers
-- defined in the product brief. Cards are the primary artefact the CISO
-- interacts with — the signal ingestion and clustering pipeline exists to
-- produce these.
--
-- Why store the 5 layers as separate columns rather than a single JSONB blob?
-- Each layer has a distinct lifecycle: the board_talking_point may be edited
-- before a briefing, the compliance_gap may need a compliance officer review,
-- the contextual_question may be reused across cards. Separate columns make
-- targeted updates and partial rendering easier than unpacking JSONB every time.

CREATE TABLE provocation_cards (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id           UUID NOT NULL REFERENCES signal_clusters(id),

  -- Layer 1: punchy present-tense headline
  signal_headline      TEXT NOT NULL,

  -- Layer 2: structured list of the contributing signals with source attribution.
  -- Array of {source, title, url, point} objects — rendered as a bullet list.
  evidence_stack       JSONB NOT NULL DEFAULT '[]',

  -- Layer 3: which regulatory or audit framework this falls through
  compliance_gap       TEXT NOT NULL,

  -- Layer 4: question the CISO can pose to their team or board
  contextual_question  TEXT NOT NULL,

  -- Layer 5: one paragraph the CISO can use almost verbatim in a board briefing
  board_talking_point  TEXT NOT NULL,

  -- Denormalised from the cluster for fast filtering without a join
  risk_domain          TEXT NOT NULL,
  score                DECIMAL(5,2) NOT NULL,

  generated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- 'active' | 'archived' — archived cards are hidden from the default feed
  -- but retained for audit trail and trend analysis
  status               TEXT NOT NULL DEFAULT 'active',

  -- Model name + token usage stored for cost tracking and quality auditing
  metadata             JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_cards_risk_domain   ON provocation_cards (risk_domain);
CREATE INDEX idx_cards_status_score  ON provocation_cards (status, score DESC);
CREATE INDEX idx_cards_generated_at  ON provocation_cards (generated_at DESC);
CREATE INDEX idx_cards_cluster_id    ON provocation_cards (cluster_id);
