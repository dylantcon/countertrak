-- WEAPON PERFORMANCE ANALYSIS
-- Demonstrates SELECT-FROM-WHERE and JOIN operations with accurate kill attribution.
--
-- The previous version used DISTINCT ON without ordering by state_timestamp, so it
-- captured an arbitrary snapshot's round_kills (often 0). This version takes
-- MAX(round_kills) per (match, round, player) -- the true round total, since the
-- counter only increases within a round -- and distributes it evenly across that
-- round's distinct active weapons, so estimated kills sum back to the real total.

-- Basic weapon effectiveness by player (SELECT-FROM-WHERE, JOIN)
WITH rk AS (
    SELECT match_id, round_number, steam_account_id,
           MAX(round_kills) AS round_kills
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
           rk.round_kills::numeric / NULLIF(awc.active_weapons, 0) AS estimated_kills
    FROM aw
    JOIN awc USING (match_id, round_number, steam_account_id)
    JOIN rk  USING (match_id, round_number, steam_account_id)
)
SELECT
    w.name AS weapon_name,
    w.type AS weapon_type,
    COUNT(DISTINCT attr.match_id) AS matches_used,
    COUNT(DISTINCT (attr.match_id, attr.round_number)) AS rounds_used,
    ROUND(SUM(attr.estimated_kills), 0) AS estimated_total_kills,
    ROUND(SUM(attr.estimated_kills)::numeric /
          NULLIF(COUNT(DISTINCT (attr.match_id, attr.round_number)), 0), 2) AS kills_per_round
FROM attr
JOIN stats_weapon w ON w.weapon_id = attr.weapon_id
GROUP BY w.name, w.type
ORDER BY estimated_total_kills DESC;

-- Weapon performance by map (Multiple JOIN example)
WITH rk AS (
    SELECT match_id, round_number, steam_account_id,
           MAX(round_kills) AS round_kills
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
           rk.round_kills::numeric / NULLIF(awc.active_weapons, 0) AS estimated_kills
    FROM aw
    JOIN awc USING (match_id, round_number, steam_account_id)
    JOIN rk  USING (match_id, round_number, steam_account_id)
)
SELECT
    m.map_name,
    w.name AS weapon_name,
    COUNT(DISTINCT attr.match_id) AS matches_used,
    COUNT(DISTINCT (attr.match_id, attr.round_number)) AS rounds_used,
    ROUND(SUM(attr.estimated_kills), 0) AS estimated_total_kills,
    ROUND(SUM(attr.estimated_kills)::numeric /
          NULLIF(COUNT(DISTINCT (attr.match_id, attr.round_number)), 0), 2) AS kills_per_round
FROM attr
JOIN stats_weapon w ON w.weapon_id = attr.weapon_id
JOIN matches_match m ON m.match_id = attr.match_id
GROUP BY m.map_name, w.name
ORDER BY m.map_name, estimated_total_kills DESC;
