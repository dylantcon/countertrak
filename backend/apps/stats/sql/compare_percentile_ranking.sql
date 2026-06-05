-- PLAYER VS FIELD: PERCENTILE RANKING
-- Ranks you against every other tracked player on the core performance
-- metrics, so the rows at the top reveal where your game stands out most.
--
-- Built on stats_playermatchstat (one authoritative row per player per match
-- via ON CONFLICT upsert) rather than summing round_kills across the many
-- per-second PlayerRoundState snapshots, which would massively inflate kills.
WITH player_agg AS (
    SELECT
        steam_account_id,
        COUNT(*)                                      AS matches,
        AVG(kills)                                    AS avg_kills,
        AVG(assists)                                  AS avg_assists,
        AVG(mvps)                                     AS avg_mvps,
        AVG(score)                                    AS avg_score,
        SUM(kills)::numeric / NULLIF(SUM(deaths), 0)  AS kd_ratio
    FROM stats_playermatchstat
    GROUP BY steam_account_id
    HAVING COUNT(*) >= 1
),
ranked AS (
    SELECT
        steam_account_id, matches,
        avg_kills, avg_assists, avg_mvps, avg_score, kd_ratio,
        PERCENT_RANK() OVER (ORDER BY avg_kills)   AS pr_kills,
        PERCENT_RANK() OVER (ORDER BY kd_ratio)    AS pr_kd,
        PERCENT_RANK() OVER (ORDER BY avg_assists) AS pr_assists,
        PERCENT_RANK() OVER (ORDER BY avg_mvps)    AS pr_mvps,
        PERCENT_RANK() OVER (ORDER BY avg_score)   AS pr_score
    FROM player_agg
),
field AS (
    SELECT
        AVG(avg_kills)   AS f_kills,
        AVG(kd_ratio)    AS f_kd,
        AVG(avg_assists) AS f_assists,
        AVG(avg_mvps)    AS f_mvps,
        AVG(avg_score)   AS f_score,
        COUNT(*)         AS player_pool
    FROM player_agg
),
me AS (
    SELECT * FROM ranked WHERE steam_account_id = ${steam_id}
)
SELECT metric, your_value, field_average, percentile_rank, players_compared
FROM (
    SELECT 'Kills / match'  AS metric,
           ROUND(me.avg_kills, 2)               AS your_value,
           ROUND(field.f_kills, 2)              AS field_average,
           ROUND((me.pr_kills * 100)::numeric, 1)   AS percentile_rank,
           field.player_pool                   AS players_compared
    FROM me, field
    UNION ALL
    SELECT 'K/D ratio',
           ROUND(me.kd_ratio, 2), ROUND(field.f_kd, 2),
           ROUND((me.pr_kd * 100)::numeric, 1), field.player_pool
    FROM me, field
    UNION ALL
    SELECT 'Assists / match',
           ROUND(me.avg_assists, 2), ROUND(field.f_assists, 2),
           ROUND((me.pr_assists * 100)::numeric, 1), field.player_pool
    FROM me, field
    UNION ALL
    SELECT 'MVPs / match',
           ROUND(me.avg_mvps, 2), ROUND(field.f_mvps, 2),
           ROUND((me.pr_mvps * 100)::numeric, 1), field.player_pool
    FROM me, field
    UNION ALL
    SELECT 'Score / match',
           ROUND(me.avg_score, 2), ROUND(field.f_score, 2),
           ROUND((me.pr_score * 100)::numeric, 1), field.player_pool
    FROM me, field
) t
ORDER BY percentile_rank DESC NULLS LAST;
