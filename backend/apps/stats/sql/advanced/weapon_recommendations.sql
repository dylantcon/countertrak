-- ADVANCED WEAPON RECOMMENDATIONS
-- Demonstrates advanced analytics for our unique performance pattern recognition

-- Weapon effectiveness by map with performance scoring
WITH weapon_performance AS (
    SELECT 
        m.map_name,
        w.name AS weapon_name,
        w.type AS weapon_type,
        COUNT(DISTINCT pw.match_id) AS matches_used,
        SUM(prs.round_kills) AS total_kills,
        COUNT(DISTINCT CASE WHEN prs.round_kills > 0 THEN prs.round_number ELSE NULL END) AS rounds_with_kills,
        COUNT(DISTINCT prs.round_number) AS total_rounds_used,
        -- Performance metrics
        ROUND(SUM(prs.round_kills)::numeric / NULLIF(COUNT(DISTINCT prs.round_number), 0), 3) AS kills_per_round,
        ROUND(COUNT(DISTINCT CASE WHEN prs.round_kills > 0 THEN prs.round_number ELSE NULL END)::numeric / 
              NULLIF(COUNT(DISTINCT prs.round_number), 0), 3) AS kill_consistency,
        -- Economic efficiency
        ROUND(SUM(prs.round_kills)::numeric / NULLIF(SUM(prs.equip_value)/1000, 0), 3) AS kills_per_1000_spent
    FROM 
        stats_weapon w
    JOIN 
        stats_playerweapon pw ON w.weapon_id = pw.weapon_id
    JOIN 
        stats_playerroundstate prs ON
		pw.match_id = prs.match_id AND
        	pw.round_number = prs.round_number AND
        	pw.steam_account_id = prs.steam_account_id
    JOIN 
        matches_match m ON prs.match_id = m.match_id
    JOIN 
        stats_playermatchstat pms ON 
            prs.match_id = pms.match_id AND 
            prs.steam_account_id = pms.steam_account_id
    WHERE 
        pw.state = 'active'
        AND prs.steam_account_id = ${steam_id}
        AND w.type NOT IN ('Knife', 'Grenade', 'C4', 'Other')
    GROUP BY 
        m.map_name, w.name, w.type
    HAVING 
        COUNT(DISTINCT prs.round_number) >= 5  -- Only include weapons with sufficient usage
)
SELECT 
    map_name,
    weapon_name,
    weapon_type,
    matches_used,
    total_kills,
    kills_per_round,
    kill_consistency,
    kills_per_1000_spent,
    -- Calculate optimal weapon score (advanced weighting algorithm)
    ROUND(
        (kills_per_round * 0.4) + 
        (kill_consistency * 0.3) + 
        (kills_per_1000_spent * 0.3)
    , 3) AS weapon_effectiveness_score,
    -- Generate recommendation tier
    CASE 
        WHEN kills_per_round >= 0.75 AND kill_consistency >= 0.5 THEN 'S-Tier'
        WHEN kills_per_round >= 0.5 AND kill_consistency >= 0.4 THEN 'A-Tier'
        WHEN kills_per_round >= 0.3 AND kill_consistency >= 0.3 THEN 'B-Tier'
        WHEN kills_per_round >= 0.2 THEN 'C-Tier'
        ELSE 'D-Tier'
    END AS recommendation_tier
FROM 
    weapon_performance
ORDER BY 
    map_name, weapon_effectiveness_score DESC;
