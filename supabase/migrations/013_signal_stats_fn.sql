-- SQL aggregation for signal stats.
--
-- Replaces Python-side groupby that loaded every signal row into memory.
-- unnest(risk_domains) expands the TEXT[] column so we can GROUP BY domain,
-- which is not possible with a plain GROUP BY on an array column.

CREATE OR REPLACE FUNCTION get_signal_stats()
RETURNS JSON LANGUAGE sql STABLE AS $$
    SELECT json_build_object(
        'by_source',
        (SELECT COALESCE(json_object_agg(source, cnt), '{}')
         FROM (SELECT source, COUNT(*) AS cnt FROM signals GROUP BY source) s),
        'by_domain',
        (SELECT COALESCE(json_object_agg(domain, cnt), '{}')
         FROM (SELECT unnest(risk_domains) AS domain, COUNT(*) AS cnt
               FROM signals GROUP BY domain) d)
    );
$$;
