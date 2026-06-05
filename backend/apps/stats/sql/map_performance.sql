-- MAP PERFORMANCE ANALYSIS
-- Demonstrates GROUP BY, HAVING, and AGGREGATE operations.
--
-- These queries read from stats_playermatchstat (one authoritative row per
-- player per match), so per-match kills/deaths/score are already accurate. The
-- win-rate query derives a single team per match for the player (their ending
-- side) instead of joining the multi-row snapshot table, which previously
-- multiplied "matches_won" by the snapshot count and could push win % over 100.

-- Performance statistics by map
SELECT
    m.map_name,
    COUNT(DISTINCT m.match_id) AS matches_played,
    SUM(CASE WHEN pms.kills > pms.deaths THEN 1 ELSE 0 END) AS positive_kd_matches,
    ROUND(AVG(pms.kills), 2) AS avg_kills,
    ROUND(AVG(pms.deaths), 2) AS avg_deaths,
    ROUND(AVG(pms.assists), 2) AS avg_assists,
    ROUND(AVG(pms.score), 2) AS avg_score,
    ROUND(SUM(pms.kills)::numeric / NULLIF(SUM(pms.deaths), 0), 2) AS overall_kd_ratio
FROM
    matches_match m
JOIN
    stats_playermatchstat pms ON m.match_id = pms.match_id
WHERE
    pms.steam_account_id = ${steam_id}
GROUP BY
    m.map_name
ORDER BY
    avg_score DESC;

-- Map win rate analysis with HAVING clause
WITH player_match_team AS (
    -- one row per match: the side the player finished the match on
    SELECT DISTINCT ON (prs.match_id)
        prs.match_id,
        prs.team
    FROM stats_playerroundstate prs
    WHERE prs.steam_account_id = ${steam_id}
    ORDER BY prs.match_id, prs.round_number DESC, prs.state_timestamp DESC
)
SELECT
    m.map_name,
    COUNT(DISTINCT m.match_id) AS matches_played,
    SUM(CASE
        WHEN (pmt.team = 'CT' AND m.team_ct_score > m.team_t_score) OR
             (pmt.team = 'T'  AND m.team_t_score > m.team_ct_score)
        THEN 1 ELSE 0
    END) AS matches_won,
    ROUND(
        (SUM(CASE
            WHEN (pmt.team = 'CT' AND m.team_ct_score > m.team_t_score) OR
                 (pmt.team = 'T'  AND m.team_t_score > m.team_ct_score)
            THEN 1 ELSE 0
        END)::numeric / NULLIF(COUNT(DISTINCT m.match_id), 0)) * 100,
    2) AS win_percentage
FROM
    matches_match m
JOIN
    player_match_team pmt ON m.match_id = pmt.match_id
GROUP BY
    m.map_name
HAVING
    COUNT(DISTINCT m.match_id) >= 3  -- Only include maps played at least 3 times
ORDER BY
    win_percentage DESC;
