-- Atomic helper for toggling a source ID in the disabled_sources array.
--
-- Using array_append / array_remove in a single UPDATE is safer than the
-- read-modify-write pattern in Python, which has a race condition when two
-- requests toggle the same source concurrently. Returns true if the source
-- is now enabled (i.e. removed from disabled_sources), false if now disabled.

CREATE OR REPLACE FUNCTION toggle_disabled_source(p_source_id TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_disabled TEXT[];
    v_enabled  BOOLEAN;
BEGIN
    SELECT disabled_sources INTO v_disabled
    FROM org_profile
    WHERE id = 1
    FOR UPDATE;  -- row-level lock prevents concurrent races on the same toggle

    IF p_source_id = ANY(v_disabled) THEN
        UPDATE org_profile
        SET disabled_sources = array_remove(disabled_sources, p_source_id),
            updated_at        = NOW()
        WHERE id = 1;
        v_enabled := TRUE;
    ELSE
        UPDATE org_profile
        SET disabled_sources = array_append(disabled_sources, p_source_id),
            updated_at        = NOW()
        WHERE id = 1;
        v_enabled := FALSE;
    END IF;

    RETURN v_enabled;
END;
$$;
