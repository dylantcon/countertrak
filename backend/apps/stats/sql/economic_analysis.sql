-- ECONOMIC ANALYSIS QUERIES
-- demonstrates economic decision analysis and impact on performance.
--
-- Each round has many snapshot rows, so we first reduce stats_playerroundstate to
-- one row per (match, round, player) using MAX(round_kills)/MAX(equip_value) and
-- the round's average money, so kills and spend are counted once per round.
-- Win rate compares the round winner to the player's own team (the previous
-- version counted every decided round as a "win", which was always ~100%).

-- economic round state analysis
WITH rk AS (
    SELECT match_id, round_number, steam_account_id,
           MAX(round_kills) AS round_kills,
           MAX(equip_value) AS equip_value,
           ROUND(AVG(money)) AS money,
           MAX(team)        AS team
    FROM stats_playerroundstate
    WHERE steam_account_id = ${steam_id}
    GROUP BY match_id, round_number, steam_account_id
),
round_economics AS (
    SELECT
        m.match_id,
        m.map_name,
        r.round_number,
        CASE
            WHEN rk.equip_value < 1000 THEN 'Eco (< $1000)'
            WHEN rk.equip_value BETWEEN 1000 AND 2500 THEN 'Semi-Eco ($1000-$2500)'
            WHEN rk.equip_value BETWEEN 2501 AND 4000 THEN 'Semi-Buy ($2501-$4000)'
            WHEN rk.equip_value > 4000 THEN 'Full Buy (> $4000)'
        END AS economic_state,
        rk.money AS remaining_money,
        rk.equip_value AS equip_value,
        rk.round_kills AS round_kills,
        (r.winning_team = rk.team) AS round_won
    FROM rk
    JOIN matches_match m ON rk.match_id = m.match_id
    JOIN matches_round r ON rk.match_id = r.match_id AND rk.round_number = r.round_number
)

-- economic strategy effectiveness analysis
SELECT
    economic_state,
    COUNT(*) AS rounds_played,
    ROUND(COUNT(*) FILTER (WHERE round_won)::numeric /
          NULLIF(COUNT(*), 0) * 100, 2) AS win_rate,
    ROUND(AVG(round_kills), 2) AS avg_kills_per_round,
    ROUND(AVG(equip_value), 2) AS avg_investment,
    ROUND(AVG(remaining_money), 2) AS avg_remaining_money,
    ROUND(SUM(round_kills)::numeric / NULLIF(SUM(equip_value) / 1000, 0), 2) AS kills_per_1000_spent
FROM round_economics
GROUP BY economic_state
ORDER BY win_rate DESC;

-- economic transitions analysis: impact of previous round's economy
WITH rk AS (
    SELECT match_id, round_number, steam_account_id,
           MAX(round_kills) AS round_kills,
           MAX(equip_value) AS equip_value,
           ROUND(AVG(money)) AS money,
           MAX(team)        AS team
    FROM stats_playerroundstate
    WHERE steam_account_id = ${steam_id}
    GROUP BY match_id, round_number, steam_account_id
),
round_sequence AS (
    SELECT
        rk.match_id,
        rk.round_number,
        rk.equip_value AS current_equip_value,
        rk.money AS current_money,
        rk.round_kills,
        rk.team,
        (r.winning_team = rk.team) AS round_won,
        LAG(rk.equip_value) OVER (
            PARTITION BY rk.match_id
            ORDER BY rk.round_number
        ) AS prev_equip_value,
        LAG((r.winning_team = rk.team)) OVER (
            PARTITION BY rk.match_id
            ORDER BY rk.round_number
        ) AS prev_round_won
    FROM rk
    JOIN matches_round r ON rk.match_id = r.match_id AND rk.round_number = r.round_number
)

SELECT
    CASE
        WHEN prev_equip_value < 1000 THEN 'After Eco (< $1000)'
        WHEN prev_equip_value BETWEEN 1000 AND 2500 THEN 'After Semi-Eco ($1000-$2500)'
        WHEN prev_equip_value BETWEEN 2501 AND 4000 THEN 'After Semi-Buy ($2501-$4000)'
        WHEN prev_equip_value > 4000 THEN 'After Full Buy (> $4000)'
        ELSE 'First Round'
    END AS previous_economic_state,
    CASE
        WHEN prev_round_won IS TRUE THEN 'Won'
        WHEN prev_round_won IS FALSE THEN 'Lost'
        ELSE 'First Round'
    END AS previous_round_outcome,
    COUNT(*) AS rounds_played,
    ROUND(AVG(current_equip_value), 2) AS avg_current_investment,
    ROUND(AVG(current_money), 2) AS avg_current_money,
    ROUND(AVG(round_kills), 2) AS avg_kills,
    ROUND(COUNT(CASE WHEN round_won THEN 1 END)::numeric /
          NULLIF(COUNT(*), 0) * 100, 2) AS win_percentage
FROM round_sequence
WHERE round_number > 1  -- exclude first round since it doesn't have previous state
GROUP BY previous_economic_state, previous_round_outcome
HAVING COUNT(*) >= 3  -- only include scenarios with at least 3 occurrences
ORDER BY previous_economic_state, previous_round_outcome;
