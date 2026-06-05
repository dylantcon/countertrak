-- WEAPON PERFORMANCE ANALYSIS
-- Demonstrates SELECT-FROM-WHERE and JOIN operations.
--
-- IMPORTANT: stats_playerroundstate / stats_playerweapon hold one snapshot row
-- per GSI payload (up to ~10/sec), so a single round has many rows that all
-- carry the same running round_kills counter. Naively SUM-ing round_kills over
-- a playerweapon JOIN multiplies snapshots together and grossly over-reports
-- kills. We therefore collapse to one value per (match, round, player) with
-- MAX(round_kills) (the counter is monotonic within a round, so MAX = the round
-- total) and split each round's kills evenly across that round's distinct active
-- weapons. Estimated kills then sum back to the true round total.

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
           rk.round_kills::numeric / NULLIF(awc.active_weapons, 0) AS est_kills
    FROM aw
    JOIN awc USING (match_id, round_number, steam_account_id)
    JOIN rk  USING (match_id, round_number, steam_account_id)
)
SELECT
    w.name AS weapon_name,
    w.type AS weapon_type,
    COUNT(DISTINCT attr.match_id) AS times_used,
    ROUND(SUM(attr.est_kills), 0) AS total_kills_with_weapon,
    ROUND(SUM(attr.est_kills)::numeric /
          NULLIF(COUNT(DISTINCT (attr.match_id, attr.round_number)), 0), 2) AS kills_per_round
FROM attr
JOIN stats_weapon w ON w.weapon_id = attr.weapon_id
GROUP BY w.name, w.type
ORDER BY total_kills_with_weapon DESC;

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
           rk.round_kills::numeric / NULLIF(awc.active_weapons, 0) AS est_kills
    FROM aw
    JOIN awc USING (match_id, round_number, steam_account_id)
    JOIN rk  USING (match_id, round_number, steam_account_id)
)
SELECT
    m.map_name,
    w.name AS weapon_name,
    COUNT(DISTINCT attr.match_id) AS match_count,
    ROUND(SUM(attr.est_kills), 0) AS total_kills,
    ROUND(SUM(attr.est_kills)::numeric /
          NULLIF(COUNT(DISTINCT (attr.match_id, attr.round_number)), 0), 2) AS avg_kills_per_round
FROM attr
JOIN stats_weapon w ON w.weapon_id = attr.weapon_id
JOIN matches_match m ON m.match_id = attr.match_id
GROUP BY m.map_name, w.name
ORDER BY m.map_name, total_kills DESC;
