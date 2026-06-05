-- ADVANCED WEAPON RECOMMENDATIONS
-- Demonstrates advanced analytics for our unique performance pattern recognition.
--
-- Kills and equipment spend are per-round resources, but the snapshot tables
-- store many rows per round. We collapse to one row per (match, round, player)
-- with MAX(round_kills)/MAX(equip_value), then split both evenly across the
-- round's distinct active weapons so totals never exceed the real round values.

-- Weapon effectiveness by map with performance scoring
WITH rk AS (
    SELECT match_id, round_number, steam_account_id,
           MAX(round_kills) AS round_kills,
           MAX(equip_value) AS equip_value
    FROM stats_playerroundstate
    WHERE steam_account_id = ${steam_id}
    GROUP BY match_id, round_number, steam_account_id
),
aw AS (
    SELECT DISTINCT match_id, round_number, steam_account_id, weapon_id
    FROM stats_playerweapon
    WHERE state = 'active' AND steam_account_id = ${steam_id}
),
awc AS (
    SELECT match_id, round_number, steam_account_id, COUNT(*) AS active_weapons
    FROM aw
    GROUP BY match_id, round_number, steam_account_id
),
attr AS (
    SELECT aw.weapon_id, aw.match_id, aw.round_number,
           rk.round_kills AS round_total_kills,
           rk.round_kills::numeric / NULLIF(awc.active_weapons, 0) AS est_kills,
           rk.equip_value::numeric / NULLIF(awc.active_weapons, 0) AS est_equip
    FROM aw
    JOIN awc USING (match_id, round_number, steam_account_id)
    JOIN rk  USING (match_id, round_number, steam_account_id)
),
weapon_performance AS (
    SELECT
        m.map_name,
        w.name AS weapon_name,
        w.type AS weapon_type,
        COUNT(DISTINCT attr.match_id) AS matches_used,
        ROUND(SUM(attr.est_kills), 0) AS total_kills,
        COUNT(DISTINCT CASE WHEN attr.round_total_kills > 0
                            THEN attr.match_id || '-' || attr.round_number END) AS rounds_with_kills,
        COUNT(DISTINCT attr.match_id || '-' || attr.round_number) AS total_rounds_used,
        -- Performance metrics
        ROUND(SUM(attr.est_kills)::numeric /
              NULLIF(COUNT(DISTINCT attr.match_id || '-' || attr.round_number), 0), 3) AS kills_per_round,
        ROUND(COUNT(DISTINCT CASE WHEN attr.round_total_kills > 0
                                  THEN attr.match_id || '-' || attr.round_number END)::numeric /
              NULLIF(COUNT(DISTINCT attr.match_id || '-' || attr.round_number), 0), 3) AS kill_consistency,
        -- Economic efficiency
        ROUND(SUM(attr.est_kills)::numeric / NULLIF(SUM(attr.est_equip) / 1000, 0), 3) AS kills_per_1000_spent
    FROM attr
    JOIN stats_weapon w ON w.weapon_id = attr.weapon_id
    JOIN matches_match m ON m.match_id = attr.match_id
    WHERE w.type NOT IN ('Knife', 'Grenade', 'C4', 'Other')
    GROUP BY m.map_name, w.name, w.type
    HAVING COUNT(DISTINCT attr.match_id || '-' || attr.round_number) >= 5  -- weapons with sufficient usage
)
SELECT
    map_name,
    weapon_name,
    weapon_type,
    matches_used,
    total_kills,
    kills_per_round,
    kill_consistency,
    kills_per_1000_spent,
    -- Calculate optimal weapon score (advanced weighting algorithm)
    ROUND(
        (kills_per_round * 0.4) +
        (kill_consistency * 0.3) +
        (kills_per_1000_spent * 0.3)
    , 3) AS weapon_effectiveness_score,
    -- Generate recommendation tier
    CASE
        WHEN kills_per_round >= 0.75 AND kill_consistency >= 0.5 THEN 'S-Tier'
        WHEN kills_per_round >= 0.5 AND kill_consistency >= 0.4 THEN 'A-Tier'
        WHEN kills_per_round >= 0.3 AND kill_consistency >= 0.3 THEN 'B-Tier'
        WHEN kills_per_round >= 0.2 THEN 'C-Tier'
        ELSE 'D-Tier'
    END AS recommendation_tier
FROM weapon_performance
ORDER BY map_name, weapon_effectiveness_score DESC;
