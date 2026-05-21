-- Org profile: single-row table storing the CISO's environment configuration.
--
-- Technologies are used to re-order and highlight provocation cards that
-- mention systems the org actually runs. A card about a Palo Alto firewall
-- vulnerability is more urgent if the org uses Palo Alto.
--
-- We use a single-row convention (id=1) rather than a multi-tenant design
-- because V1 is single-org. Extend to multi-tenant in Step 7 (onboarding).

CREATE TABLE org_profile (
  id             INTEGER PRIMARY KEY DEFAULT 1,
  technologies   TEXT[] NOT NULL DEFAULT '{}',
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  -- Constraint enforces the single-row pattern
  CONSTRAINT single_row CHECK (id = 1)
);

-- Seed an empty profile so the GET endpoint always finds a row
INSERT INTO org_profile (id) VALUES (1);

-- Custom RSS/Atom signal sources added by the CISO.
-- These are ingested by the custom RSS ingester on the same schedule as
-- the built-in sources. Disabling a source stops ingestion without deleting it.

CREATE TABLE custom_sources (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  url         TEXT NOT NULL UNIQUE,
  enabled     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
