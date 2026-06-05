-- GROUP BY WITH HAVING CLAUSES
-- Demonstrates specific GROUP BY operations with HAVING filters.
--
-- Both queries first collapse the per-payload snapshot rows in
-- stats_playerroundstate to one row per (match, round, player) using
-- MAX(round_kills) (the per-round counter is monotonic, so MAX = the round
-- total). This avoids the snapshot multiplication that otherwise inflates
-- both kill sums and round counts.

-- Weapon performance grouped by type with effectiveness thresholds
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
           rk.round_kills AS round_total_kills,
           rk.round_kills::numeric / NULLIF(awc.active_weapons, 0) AS est_kills
    FROM aw
    JOIN awc USING (match_id, round_number, steam_account_id)
    JOIN rk  USING (match_id, round_number, steam_account_id)
)
SELECT
    w.type AS weapon_type,
    COUNT(DISTINCT attr.weapon_id) AS weapons_in_category,
    ROUND(SUM(attr.est_kills), 0) AS total_kills,
    COUNT(DISTINCT (attr.match_id, attr.round_number)) AS rounds_used,
    ROUND(SUM(attr.est_kills)::numeric /
          NULLIF(COUNT(DISTINCT (attr.match_id, attr.round_number)), 0), 2) AS avg_kills_per_round,
    MAX(attr.round_total_kills) AS max_kills_in_round
FROM attr
JOIN stats_weapon w ON w.weapon_id = attr.weapon_id
GROUP BY w.type
HAVING
    COUNT(DISTINCT (attr.match_id, attr.round_number)) >= 10  -- weapon types used in >= 10 rounds
    AND SUM(attr.est_kills) >= 5                              -- with at least ~5 attributed kills
ORDER BY avg_kills_per_round DESC;

-- Economic strategy grouping with effectiveness filters
WITH rk AS (
    SELECT match_id, round_number, steam_account_id,
           MAX(round_kills) AS round_kills,
           MAX(equip_value) AS equip_value,
           ROUND(AVG(money)) AS money,
           MAX(team)        AS team
    FROM stats_playerroundstate
    WHERE steam_account_id = ${steam_id}
    GROUP BY match_id, round_number, steam_account_id
)
SELECT
    CASE
        WHEN rk.equip_value < 1000 THEN 'Eco (< $1000)'
        WHEN rk.equip_value BETWEEN 1000 AND 2500 THEN 'Semi-Eco ($1000-$2500)'
        WHEN rk.equip_value BETWEEN 2501 AND 4000 THEN 'Semi-Buy ($2501-$4000)'
        WHEN rk.equip_value > 4000 THEN 'Full Buy (> $4000)'
    END AS buy_strategy,
    COUNT(*) AS rounds_used,
    ROUND(AVG(rk.round_kills), 2) AS avg_kills,
    ROUND(AVG(rk.money), 2) AS avg_remaining_money,
    SUM(CASE WHEN r.winning_team = rk.team THEN 1 ELSE 0 END) AS rounds_won,
    ROUND(
        SUM(CASE WHEN r.winning_team = rk.team THEN 1 ELSE 0 END)::numeric /
        NULLIF(COUNT(*), 0) * 100,
    2) AS strategy_win_rate
FROM rk
JOIN matches_round r ON rk.match_id = r.match_id AND rk.round_number = r.round_number
GROUP BY buy_strategy
HAVING
    COUNT(*) >= 10                 -- strategies used in at least 10 rounds
    AND AVG(rk.round_kills) > 0    -- with some success
ORDER BY strategy_win_rate DESC;
