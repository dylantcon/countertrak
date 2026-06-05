-- SIGNATURE MAP EDGE: WHERE YOU BEAT THE FIELD
-- For every map you've played, compares your per-match output to the average
-- of all OTHER players on that same map. Maps at the top are where your
-- playstyle shines uniquely relative to everyone else.
--
-- Uses stats_playermatchstat for accurate per-match kills/score (avoids the
-- round-snapshot kill inflation in PlayerRoundState-based aggregations).
WITH per_player_map AS (
    SELECT
        pms.steam_account_id,
        m.map_name,
        COUNT(*)                                          AS matches,
        AVG(pms.kills)                                    AS avg_kills,
        AVG(pms.score)                                    AS avg_score,
        SUM(pms.kills)::numeric / NULLIF(SUM(pms.deaths), 0) AS kd_ratio
    FROM stats_playermatchstat pms
    JOIN matches_match m ON pms.match_id = m.match_id
    GROUP BY pms.steam_account_id, m.map_name
),
field AS (
    SELECT
        map_name,
        AVG(avg_kills) AS field_avg_kills,
        AVG(avg_score) AS field_avg_score,
        AVG(kd_ratio)  AS field_kd,
        COUNT(*)       AS rival_players
    FROM per_player_map
    WHERE steam_account_id <> ${steam_id}
    GROUP BY map_name
)
SELECT
    me.map_name,
    me.matches                                       AS your_matches,
    f.rival_players,
    ROUND(me.avg_kills, 2)                           AS your_avg_kills,
    ROUND(f.field_avg_kills, 2)                      AS field_avg_kills,
    ROUND((me.avg_kills - f.field_avg_kills), 2)     AS kills_edge,
    ROUND(me.kd_ratio, 2)                            AS your_kd,
    ROUND(f.field_kd, 2)                             AS field_kd,
    ROUND((me.kd_ratio - f.field_kd), 2)            AS kd_edge,
    ROUND((me.avg_score - f.field_avg_score), 2)    AS score_edge
FROM per_player_map me
JOIN field f ON me.map_name = f.map_name
WHERE me.steam_account_id = ${steam_id}
ORDER BY kills_edge DESC NULLS LAST;
