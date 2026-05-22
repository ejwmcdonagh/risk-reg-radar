ALTER TABLE org_profile
  ADD COLUMN blocked_technologies TEXT[] NOT NULL DEFAULT '{}';
