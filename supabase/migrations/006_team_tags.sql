-- Add team tagging to provocation cards so CISOs can filter by affected security team
ALTER TABLE provocation_cards
  ADD COLUMN affected_teams TEXT[] NOT NULL DEFAULT '{}';

CREATE INDEX idx_cards_affected_teams ON provocation_cards USING GIN (affected_teams);
