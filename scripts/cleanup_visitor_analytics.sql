-- Cleanup for pre-existing visitor_analytics noise: dev/LAN sessions and
-- bot/empty sessions recorded before the hostname + is_internal columns
-- and the Origin check existed.
--
-- NON-DESTRUCTIVE BY DESIGN: this script contains no DELETE, DROP, or
-- TRUNCATE statement anywhere. Part B only ever sets is_internal = TRUE —
-- every raw row stays in the table forever; it's just excluded from
-- reporting (GET /api/analytics/summary already filters WHERE is_internal
-- IS FALSE). Nothing here is run automatically; nothing in the app code
-- deletes or hides these rows from the database itself.
--
-- Usage: run Part A first, read the counts, and only then run Part B.
--   psql "$DATABASE_URL" -f scripts/cleanup_visitor_analytics.sql
-- or copy/paste each part individually into a SQL client.

-- ═════════════════════════════════════════════════════════════════════════
-- PART A — INSPECT ONLY. Read-only SELECTs. Run this first and review the
-- numbers before touching Part B. Nothing here writes to the database.
-- ═════════════════════════════════════════════════════════════════════════

-- Overall shape of the table right now.
SELECT
  count(*)                                                                         AS total_rows,
  count(*) FILTER (WHERE is_internal IS TRUE)                                      AS already_flagged_internal,
  count(*) FILTER (WHERE hostname IS NULL)                                         AS no_hostname_recorded  -- rows from before this column existed
FROM visitor_analytics;

-- Breakdown by reason a row would be flagged in Part B. A row can match more
-- than one reason; this just shows how much each pattern contributes.
SELECT
  'localhost_or_lan_referrer' AS reason,
  count(*) AS matching_rows
FROM visitor_analytics
WHERE is_internal IS NOT TRUE
  AND (
    referral_source ILIKE '%localhost%'
    OR referral_source ILIKE '%127.0.0.1%'
    OR referral_source ILIKE '%192.168.%'
  )

UNION ALL

SELECT
  'non_prod_hostname',
  count(*)
FROM visitor_analytics
WHERE is_internal IS NOT TRUE
  AND hostname IS NOT NULL
  AND hostname NOT IN ('samefeel.co', 'www.samefeel.co')

UNION ALL

SELECT
  'zero_duration_no_pages_older_than_1h',
  count(*)
FROM visitor_analytics
WHERE is_internal IS NOT TRUE
  AND coalesce(session_duration_seconds, 0) = 0
  AND coalesce(jsonb_array_length(pages_viewed::jsonb), 0) = 0
  AND created_at < now() - interval '1 hour';

-- Total distinct rows Part B would flag (union of all three reasons above,
-- counted once each — this is the number that will change after Part B).
SELECT count(*) AS rows_part_b_would_flag
FROM visitor_analytics
WHERE is_internal IS NOT TRUE
  AND (
    referral_source ILIKE '%localhost%'
    OR referral_source ILIKE '%127.0.0.1%'
    OR referral_source ILIKE '%192.168.%'
    OR (hostname IS NOT NULL AND hostname NOT IN ('samefeel.co', 'www.samefeel.co'))
    OR (
      coalesce(session_duration_seconds, 0) = 0
      AND coalesce(jsonb_array_length(pages_viewed::jsonb), 0) = 0
      AND created_at < now() - interval '1 hour'
    )
  );


-- ═════════════════════════════════════════════════════════════════════════
-- PART B — WRITES. Only run this after reviewing Part A's counts above.
-- UPDATE only — no DELETE anywhere in this file. Every row stays in the
-- table; this just sets is_internal = TRUE so reporting excludes it.
-- ═════════════════════════════════════════════════════════════════════════

-- B1. Flag dev/LAN referrers and non-production hostnames as internal.
UPDATE visitor_analytics
SET is_internal = TRUE
WHERE is_internal IS NOT TRUE
  AND (
    referral_source ILIKE '%localhost%'
    OR referral_source ILIKE '%127.0.0.1%'
    OR referral_source ILIKE '%192.168.%'
    OR (hostname IS NOT NULL AND hostname NOT IN ('samefeel.co', 'www.samefeel.co'))
  );

-- B2. Flag empty/bot-shaped sessions as internal. 0 duration AND no pages
-- viewed is the "fired sessionStart, never sent an update" shape — bots,
-- prerenderers, tabs closed instantly. The 1-hour age guard avoids flagging
-- a real visitor's very first beacon before their update tick has fired.
UPDATE visitor_analytics
SET is_internal = TRUE
WHERE is_internal IS NOT TRUE
  AND coalesce(session_duration_seconds, 0) = 0
  AND coalesce(jsonb_array_length(pages_viewed::jsonb), 0) = 0
  AND created_at < now() - interval '1 hour';

-- Verify what changed.
SELECT is_internal, count(*) FROM visitor_analytics GROUP BY is_internal;


-- ═════════════════════════════════════════════════════════════════════════
-- UNDO — if Part B flagged rows it shouldn't have, this reverses it. Re-run
-- the exact same WHERE clauses with is_internal = FALSE. Since Part B never
-- deletes anything, nothing here needs to reconstruct lost data — it just
-- flips the flag back.
-- ═════════════════════════════════════════════════════════════════════════

-- UPDATE visitor_analytics
-- SET is_internal = FALSE
-- WHERE is_internal IS TRUE
--   AND (
--     referral_source ILIKE '%localhost%'
--     OR referral_source ILIKE '%127.0.0.1%'
--     OR referral_source ILIKE '%192.168.%'
--     OR (hostname IS NOT NULL AND hostname NOT IN ('samefeel.co', 'www.samefeel.co'))
--     OR (
--       coalesce(session_duration_seconds, 0) = 0
--       AND coalesce(jsonb_array_length(pages_viewed::jsonb), 0) = 0
--     )
--   );
