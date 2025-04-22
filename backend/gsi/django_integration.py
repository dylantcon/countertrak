# gsi/django_integration.py
import os
import django
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.db import connection, transaction

# configure django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'countertrak.settings')
django.setup()

# import data classes for type annotations
from gsi.payloadextractor import MatchState, PlayerState, WeaponState, RoundState
from gsi.logging_service import get_colored_logger

logger = get_colored_logger('DJANGO_INTEGRATION', 'light_yellow')
conf_logger = get_colored_logger('DJANGO_INTEGRATION_BATCH', 'cyan')

def convert_unix_timestamp_to_datetime(unix_timestamp: int) -> datetime:
    """
    Converts a Unix timestamp (seconds since epoch) to a timezone-aware datetime object.
    
    Args:
        unix_timestamp: The Unix timestamp to convert
        
    Returns:
        A timezone-aware datetime object
    """
    return datetime.fromtimestamp(
        unix_timestamp,
        tz=timezone.get_current_timezone()
    )

#==============================================================================
# match operations
#==============================================================================

@sync_to_async
def _create_match_sync(match_state: MatchState, full_match_id: str = None) -> str:
    """
    Synchronous implementation of match creation.
    
    Args:
        match_state: The match state to persist
        
    Returns:
        match_id of the created match
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO matches_match
                (match_id, game_mode, map_name, start_timestamp, rounds_played, team_ct_score, team_t_score)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING match_id
                """,
                [
                    full_match_id,
                    match_state.mode,
                    match_state.map_name,
                    convert_unix_timestamp_to_datetime(match_state.timestamp),
                    match_state.round,
                    match_state.team_ct_score,
                    match_state.team_t_score
                ]
            )
            match_id = cursor.fetchone()[0]
            logger.info(f"Created new match record: {match_id}")
            return match_id
    except Exception as e:
        logger.error(f"Error creating match: {str(e)}")
        return None

async def create_match(match_state: MatchState, full_match_id: str = None) -> str:
    """
    Create a new match record.
    
    Args:
        match_state: The match state to persist
        
    Returns:
        match_id of the created match
    """
    return await _create_match_sync(match_state, full_match_id)

@sync_to_async
def _update_match_sync(match_id: str, match_state: MatchState) -> bool:
    """
    Synchronous implementation of match update.
    
    Args:
        match_id: The ID of the match to update
        match_state: The updated match state
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE matches_match
                SET game_mode = %s,
                    map_name = %s,
                    team_ct_score = %s,
                    team_t_score = %s,
                    rounds_played = %s
                WHERE match_id = %s
                """,
                [
                    match_state.mode,
                    match_state.map_name,
                    match_state.team_ct_score,
                    match_state.team_t_score,
                    match_state.round,
                    match_id
                ]
            )
            affected = cursor.rowcount
            if affected:
                logger.info(f"Updated match record: {match_id}")
            return affected > 0
    except Exception as e:
        logger.error(f"Error updating match: {str(e)}")
        return False

async def update_match(match_id: str, match_state: MatchState) -> bool:
    """
    Update an existing match record.
    
    Args:
        match_id: The ID of the match to update
        match_state: The updated match state
        
    Returns:
        True if update was successful, False otherwise
    """
    return await _update_match_sync(match_id, match_state)

@sync_to_async
def _complete_match_sync(match_id: str, ct_score: int, t_score: int, 
                         total_rounds: int, timestamp: int) -> bool:
    """
    Synchronous implementation of match completion.
    
    Args:
        match_id: The ID of the match to complete
        ct_score: Final CT team score
        t_score: Final T team score
        total_rounds: Total rounds played
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        end_timestamp = convert_unix_timestamp_to_datetime(timestamp)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE matches_match
                SET end_timestamp = %s,
                    rounds_played = %s,
                    team_ct_score = %s,
                    team_t_score = %s
                WHERE match_id = %s
                """,
                [end_timestamp, total_rounds, ct_score, t_score, match_id]
            )
            affected = cursor.rowcount
            if affected:
                logger.info(f"Completed match record: {match_id}")
            return affected > 0
    except Exception as e:
        logger.error(f"Error completing match: {str(e)}")
        return False

async def complete_match(match_id: str, ct_score: int, t_score: int, 
                         total_rounds: int, timestamp: int) -> bool:
    """
    Mark a match as completed and update final scores.
    
    Args:
        match_id: The ID of the match to complete
        ct_score: Final CT team score
        t_score: Final T team score
        total_rounds: Total rounds played
        
    Returns:
        True if update was successful, False otherwise
    """
    return await _complete_match_sync(match_id, ct_score, t_score, total_rounds, timestamp)

@sync_to_async
def _match_exists_sync(match_id: str) -> bool:
    """
    Synchronous implementation of match existence check.
    
    Args:
        match_id: The ID of the match to check
        
    Returns:
        True if match exists, False otherwise
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM matches_match WHERE match_id = %s",
                [match_id]
            )
            return cursor.fetchone()[0] > 0
    except Exception as e:
        logger.error(f"Error checking match existence: {str(e)}")
        return False

async def match_exists(match_id: str) -> bool:
    """
    Check if a match record exists.
    
    Args:
        match_id: The ID of the match to check
        
    Returns:
        True if match exists, False otherwise
    """
    return await _match_exists_sync(match_id)

#==============================================================================
# round operations
#==============================================================================
@sync_to_async
def _create_round_sync(match_id: str, round_number: int, phase: str, 
                     winning_team: Optional[str] = None, 
                     win_condition: Optional[str] = None,
                     timestamp: int = None) -> int:
    """
    Synchronous implementation of round creation.
    
    Args:
        match_id: The match ID this round belongs to
        round_number: The round number
        phase: The round phase
        winning_team: The winning team (if round is over)
        win_condition: How the round was won
        
    Returns:
        ID of the created round
    """
    try:
        state_time = convert_unix_timestamp_to_datetime(timestamp)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO matches_round
                (match_id, round_number, phase, timestamp, winning_team, win_condition)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [match_id, round_number, phase, state_time, winning_team, win_condition]
            )
            round_id = cursor.fetchone()[0]
            logger.info(f"Created round record for match {match_id}, round {round_number}")
            return round_id
    except Exception as e:
        logger.error(f"Error creating round: {str(e)}")
        return None

async def create_round(match_id: str, round_number: int, phase: str, 
                      winning_team: Optional[str] = None, 
                      win_condition: Optional[str] = None,
                      timestamp: int = None) -> int:
    """
    Create a new round record.
    
    Args:
        match_id: The match ID this round belongs to
        round_number: The round number
        phase: The round phase
        winning_team: The winning team (if round is over)
        win_condition: How the round was won
        
    Returns:
        ID of the created round
    """
    return await _create_round_sync(match_id, round_number, phase, winning_team, win_condition, timestamp)

@sync_to_async
def _update_round_winner_sync(match_id: str, round_number: int, 
                            winning_team: str, win_condition: str) -> bool:
    """
    Synchronous implementation of round winner update.
    
    Args:
        match_id: The match ID this round belongs to
        round_number: The round number
        winning_team: The winning team
        win_condition: How the round was won
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE matches_round
                SET winning_team = %s,
                    win_condition = %s,
                    phase = 'over'
                WHERE match_id = %s AND round_number = %s
                """,
                [winning_team, win_condition, match_id, round_number]
            )
            affected = cursor.rowcount
            if affected:
                logger.info(f"Updated round winner for match {match_id}, round {round_number}")
            return affected > 0
    except Exception as e:
        logger.error(f"Error updating round winner: {str(e)}")
        return False

async def update_round_winner(match_id: str, round_number: int, 
                            winning_team: str, win_condition: str) -> bool:
    """
    Update a round with winner information.
    
    Args:
        match_id: The match ID this round belongs to
        round_number: The round number
        winning_team: The winning team
        win_condition: How the round was won
        
    Returns:
        True if update was successful, False otherwise
    """
    return await _update_round_winner_sync(match_id, round_number, winning_team, win_condition)

@sync_to_async
def _round_exists_sync(match_id: str, round_number: int) -> bool:
    """
    Synchronous implementation of round existence check.
    
    Args:
        match_id: The match ID
        round_number: The round number
        
    Returns:
        True if round exists, False otherwise
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM matches_round 
                WHERE match_id = %s AND round_number = %s
                """,
                [match_id, round_number]
            )
            return cursor.fetchone()[0] > 0
    except Exception as e:
        logger.error(f"Error checking round existence: {str(e)}")
        return False

async def round_exists(match_id: str, round_number: int) -> bool:
    """
    Check if a round record exists.
    
    Args:
        match_id: The match ID
        round_number: The round number
        
    Returns:
        True if round exists, False otherwise
    """
    return await _round_exists_sync(match_id, round_number)

#==============================================================================
# steam account operations
#==============================================================================

@sync_to_async
def _ensure_steam_account_sync(steam_id: str, player_name: str) -> str:
    """
    Check if a steam account exists without creating it.

    Args:
        steam_id: The Steam ID
        player_name: The player's name

    Returns:
        The auth token if the account exists, None otherwise
    """
    try:
        with connection.cursor() as cursor:
            # check if account exists
            cursor.execute(
                "SELECT auth_token FROM accounts_steamaccount WHERE steam_id = %s",
                [steam_id]
            )
            result = cursor.fetchone()

            if result:
                # account exists, return auth token
                return result[0]
            else:
                # account doesn't exist, log warning and return None
                logger.warning(
                    f"Steam account {steam_id} ({player_name}) not found. " +
                     "User must register first."
                )
                return None
    except Exception as e:
        logger.error(f"Error checking steam account: {str(e)}")
        return None

async def ensure_steam_account(steam_id: str, player_name: str) -> str:
    """
    Ensure a steam account exists, creating it if necessary.
    
    Args:
        steam_id: The Steam ID
        player_name: The player's name
        
    Returns:
        The auth token for the account
    """
    return await _ensure_steam_account_sync(steam_id, player_name)

#==============================================================================
# player round state operations
#==============================================================================

@sync_to_async
def _create_player_round_state_sync(match_id: str, round_number: int, 
                                  player_state: PlayerState) -> int:
    """
    Synchronous implementation of player round state creation.
    
    Args:
        match_id: The match ID
        round_number: The round number
        player_state: The player state to persist
        
    Returns:
        ID of the created player round state
    """
    try:
        with connection.cursor() as cursor:
            # create timestamp from the player state or current time
            state_time = convert_unix_timestamp_to_datetime(player_state.state_timestamp)
            
            # insert new player state
            cursor.execute(
                """
                INSERT INTO stats_playerroundstate
                (match_id, round_number, steam_account_id, health, armor,
                 money, equip_value, round_kills, team, state_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [
                    match_id, round_number, player_state.steam_id,
                    player_state.health, player_state.armor, player_state.money,
                    player_state.equip_value, player_state.round_kills,
                    player_state.team, state_time
                ]
            )
            player_round_state_id = cursor.fetchone()[0]
            logger.debug(f"Created player state for {player_state.steam_id} in match {match_id}, round {round_number}")
            return player_round_state_id
    except Exception as e:
        logger.error(f"Error creating player round state: {str(e)}")
        return None

async def create_player_round_state(match_id: str, round_number: int, player_state: PlayerState) -> int:
    """
    Create a new player round state record.
    
    Args:
        match_id: The match ID
        round_number: The round number
        player_state: The player state to persist
        
    Returns:
        ID of the created player round state
    """
    # first check if the steam account exists
    auth_token = await ensure_steam_account(player_state.steam_id, player_state.name)

    if not auth_token:
        logger.info(
            f"Skipping player state creation for {player_state.steam_id} " +
             "- account not registered")
        return None
    
    # create the player round state
    return await _create_player_round_state_sync(match_id, round_number, player_state)

async def batch_create_player_states(match_id: str, round_number: int,
                                  player_states: List[PlayerState]) -> int:
    """
    Create multiple player states in a single transaction.
    ONLY creates player states - weapon states must be created separately.

    Args:
        match_id: The match ID
        round_number: The round number
        player_states: List of player states to persist

    Returns:
        Number of player states created
    """
    try:
        count = 0

        for player_state in player_states:
            # check if a duplicate record exists (if so, skip it)
            seen = await player_round_state_exists(match_id, round_number, player_state)
            if seen is True:
                continue

            # otherwise, create player round state
            player_round_state_id = await create_player_round_state(
                match_id, round_number, player_state
            )

            if player_round_state_id:
                count += 1

        conf_logger.info(f"Batch created {count} player states for match {match_id}, round {round_number}")
        return count
    except Exception as e:
        logger.error(f"Error batch creating player states: {str(e)}")
        return 0

@sync_to_async
def _player_round_state_exists_sync(match_id: str, round_number: int,
                                    player_state: PlayerState) -> bool:
    """
    Synchronous implementation. 

    Check to see if a given PlayerRoundState exists in the database records.
    """
    try:
        state_time = convert_unix_timestamp_to_datetime(player_state.state_timestamp) 
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM stats_playerroundstate
                WHERE
                    match_id = %s AND
                    round_number = %s AND
                    steam_account_id = %s AND
                    state_timestamp = %s
                """,
                [
                    match_id,
                    round_number,
                    player_state.steam_id,
                    state_time
                ]
            )
            return cursor.fetchone()[0] > 0
    except Exception as e:
        logger.error(f"Error checking round existence: {str(e)}")
        return False

async def player_round_state_exists(match_id: str, round_number: int,
                                    player_state: PlayerState) -> bool:
    """
    Check to see if a given PlayerRoundState exists in the database records.
    """
    return await _player_round_state_exists_sync(
        match_id, round_number, player_state
    )

#==============================================================================
# player weapons operations
#==============================================================================

@sync_to_async
def _create_player_weapon_states_sync(match_id: str, round_number: int,
                                    steam_id: str, weapons: Dict[str, WeaponState]) -> int:
    """
    Synchronous implementation of weapon state creation using compound key.
    Preserves the original timestamp from when the payload was received.

    Args:
        match_id: The match ID
        round_number: The round number
        steam_id: The steam ID of the weapon owner
        weapons: Dictionary of weapon states to persist
    """
    if not weapons:
        logger.warning(f"No weapons provided for player {steam_id}")
        return 0

    try:
        count = 0
        with connection.cursor() as cursor:
            # process each weapon
            for slot, weapon_state in weapons.items():
                try:
                    # get weapon id from name
                    cursor.execute(
                        "SELECT weapon_id FROM stats_weapon WHERE name = %s",
                        [weapon_state.name]
                    )
                    result = cursor.fetchone()
                    if not result:
                        logger.warning(f"Unknown weapon: {weapon_state.name}")
                        continue
                    weapon_id = result[0]

                    # convert the unix timestamp from weapon_state to a datetime object
                    state_time = convert_unix_timestamp_to_datetime(weapon_state.state_timestamp)

                    # insert using the original timestamp
                    cursor.execute(
                        """
                        INSERT INTO stats_playerweapon
                        (match_id, round_number, steam_account_id, weapon_id,
                         state, ammo_clip, ammo_reserve, paintkit, state_timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        [
                            match_id,
                            round_number,
                            steam_id,
                            weapon_id,
                            weapon_state.state,
                            weapon_state.ammo_clip,
                            weapon_state.ammo_reserve,
                            weapon_state.paintkit,
                            state_time
                        ]
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"Error creating weapon state for {weapon_state.name}: {str(e)}")

            return count
    except Exception as e:
        logger.error(f"Error creating weapon states: {str(e)}")
        return 0

async def create_player_weapon_states(match_id: str, round_number: str,
                                    steam_id: str, weapons: Dict[str, WeaponState]) -> int:
    """
    Create weapon states directly using the compound key components.

    Args:
        match_id: The match ID
        round_number: The round number
        steam_id: The steam ID of the weapon owner
        weapons: Dictionary of weapon states

    Returns:
        Number of weapon states created
    """
    return await _create_player_weapon_states_sync(match_id, round_number, steam_id, weapons)

async def batch_create_player_weapons(match_id: str, round_number: int, steam_id: str,
                                      weapon_states_history: List[Dict[str, WeaponState]]) -> int:
    """
    Create weapon records from a list of weapon state dictionaries.
    """
    try:
        if not weapon_states_history:
            logger.warning(f"No weapon states history to persist for player {steam_id} in match {match_id}, round {round_number}")
            return 0

        total_count = 0

        # Process each dictionary (snapshot) in the history list
        for weapon_states_dict in weapon_states_history:
            if not weapon_states_dict:
                continue
                
            weapons_to_create = {}
            
            # Check each weapon in the dictionary
            for slot, weapon_state in weapon_states_dict.items():
                # Get weapon ID from name - using our async helper
                weapon_id = await get_weapon_id_by_name(weapon_state.name)
                
                if not weapon_id:
                    logger.warning(f"Unknown weapon: {weapon_state.name}")
                    continue
                    
                # Check if this weapon record already exists
                seen = await player_weapon_exists(
                    match_id, round_number, steam_id, weapon_id, weapon_state.state_timestamp
                )
                
                if seen:
                    logger.debug(f"Skipping duplicate weapon record for {weapon_state.name}")
                    continue
                    
                # Add to weapons to create
                weapons_to_create[slot] = weapon_state
            
            # Create only weapons that don't exist yet
            if weapons_to_create:
                weapon_count = await create_player_weapon_states(
                    match_id, round_number, steam_id, weapons_to_create
                )
                total_count += weapon_count

        conf_logger.info(f"Created {total_count} weapon states for player {steam_id} in match {match_id}, round {round_number}")
        return total_count

    except Exception as e:
        logger.error(f"Error creating weapon states history: {str(e)}")
        return 0

@sync_to_async
def _player_weapon_exists_sync(match_id: str, round_number: int, 
                              steam_id: str, weapon_id: int, 
                              state_timestamp: int) -> bool:
    """
    Synchronous implementation. 
    Check if a PlayerWeapon record already exists in the database.
    """
    try:
        state_time = convert_unix_timestamp_to_datetime(state_timestamp) 
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM stats_playerweapon
                WHERE
                    match_id = %s AND
                    round_number = %s AND
                    steam_account_id = %s AND
                    weapon_id = %s AND
                    state_timestamp = %s
                """,
                [
                    match_id,
                    round_number,
                    steam_id,
                    weapon_id,
                    state_time
                ]
            )
            return cursor.fetchone()[0] > 0
    except Exception as e:
        logger.error(f"Error checking weapon record existence: {str(e)}")
        return False

async def player_weapon_exists(match_id: str, round_number: int,
                              steam_id: str, weapon_id: int,
                              state_timestamp: int) -> bool:
    """
    Check if a PlayerWeapon record already exists in the database.
    """
    return await _player_weapon_exists_sync(
        match_id, round_number, steam_id, weapon_id, state_timestamp
    )

@sync_to_async
def _get_weapon_id_by_name_sync(weapon_name: str) -> Optional[int]:
    """Synchronous implementation to get weapon ID by name"""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT weapon_id FROM stats_weapon WHERE name = %s",
                [weapon_name]
            )
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting weapon ID for {weapon_name}: {str(e)}")
        return None

async def get_weapon_id_by_name(weapon_name: str) -> Optional[int]:
    """Get weapon ID by name asynchronously"""
    return await _get_weapon_id_by_name_sync(weapon_name)

#==============================================================================
# player match statistics operations
#==============================================================================

@sync_to_async
def _update_player_match_stats_sync(match_id: str, player_state: PlayerState) -> bool:
    """
    Synchronous implementation of player match stats update.
    
    Args:
        match_id: The match ID
        player_state: The player state containing match statistics
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stats_playermatchstat
                (steam_account_id, match_id, kills, deaths, assists, mvps, score)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (steam_account_id, match_id)
                DO UPDATE SET
                    kills = EXCLUDED.kills,
                    deaths = EXCLUDED.deaths,
                    assists = EXCLUDED.assists,
                    mvps = EXCLUDED.mvps,
                    score = EXCLUDED.score
                """,
                [
                    player_state.steam_id, match_id,
                    player_state.match_kills, player_state.match_deaths,
                    player_state.match_assists, player_state.match_mvps,
                    player_state.match_score
                ]
            )
            logger.debug(f"Updated match stats for player {player_state.steam_id} in match {match_id}")
            return True
    except Exception as e:
        logger.error(f"Error updating player match stats: {str(e)}")
        return False

async def update_player_match_stats(match_id: str, player_state: PlayerState) -> bool:
    """
    Update a player's match statistics.
    
    Unlike player states, match stats represent cumulative totals and are updated.
    
    Args:
        match_id: The match ID
        player_state: The player state containing match statistics
        
    Returns:
        True if update was successful, False otherwise
    """
    return await _update_player_match_stats_sync(match_id, player_state)
