-- WEAPON PERFORMANCE ANALYSIS
-- Demonstrates SELECT-FROM-WHERE and JOIN operations

-- Basic weapon effectiveness by player (SELECT-FROM-WHERE, JOIN)
SELECT 
    w.name AS weapon_name,
    w.type AS weapon_type,
    COUNT(DISTINCT pw.match_id) AS times_used,
    SUM(prs.round_kills) AS total_kills_with_weapon,
    CASE 
        WHEN COUNT(pw.id) > 0 THEN ROUND(SUM(prs.round_kills)::numeric / COUNT(pw.id), 2)
        ELSE 0
    END AS kills_per_usage
FROM 
    stats_weapon w
JOIN 
    stats_playerweapon pw ON w.weapon_id = pw.weapon_id
JOIN 
    stats_playerroundstate prs ON 
        pw.player_round_state_id = prs.id
WHERE 
    pw.state = 'active'
    AND prs.steam_account_id = ${steam_id}
GROUP BY 
    w.name, w.type
ORDER BY 
    total_kills_with_weapon DESC;

-- Weapon performance by map (Multiple JOIN example)
SELECT 
    m.map_name,
    w.name AS weapon_name,
    COUNT(DISTINCT pw.match_id) AS match_count,
    SUM(prs.round_kills) AS total_kills,
    ROUND(AVG(prs.round_kills), 2) AS avg_kills_per_round
FROM 
    stats_weapon w
JOIN 
    stats_playerweapon pw ON w.weapon_id = pw.weapon_id
JOIN 
    stats_playerroundstate prs ON pw.player_round_state_id = prs.id
JOIN 
    matches_match m ON prs.match_id = m.match_id
WHERE 
    pw.state = 'active'
    AND prs.steam_account_id = ${steam_id}
GROUP BY 
    m.map_name, w.name
ORDER BY 
    m.map_name, total_kills DESC;
