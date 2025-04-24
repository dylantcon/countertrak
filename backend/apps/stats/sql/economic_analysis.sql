-- ECONOMIC ANALYSIS QUERIES
-- demonstrates economic decision analysis and impact on performance

-- economic round state analysis
WITH round_economics AS (
    SELECT 
        m.match_id,
        m.map_name,
        r.round_number,
        r.winning_team,
        CASE 
            WHEN AVG(prs.equip_value) < 1000 THEN 'Eco (< $1000)'
            WHEN AVG(prs.equip_value) BETWEEN 1000 AND 2500 THEN 'Semi-Eco ($1000-$2500)'
            WHEN AVG(prs.equip_value) BETWEEN 2501 AND 4000 THEN 'Semi-Buy ($2501-$4000)'
            WHEN AVG(prs.equip_value) > 4000 THEN 'Full Buy (> $4000)'
        END AS economic_state,
        AVG(prs.money) AS avg_remaining_money,
        AVG(prs.equip_value) AS avg_equip_value,
        SUM(prs.round_kills) AS total_kills,
        COUNT(DISTINCT prs.steam_account_id) AS player_count
    FROM 
        matches_match m
    JOIN 
        matches_round r ON m.match_id = r.match_id
    JOIN 
        stats_playerroundstate prs ON 
            r.match_id = prs.match_id AND 
            r.round_number = prs.round_number
    WHERE 
        prs.steam_account_id = ${steam_id}
    GROUP BY 
        m.match_id, m.map_name, r.round_number, r.winning_team
)

-- economic strategy effectiveness analysis
SELECT 
    economic_state,
    COUNT(DISTINCT (match_id, round_number)) AS rounds_played,
    ROUND(COUNT(DISTINCT CASE WHEN winning_team = 'CT' OR winning_team = 'T' THEN (match_id, round_number) END)::numeric / 
        NULLIF(COUNT(DISTINCT (match_id, round_number)), 0) * 100, 2) AS win_rate,
    ROUND(SUM(total_kills)::numeric / NULLIF(COUNT(DISTINCT (match_id, round_number)), 0), 2) AS avg_kills_per_round,
    ROUND(AVG(avg_equip_value), 2) AS avg_investment,
    ROUND(AVG(avg_remaining_money), 2) AS avg_remaining_money,
    ROUND(SUM(total_kills)::numeric / NULLIF(SUM(avg_equip_value) / 1000, 0), 2) AS kills_per_1000_spent
FROM 
    round_economics
GROUP BY 
    economic_state
ORDER BY 
    win_rate DESC;

-- economic transitions analysis: impact of previous round's economy
WITH round_sequence AS (
    SELECT DISTINCT ON (prs1.match_id, prs1.round_number)
        prs1.match_id,
        prs1.round_number,
        prs1.steam_account_id,
        prs1.equip_value AS current_equip_value,
        prs1.money AS current_money,
        prs1.round_kills,
        prs1.team,
        r1.winning_team = prs1.team AS round_won,
        LAG(prs1.equip_value) OVER (
            PARTITION BY prs1.match_id
            ORDER BY prs1.round_number
        ) AS prev_equip_value,
        LAG(r1.winning_team = prs1.team) OVER (
            PARTITION BY prs1.match_id
            ORDER BY prs1.round_number
        ) AS prev_round_won
    FROM 
        stats_playerroundstate prs1
    JOIN 
        matches_round r1 ON 
            prs1.match_id = r1.match_id AND 
            prs1.round_number = r1.round_number
    WHERE 
        prs1.steam_account_id = ${steam_id}
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
FROM 
    round_sequence
WHERE 
    round_number > 1  -- exclude first round since it doesn't have previous state
GROUP BY 
    previous_economic_state, previous_round_outcome
HAVING 
    COUNT(*) >= 3  -- only include scenarios with at least 3 occurrences
ORDER BY 
    previous_economic_state, previous_round_outcome;
