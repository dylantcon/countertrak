-- GROUP BY WITH HAVING CLAUSES
-- Demonstrates specific GROUP BY operations with HAVING filters

-- Weapon performance grouped by type with effectiveness thresholds
SELECT 
    w.type AS weapon_type,
    COUNT(DISTINCT w.weapon_id) AS weapons_in_category,
    SUM(prs.round_kills) AS total_kills,
    COUNT(DISTINCT prs.round_number) AS rounds_used,
    ROUND(SUM(prs.round_kills)::numeric / NULLIF(COUNT(DISTINCT prs.round_number), 0), 2) AS avg_kills_per_round,
    MAX(prs.round_kills) AS max_kills_in_round
FROM 
    stats_weapon w
JOIN 
    stats_playerweapon pw ON w.weapon_id = pw.weapon_id
JOIN 
    stats_playerroundstate prs ON 
        pw.match_id = prs.match_id AND
        pw.round_number = prs.round_number AND
        pw.steam_account_id = prs.steam_account_id
WHERE 
    pw.state = 'active'
    AND prs.steam_account_id = ${steam_id}
GROUP BY 
    w.type
HAVING 
    COUNT(DISTINCT prs.round_number) >= 10  -- Only include weapon types used in at least 10 rounds
    AND SUM(prs.round_kills) >= 5  -- Only include weapon types with at least 5 kills
ORDER BY 
    avg_kills_per_round DESC;

-- Economic strategy grouping with effectiveness filters
SELECT 
    CASE 
        WHEN prs.equip_value < 1000 THEN 'Eco (< $1000)'
        WHEN prs.equip_value BETWEEN 1000 AND 2500 THEN 'Semi-Eco ($1000-$2500)'
        WHEN prs.equip_value BETWEEN 2501 AND 4000 THEN 'Semi-Buy ($2501-$4000)'
        WHEN prs.equip_value > 4000 THEN 'Full Buy (> $4000)'
    END AS buy_strategy,
    COUNT(*) AS rounds_used,
    ROUND(AVG(prs.round_kills), 2) AS avg_kills,
    ROUND(AVG(prs.money), 2) AS avg_remaining_money,
    SUM(CASE WHEN r.winning_team = prs.team THEN 1 ELSE 0 END) AS rounds_won,
    ROUND(
        SUM(CASE WHEN r.winning_team = prs.team THEN 1 ELSE 0 END)::numeric / 
        COUNT(*) * 100, 
    2) AS strategy_win_rate
FROM 
    stats_playerroundstate prs
JOIN 
    matches_round r ON 
        prs.match_id = r.match_id AND 
        prs.round_number = r.round_number
WHERE 
    prs.steam_account_id = ${steam_id}
GROUP BY 
    buy_strategy
HAVING 
    COUNT(*) >= 10  -- Only include strategies used in at least 10 rounds
    AND AVG(prs.round_kills) > 0  -- Only include strategies with some success
ORDER BY 
    strategy_win_rate DESC;
