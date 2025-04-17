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
from gsi.payloadextractor import MatchState, PlayerState, WeaponState

logger = logging.getLogger('django_integration')

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
                    timezone.now(),  # use timezone-aware datetime
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
def _complete_match_sync(match_id: str, ct_score: int, t_score: int, total_rounds: int) -> bool:
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
        end_timestamp = timezone.now()
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

async def complete_match(match_id: str, ct_score: int, t_score: int, total_rounds: int) -> bool:
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
    return await _complete_match_sync(match_id, ct_score, t_score, total_rounds)

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
                     win_condition: Optional[str] = None) -> int:
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
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO matches_round
                (match_id, round_number, phase, timestamp, winning_team, win_condition)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [match_id, round_number, phase, timezone.now(), winning_team, win_condition]
            )
            round_id = cursor.fetchone()[0]
            logger.info(f"Created round record for match {match_id}, round {round_number}")
            return round_id
    except Exception as e:
        logger.error(f"Error creating round: {str(e)}")
        return None

async def create_round(match_id: str, round_number: int, phase: str, 
                      winning_team: Optional[str] = None, 
                      win_condition: Optional[str] = None) -> int:
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
    return await _create_round_sync(match_id, round_number, phase, winning_team, win_condition)

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
                # generate a unique auth token
                from apps.accounts.models import SteamAccount
                temp_account = SteamAccount(steam_id=steam_id)
                auth_token = temp_account.generate_auth_token()
                
                # create new account
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
# player state operations
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
            state_time = datetime.fromtimestamp(player_state.state_timestamp)
            
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

@sync_to_async
def _create_player_weapon_states_sync(player_round_state_id: int, 
                                    weapons: Dict[str, WeaponState]) -> int:
    """
    Synchronous implementation of player weapon state creation.
    
    Args:
        player_round_state_id: The player round state ID these weapons belong to
        weapons: Dictionary of weapon states to persist
        
    Returns:
        Number of weapon records created
    """
    try:
        count = 0
        with connection.cursor() as cursor:
            # process each weapon
            for weapon_slot, weapon_state in weapons.items():
                weapon_id = int(weapon_slot) if weapon_slot.isdigit() else 0
                
                # ensure weapon exists in weapons table
                cursor.execute(
                    """
                    INSERT INTO stats_weapon (weapon_id, name, type, max_clip)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (weapon_id) DO NOTHING
                    """,
                    [
                        weapon_id,
                        weapon_state.name,
                        weapon_state.type,
                        weapon_state.ammo_clip_max
                    ]
                )
                
                # create timestamp from the weapon state
                state_time = datetime.fromtimestamp(weapon_state.state_timestamp)
                
                # create new weapon state record
                cursor.execute(
                    """
                    INSERT INTO stats_playerweapon
                    (player_round_state_id, weapon_id, state, ammo_clip,
                     ammo_reserve, paintkit, state_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        player_round_state_id,
                        weapon_id,
                        weapon_state.state,
                        weapon_state.ammo_clip,
                        weapon_state.ammo_reserve,
                        weapon_state.paintkit,
                        state_time
                    ]
                )
                count += 1
            
            logger.debug(f"Created {count} weapon states for player round state {player_round_state_id}")
            return count
    except Exception as e:
        logger.error(f"Error creating player weapon states: {str(e)}")
        return 0

async def create_player_weapon_states(player_round_state_id: int, 
                                    weapons: Dict[str, WeaponState]) -> int:
    """
    Create player weapon state records for all weapons.
    
    Args:
        player_round_state_id: The player round state ID these weapons belong to
        weapons: Dictionary of weapon states to persist
        
    Returns:
        Number of weapon records created
    """
    return await _create_player_weapon_states_sync(player_round_state_id, weapons)

async def batch_create_player_states(match_id: str, round_number: int, 
                                  player_states: Dict[str, PlayerState]) -> Dict[str, int]:
    """
    Create multiple player states in a single transaction.
    
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
            # create player round state
            player_round_state_id = await create_player_round_state(
                match_id, round_number, player_state
            )
            
            if player_round_state_id:
                # create associated weapon states
                await create_player_weapon_states(
                    player_round_state_id, player_state.weapons
                )
                
                # store result
                results[steam_id] = player_round_state_id
        
        logger.info(f"Batch created {len(results)} player states for match {match_id}, round {round_number}")
        return results
    except Exception as e:
        logger.error(f"Error batch creating player states: {str(e)}")
        return {}

#==============================================================================
# match statistics operations
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

async def batch_update_player_match_stats(match_id: str, 
                                       player_states: Dict[str, PlayerState]) -> int:
    """
    Update multiple players' match statistics.
    
    Args:
        match_id: The match ID
        player_states: Dictionary of player states containing match statistics
        
    Returns:
        Number of player records updated
    """
    try:
        count = 0
        
        for steam_id, player_state in player_states.items():
            success = await update_player_match_stats(match_id, player_state)
            if success:
                count += 1
        
        logger.info(f"Batch updated {count} player match stats for match {match_id}")
        return count
    except Exception as e:
        logger.error(f"Error batch updating player match stats: {str(e)}")
        return 0
