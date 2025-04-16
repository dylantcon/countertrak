-- DATA MANIPULATION OPERATIONS
-- Demonstrates INSERT, UPDATE, DELETE operations

-- INSERT operation - Add a new match
INSERT INTO matches_match (
    match_id,
    game_mode,
    map_name,
    start_timestamp,
    end_timestamp,
    rounds_played,
    team_ct_score,
    team_t_score
) VALUES (
    '${new_match_id}',  -- Parameter: UUID for new match
    '${game_mode}',     -- Parameter: Game mode (e.g., 'competitive')
    '${map_name}',      -- Parameter: Map name (e.g., 'de_dust2')
    NOW(),              -- Current timestamp for start
    NULL,               -- End timestamp null (match in progress)
    0,                  -- Initial rounds played
    0,                  -- Initial CT score
    0                   -- Initial T score
)
RETURNING match_id;

-- UPDATE operation - Update match scores
UPDATE matches_match
SET 
    team_ct_score = ${ct_score},
    team_t_score = ${t_score},
    rounds_played = ${rounds_played},
    end_timestamp = CASE WHEN ${is_completed} THEN NOW() ELSE end_timestamp END
WHERE 
    match_id = '${match_id}'
RETURNING match_id, team_ct_score, team_t_score, rounds_played;

-- UPDATE operation - Update player match stats
UPDATE stats_playermatchstat
SET 
    kills = ${kills},
    deaths = ${deaths},
    assists = ${assists},
    mvps = ${mvps},
    score = ${score}
WHERE 
    steam_account_id = '${steam_id}'
    AND match_id = '${match_id}'
RETURNING steam_account_id, match_id, kills, deaths, assists;

-- DELETE operation - Remove a specific player round state
DELETE FROM stats_playerroundstate
WHERE 
    match_id = '${match_id}'
    AND round_number = ${round_number}
    AND steam_account_id = '${steam_id}'
RETURNING match_id, round_number, steam_account_id;
