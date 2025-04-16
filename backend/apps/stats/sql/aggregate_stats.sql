-- AGGREGATE STATISTICS QUERIES
-- Demonstrates various aggregate functions: COUNT, SUM, AVG, MIN, MAX, STDDEV

-- Basic aggregate statistics
SELECT 
    COUNT(DISTINCT m.match_id) AS total_matches,
    COUNT(DISTINCT m.map_name) AS unique_maps_played,
    SUM(pms.kills) AS total_kills,
    SUM(pms.deaths) AS total_deaths,
    SUM(pms.assists) AS total_assists,
    SUM(pms.mvps) AS total_mvps,
    ROUND(AVG(pms.kills), 2) AS avg_kills_per_match,
    ROUND(AVG(pms.deaths), 2) AS avg_deaths_per_match,
    MAX(pms.kills) AS highest_kills,
    MIN(pms.deaths) AS lowest_deaths,
    ROUND(SUM(pms.kills)::numeric / NULLIF(SUM(pms.deaths), 0), 2) AS overall_kd_ratio
FROM 
    stats_playermatchstat pms
JOIN 
    matches_match m ON pms.match_id = m.match_id
WHERE 
    pms.steam_account_id = ${steam_id};

-- Advanced aggregate statistics with standard deviation
SELECT 
    m.map_name,
    COUNT(DISTINCT m.match_id) AS matches_played,
    ROUND(AVG(pms.kills), 2) AS avg_kills,
    ROUND(AVG(pms.deaths), 2) AS avg_deaths,
    ROUND(STDDEV(pms.kills), 2) AS kills_stddev,
    ROUND(STDDEV(pms.deaths), 2) AS deaths_stddev,
    ROUND(VARIANCE(pms.kills), 2) AS kills_variance,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pms.kills), 2) AS median_kills
FROM 
    stats_playermatchstat pms
JOIN 
    matches_match m ON pms.match_id = m.match_id
WHERE 
    pms.steam_account_id = ${steam_id}
GROUP BY 
    m.map_name
HAVING 
    COUNT(DISTINCT m.match_id) >= 3
ORDER BY 
    matches_played DESC;
