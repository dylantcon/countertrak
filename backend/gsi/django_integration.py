# gsi/django_integration.py
import os
import django
import logging
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

logger = logging.getLogger('django_integration')

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
    Synchronous implementation of steam account check/creation.

    Args:
        steam_id: The Steam ID
        player_name: The player's name

    Returns:
        The auth token for the account
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
                # generate a unique auth token (this uses hardcoded for now)
                from apps.accounts.models import SteamAccount
                temp_account = SteamAccount(steam_id=steam_id)
                auth_token = temp_account.generate_auth_token()

                # create new account without a user_id for now
                cursor.execute(
                    """
                    INSERT INTO accounts_steamaccount (steam_id, player_name, auth_token, user_id)
                    VALUES (%s, %s, %s, NULL)
                    """,
                    [steam_id, player_name, auth_token]
                )
                logger.info(f"Created new steam account: {steam_id}")
                return auth_token
    except Exception as e:
        logger.error(f"Error ensuring steam account: {str(e)}")
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
                 money, equip_value, round_kills, state_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [
                    match_id, round_number, player_state.steam_id,
                    player_state.health, player_state.armor, player_state.money,
                    player_state.equip_value, player_state.round_kills,
                    state_time
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
    # first ensure the steam account exists
    await ensure_steam_account(player_state.steam_id, player_state.name)
    
    # create the player round state
    return await _create_player_round_state_sync(match_id, round_number, player_state)

async def batch_create_player_states(match_id: str, round_number: int,
                                  player_states: Dict[str, PlayerState]) -> Dict[str, int]:
    """
    Create multiple player states in a single transaction.
    ONLY creates player states - weapon states must be created separately.

    Args:
        match_id: The match ID
        round_number: The round number
        player_states: Dictionary of player states to persist

    Returns:
        Dictionary mapping steam_ids to their player_round_state_ids
    """
    try:
        results = {}

        for steam_id, player_state in player_states.items():
            # create player round state only
            player_round_state_id = await create_player_round_state(
                match_id, round_number, player_state
            )

            if player_round_state_id:
                # store result - no weapon creation here
                results[steam_id] = player_round_state_id

        logger.info(f"Batch created {len(results)} player states for match {match_id}, round {round_number}")
        return results
    except Exception as e:
        logger.error(f"Error batch creating player states: {str(e)}")
        return {}

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
                    # get weapon ID from name
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

async def batch_create_player_weapons(match_id: str, round_number: int,
                                    steam_id: str, weapon_states: Dict[str, WeaponState]) -> int:
    """
    Create weapon records directly using the compound key approach.

    Args:
        match_id: The match ID
        round_number: The round number
        steam_id: The steam ID of the weapon owner
        weapon_states: Dictionary of weapon states keyed by slot

    Returns:
        Number of weapon records created
    """
    try:
        if not weapon_states:
            logger.warning(f"No weapon states to persist for player {steam_id}")
            return 0

        # persist weapons directly
        weapon_count = await create_player_weapon_states(
            match_id, round_number, steam_id, weapon_states
        )

        logger.info(f"Created {weapon_count} weapon states for match {match_id}, round {round_number}, player {steam_id}")
        return weapon_count

    except Exception as e:
        logger.error(f"Error creating weapon states: {str(e)}")
        return 0

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
