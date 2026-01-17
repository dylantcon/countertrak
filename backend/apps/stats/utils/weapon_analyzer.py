from django.db import connection
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

def get_weapon_analysis(steam_id: str) -> List[Dict[Any, Any]]:
    """
    Performs advanced weapon analysis with precise kill attribution.
    
    This function uses raw SQL with window functions to accurately attribute kills
    to the weapons that were active when those kills occurred. The approach:
    
    1. Identifies when player kill counts increase (PlayerStateChanges CTE)
    2. Tracks which weapons were active at which times (ActiveWeapons CTE)
    3. Correlates kill increases with active weapons (WeaponKills CTE)
    4. Calculates usage statistics and effectiveness metrics
    
    Args:
        steam_id: The Steam ID of the player to analyze
        
    Returns:
        A list of dictionaries containing weapon statistics
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                -- ADVANCED WEAPON ANALYSIS QUERY
                -- This query performs temporal sequence analysis to attribute kills
                -- to the correct weapons based on which weapon was active when kills occurred.
                
                WITH PlayerStateChanges AS (
                    -- STEP 1: Identify points where round_kills increases
                    -- This CTE analyzes the PlayerRoundState table to find moments when
                    -- a player's kill count increases, indicating they got a kill.
                    -- 
                    -- The LAG window function compares the current round_kills with the
                    -- previous round_kills value (ordered by timestamp) to calculate the
                    -- kill_increase (how many kills were just added).
                    
                    SELECT 
                        prs1.match_id, 
                        prs1.round_number,
                        prs1.state_timestamp,
                        -- Calculate kill increase using LAG window function
                        -- This finds the exact moments when kills increased
                        prs1.round_kills - LAG(prs1.round_kills, 1, 0) OVER (
                            PARTITION BY prs1.match_id, prs1.round_number 
                            ORDER BY prs1.state_timestamp
                        ) AS kill_increase,
                        prs1.money
                    FROM stats_playerroundstate prs1
                    WHERE 
                        prs1.steam_account_id = %s
                        AND prs1.round_kills > 0  -- Only include states with kills
                ),
                
                ActiveWeapons AS (
                    -- STEP 2: Identify which weapon was active at each point in time
                    -- This CTE tracks which weapons were 'active' (being used) at which times.
                    -- 
                    -- We use ROW_NUMBER to identify unique weapon activations, avoiding
                    -- counting every state update as a separate usage instance.
                    
                    SELECT
                        pw.match_id,
                        pw.round_number,
                        pw.weapon_id,
                        pw.state_timestamp,
                        w.name AS weapon_name,
                        w.type AS weapon_type,
                        -- Rank each weapon state by timestamp within round
                        -- This helps identify distinct weapon activations
                        ROW_NUMBER() OVER (
                            PARTITION BY pw.match_id, pw.round_number, pw.weapon_id 
                            ORDER BY pw.state_timestamp
                        ) AS activation_rank
                    FROM stats_playerweapon pw
                    JOIN stats_weapon w ON pw.weapon_id = w.weapon_id
                    WHERE 
                        pw.steam_account_id = %s
                        AND pw.state = 'active'  -- Only include active weapons
                        -- Exclude non-weapon items like grenades, C4, etc.
                        AND w.type NOT IN ('Grenade', 'C4')
                        AND w.type IS NOT NULL
                        AND w.type != 'StackableItem'
                ),
                
                WeaponKills AS (
                    -- STEP 3: Join kills with active weapons to attribute kills correctly
                    -- This CTE correlates kills with active weapons based on timestamps.
                    --
                    -- We join PlayerStateChanges with ActiveWeapons where:
                    -- 1. They're in the same match and round
                    -- 2. The kill timestamp is >= the weapon activation timestamp
                    -- 3. There was an actual kill increase
                    --
                    -- This temporal relationship analysis is the key to attributing
                    -- kills to the correct weapons.
                    
                    SELECT
                        aw.weapon_id,
                        aw.weapon_name,
                        aw.weapon_type,
                        -- Count distinct rounds where this weapon was used
                        COUNT(DISTINCT CONCAT(aw.match_id, '-', aw.round_number)) AS rounds_used,
                        -- Count total state records (approximates usage frequency)
                        COUNT(aw.match_id) AS state_count,
                        -- Sum kill increases that occurred while this weapon was active
                        SUM(CASE WHEN psc.kill_increase > 0 THEN psc.kill_increase ELSE 0 END) AS total_kills,
                        -- Track money for economic analysis
                        SUM(psc.money) AS total_money
                    FROM ActiveWeapons aw
                    LEFT JOIN PlayerStateChanges psc ON 
                        -- Join on match and round
                        aw.match_id = psc.match_id 
                        AND aw.round_number = psc.round_number
                        -- The kill happened AFTER this weapon became active
                        AND psc.state_timestamp >= aw.state_timestamp
                        -- Only include actual kill increases
                        AND (psc.kill_increase > 0)
                    GROUP BY aw.weapon_id, aw.weapon_name, aw.weapon_type
                )
                
                -- STEP 4: Final output with calculated metrics
                -- This final query calculates performance metrics like:
                -- - Average kills per round
                -- - Average money during weapon usage
                -- - Overall weapon effectiveness
                
                SELECT
                    weapon_id,
                    weapon_name,
                    weapon_type,
                    rounds_used,
                    state_count,
                    total_kills,
                    -- Calculate average kills per round
                    CASE WHEN rounds_used > 0 THEN total_kills::float / rounds_used ELSE 0 END AS avg_kills,
                    -- Calculate average money during weapon usage
                    CASE WHEN state_count > 0 THEN total_money::float / state_count ELSE 0 END AS avg_money
                FROM WeaponKills
                ORDER BY state_count DESC;  -- Sort by usage frequency
            """, [steam_id, steam_id])
            
            # process the query results into a list of dictionaries
            # this makes the data easy to work with in django views
            weapon_analysis = []
            for row in cursor.fetchall():
                weapon_analysis.append({
                    'weapon_id': row[0],
                    'weapon__name': row[1],  # match the format from the old query
                    'weapon__type': row[2],  # match the format from the old query
                    'rounds_used': row[3],
                    'times_active': row[4],
                    'total_kills': row[5],
                    'avg_kills_when_active': row[6],
                    'avg_money': row[7]
                })
            
            return weapon_analysis
            
    except Exception as e:
        logger.error(f"Error in weapon analysis for {steam_id}: {str(e)}")
        # return empty list on error rather than crashing
        return []
