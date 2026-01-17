-- WEAPON PERFORMANCE ANALYSIS
-- Demonstrates SELECT-FROM-WHERE and JOIN operations with accurate kill attribution

-- Basic weapon effectiveness by player (SELECT-FROM-WHERE, JOIN)
WITH WeaponRoundStats AS (
    -- First get one row per weapon per round with distinct round data
    SELECT DISTINCT ON (pw.match_id, pw.round_number, w.weapon_id)
        w.name AS weapon_name,
        w.type AS weapon_type,
        pw.match_id,
        pw.round_number,
        prs.round_kills,
        -- Calculate approximate kill share based on weapon prevalence
        -- This distributes kills proportionally among active weapons
        CASE 
            WHEN weapon_count.active_weapons > 0 
            THEN ROUND(prs.round_kills::numeric / weapon_count.active_weapons, 2)
            ELSE 0 
        END AS estimated_kills
    FROM 
        stats_weapon w
    JOIN 
        stats_playerweapon pw ON w.weapon_id = pw.weapon_id
    JOIN 
        stats_playerroundstate prs ON 
            pw.match_id = prs.match_id AND
            pw.round_number = prs.round_number AND
            pw.steam_account_id = prs.steam_account_id
    -- Count active weapons per round to distribute kills
    JOIN (
        SELECT 
            match_id, 
            round_number, 
            steam_account_id,
            COUNT(DISTINCT weapon_id) AS active_weapons
        FROM 
            stats_playerweapon
        WHERE 
            state = 'active'
        GROUP BY 
            match_id, round_number, steam_account_id
    ) AS weapon_count ON 
        pw.match_id = weapon_count.match_id AND
        pw.round_number = weapon_count.round_number AND
        pw.steam_account_id = weapon_count.steam_account_id
    WHERE 
        pw.state = 'active'
        AND prs.steam_account_id = ${steam_id}
    ORDER BY 
        pw.match_id, pw.round_number, w.weapon_id
)

-- Summarize weapon performance
SELECT 
    weapon_name,
    weapon_type,
    COUNT(DISTINCT match_id) AS matches_used,
    COUNT(DISTINCT (match_id, round_number)) AS rounds_used,
    ROUND(SUM(estimated_kills), 0) AS estimated_total_kills,
    CASE 
        WHEN COUNT(DISTINCT (match_id, round_number)) > 0 
        THEN ROUND(SUM(estimated_kills)::numeric / COUNT(DISTINCT (match_id, round_number)), 2)
        ELSE 0
    END AS kills_per_round
FROM 
    WeaponRoundStats
GROUP BY 
    weapon_name, weapon_type
ORDER BY 
    estimated_total_kills DESC;

-- Weapon performance by map (Multiple JOIN example)
WITH MapWeaponStats AS (
    -- Get distinct weapon usage per round per map
    SELECT DISTINCT ON (m.map_name, pw.match_id, pw.round_number, w.weapon_id)
        m.map_name,
        w.name AS weapon_name,
        pw.match_id,
        pw.round_number,
        prs.round_kills,
        -- Calculate approximate kill share based on weapon prevalence
        CASE 
            WHEN weapon_count.active_weapons > 0 
            THEN ROUND(prs.round_kills::numeric / weapon_count.active_weapons, 2)
            ELSE 0 
        END AS estimated_kills
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
    -- Count active weapons per round to distribute kills
    JOIN (
        SELECT 
            match_id, 
            round_number, 
            steam_account_id,
            COUNT(DISTINCT weapon_id) AS active_weapons
        FROM 
            stats_playerweapon
        WHERE 
            state = 'active'
        GROUP BY 
            match_id, round_number, steam_account_id
    ) AS weapon_count ON 
        pw.match_id = weapon_count.match_id AND
        pw.round_number = weapon_count.round_number AND
        pw.steam_account_id = weapon_count.steam_account_id
    WHERE 
        pw.state = 'active'
        AND prs.steam_account_id = ${steam_id}
    ORDER BY 
        m.map_name, pw.match_id, pw.round_number, w.weapon_id
)

-- Summarize by map and weapon
SELECT 
    map_name,
    weapon_name,
    COUNT(DISTINCT match_id) AS matches_used,
    COUNT(DISTINCT (match_id, round_number)) AS rounds_used,
    ROUND(SUM(estimated_kills), 0) AS estimated_total_kills,
    CASE 
        WHEN COUNT(DISTINCT (match_id, round_number)) > 0 
        THEN ROUND(SUM(estimated_kills)::numeric / COUNT(DISTINCT (match_id, round_number)), 2)
        ELSE 0
    END AS kills_per_round
FROM 
    MapWeaponStats
GROUP BY 
    map_name, weapon_name
ORDER BY 
    map_name, estimated_total_kills DESC;
