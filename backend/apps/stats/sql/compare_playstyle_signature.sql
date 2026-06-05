-- PLAYSTYLE SIGNATURE: YOUR RATIOS VS THE AVERAGE PLAYER
-- Describes *how* you play rather than raw skill, using ratios that capture
-- role tendencies, then measures how far each one deviates from the field
-- average. Every trait is framed so that "higher = more pronounced", so the
-- top row is the dimension where your style is most distinctive.
--
-- Built entirely on stats_playermatchstat to keep kill-derived ratios accurate
-- (round_kills snapshot rows would over-count and skew every ratio).
WITH player_ratios AS (
    SELECT
        steam_account_id,
        COUNT(*)                                      AS matches,
        SUM(assists)::numeric / NULLIF(SUM(kills), 0) AS assists_per_kill,
        AVG(mvps)                                     AS mvps_per_match,
        SUM(score)::numeric / NULLIF(SUM(kills), 0)   AS score_per_kill,
        SUM(kills)::numeric / NULLIF(SUM(deaths), 0)  AS kd_ratio,
        AVG(kills)                                    AS kills_per_match
    FROM stats_playermatchstat
    GROUP BY steam_account_id
    HAVING COUNT(*) >= 1
),
field AS (
    SELECT
        AVG(assists_per_kill) AS f_apk,
        AVG(mvps_per_match)   AS f_mvp,
        AVG(score_per_kill)   AS f_spk,
        AVG(kd_ratio)         AS f_kd,
        AVG(kills_per_match)  AS f_kpm
    FROM player_ratios
    WHERE steam_account_id <> ${steam_id}
),
me AS (
    SELECT * FROM player_ratios WHERE steam_account_id = ${steam_id}
)
SELECT
    trait,
    your_value,
    field_average,
    ROUND(((your_value - field_average) / NULLIF(ABS(field_average), 0) * 100)::numeric, 1)
        AS pct_vs_field
FROM (
    SELECT 'Support  (assists per kill)' AS trait,
           ROUND(me.assists_per_kill, 3) AS your_value,
           ROUND(field.f_apk, 3)         AS field_average
    FROM me, field
    UNION ALL
    SELECT 'Impact   (MVPs per match)',
           ROUND(me.mvps_per_match, 3), ROUND(field.f_mvp, 3)
    FROM me, field
    UNION ALL
    SELECT 'Utility  (score per kill)',
           ROUND(me.score_per_kill, 3), ROUND(field.f_spk, 3)
    FROM me, field
    UNION ALL
    SELECT 'Dueling  (K/D ratio)',
           ROUND(me.kd_ratio, 3), ROUND(field.f_kd, 3)
    FROM me, field
    UNION ALL
    SELECT 'Firepower (kills per match)',
           ROUND(me.kills_per_match, 3), ROUND(field.f_kpm, 3)
    FROM me, field
) t
ORDER BY pct_vs_field DESC NULLS LAST;
