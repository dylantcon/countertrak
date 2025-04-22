import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Set, Any, Tuple
from datetime import datetime
from django.utils import timezone

# utilize our custom logger service
from gsi.logging_service import payload_logger as logger
from gsi.logging_service import get_colored_logger

# import utility functions
from gsi.utils import extract_base_match_id

debug = get_colored_logger('payload_debug', 'light_purple')

@dataclass
class MatchState:
    """
    Represents the state of a CS2 match.
    Maps to the 'matches_match' table in our database.
    """
    match_id: str  # base format: map_name_game_mode_steamid
    mode: str      # game mode (competitive, casual, etc.)
    map_name: str  # map name (de_dust2, de_mirage, etc.)
    phase: str     # match phase (warmup, live, gameover)
    round: int     # current round number
    team_ct_score: int  # ct team score
    team_t_score: int   # t team score
    timestamp: int      # timestamp from payload

@dataclass
class WeaponState:
    """
    Represents the state of a weapon.
    Maps to the 'stats_playerweapon' table when associated with a player.
    """
    name: str      # weapon name (weapon_ak47, etc.)
    type: str      # weapon type from payload (rifle, pistol, etc.)
    state: str     # weapon state (active, holstered)
    ammo_clip: Optional[int] = None     # current ammo in clip
    ammo_clip_max: Optional[int] = None # max ammo in clip
    ammo_reserve: Optional[int] = None  # reserve ammo
    paintkit: str = "default"           # weapon skin
    steam_id: Optional[str] = None      # owner's steam ID
    state_timestamp: int = field(default_factory=lambda: int(time.time()))  # unix timestamp

@dataclass
class RoundState:
    """
    Represents the state of a round.
    Maps to the 'matches_round' table in our database.
    """
    round_number: int                # round number
    phase: str                       # round phase (freezetime, live, over)
    win_team: Optional[str] = None   # winning team (ct, t, or none if ongoing)
    bomb_state: Optional[str] = None # bomb state (planted, exploded, defused, or none)
    win_condition: Optional[str] = None  # how the round was won
    timestamp: int = field(default_factory=lambda: int(time.time()))  # unix timestamp

@dataclass
class PlayerState:
    """
    Represents the state of a player.
    Maps to both 'stats_playerroundstate' and 'stats_playermatchstat' tables.
    """
    steam_id: str           # player's steam id
    name: str               # player's name
    team: str               # player's team (ct, t, spec)
    health: int             # current health
    armor: int              # current armor
    money: int              # current money
    equip_value: int        # equipment value
    round_kills: int        # kills in current round
    match_kills: int        # total kills in match
    match_deaths: int       # total deaths in match
    match_assists: int      # total assists in match
    match_mvps: int         # total mvps in match
    match_score: int        # total score in match
    state_timestamp: int = field(default_factory=lambda: int(time.time()))  # unix timestamp

class PayloadExtractor:
    """
    Extracts and tracks data from CS2 GSI payloads.
    Maintains state between updates and provides structured access to game data.
    
    This class is the central component for all payload processing, following
    the Single Responsibility Principle by focusing exclusively on extracting
    and tracking state from raw payloads.
    """

    def __init__(self):
        # current state tracking
        self.current_match: Optional[MatchState] = None
        self.player_states: Dict[str, PlayerState] = {}
        self.current_round: Optional[RoundState] = None
        self.weapon_states: Dict[str, WeaponState] = {}
        
        # historical data tracking
        self.previous_round_state = RoundState
        self.round_history: Dict[int, RoundState] = {}  # map round_number to roundstate
        self.processed_rounds: Set[int] = set()         # track which rounds have been processed
        
        logger.info("PayloadExtractor initialized")

    def _extract_timestamp(self, payload: Dict) -> int:
        """
        Generate a consistent server-side timestamp for all state objects.

        Using server timestamps ensures all events use the same time source,
        which is critical for accurate temporal relationship analysis.

        Args:
            payload: The GSI payload (no longer used for timestamp)

        Returns:
            Unix timestamp (seconds since epoch)
        """
        # always use server timestamp for consistency
        return int(timezone.now().timestamp())

    def process_payload(self, payload: Dict) -> Dict[str, Any]:
        """
        Single entry point for processing a complete GSI payload.
        
        This method centralizes all extraction and state change detection,
        ensuring consistent timestamp usage and proper state tracking.
        
        Args:
            payload: The raw GSI payload from CS2
            
        Returns:
            Dictionary containing all extracted states and detected changes
        """
        # extract timestamp once at the beginning
        timestamp = self._extract_timestamp(payload)
        
        # extract all state components with the same timestamp
        match_state = self.extract_match_state(payload, timestamp)
        player_state = self.extract_player_state(payload, timestamp)
        round_state = self.extract_round_state(payload, timestamp)
        weapon_states = self.extract_all_weapons(payload, timestamp)
        
        # detect state changes before updating internal state
        changes = self._detect_state_changes(
            payload, match_state, player_state, round_state, weapon_states
        )
        
        # update internal state
        self._update_internal_state(match_state, player_state, round_state, weapon_states)
        
        # return a complete result with all states and changes
        return {
            'timestamp': timestamp,
            'match_state': match_state,
            'player_state': player_state, 
            'round_state': round_state,
            'weapon_states': weapon_states,
            'changes': changes
        }

    def extract_match_state(self, payload: Dict, timestamp: int) -> Optional[MatchState]:
        """
        Extract match state from a GSI payload.
        
        Args:
            payload: The GSI payload
            timestamp: Timestamp to use for this state
            
        Returns:
            A MatchState object, or None if match data couldn't be extracted
        """
        if 'map' not in payload or 'provider' not in payload:
            return None
            
        map_data = payload['map']
        provider_data = payload['provider']

        # use centralized utility function to get base_match_id
        base_match_id = extract_base_match_id(payload)
        if not base_match_id:
            return None

        # get raw round number from map payload portion
        raw_round = map_data.get('round', 0)

        # add 1 to convert from zero-indexed to one-indexed
        adjusted_round = raw_round + 1

        # return full match state with the provided timestamp
        return MatchState(
            match_id=base_match_id,
            mode=map_data.get('mode', 'casual'),
            map_name=map_data.get('name', 'unknown_map'),
            phase=map_data.get('phase', 'unknown'),
            round=adjusted_round,
            team_ct_score=map_data.get('team_ct', {}).get('score', 0),
            team_t_score=map_data.get('team_t', {}).get('score', 0),
            timestamp=timestamp
        )

    def extract_round_state(self, payload: Dict, timestamp: int) -> Optional[RoundState]:
        """
        Extract round state information from a GSI payload.
        
        Args:
            payload: The GSI payload
            timestamp: Timestamp to use for this state
            
        Returns:
            A RoundState object, or None if round data couldn't be extracted
        """
        if 'round' not in payload or 'map' not in payload:
            return None
                
        round_data = payload.get('round', {})
        map_data = payload.get('map', {})

        
        # log raw round data for debugging
        raw_round_number = map_data.get('round', 0)
        ct_score = map_data.get('team_ct', {}).get('score', 0)
        t_score = map_data.get('team_t', {}).get('score', 0)
        
        # add 1 to payload round number to account for zero-indexing
        round_number = raw_round_number + 1
        
        # extract round phase and other properties
        phase = round_data.get('phase', 'unknown')
        win_team = round_data.get('win_team')
        bomb_state = round_data.get('bomb')
        
        # determine win condition based on bomb state
        win_condition = None
        if phase == 'over' and win_team:
            if bomb_state == 'exploded':
                win_condition = 'bomb_exploded'
            elif bomb_state == 'defused':
                win_condition = 'bomb_defused'
            else:
                win_condition = 'elimination'  # default for round ending with a winner
        
        return RoundState(
            round_number=round_number,
            phase=phase,
            win_team=win_team,
            bomb_state=bomb_state,
            win_condition=win_condition,
            timestamp=timestamp
        )

    def extract_weapon_state(self, weapon_data: Dict, timestamp: int) -> WeaponState:
        """
        Extract weapon state from weapon data.
        
        Args:
            weapon_data: Weapon data from the GSI payload
            timestamp: Timestamp to use for this state
            
        Returns:
            A WeaponState object
        """
        return WeaponState(
            name=weapon_data.get("name", "unknown_weapon"),
            type=weapon_data.get("type", "Other"),
            state=weapon_data.get("state", "unknown"),
            ammo_clip=weapon_data.get("ammo_clip"),
            ammo_clip_max=weapon_data.get("ammo_clip_max"),
            ammo_reserve=weapon_data.get("ammo_reserve"),
            paintkit=weapon_data.get("paintkit", "default"),
            steam_id=weapon_data.get("steam_id"),
            state_timestamp=timestamp
        )

    def extract_all_weapons(self, payload: Dict, timestamp: int) -> Dict[str, WeaponState]:
        """
        Extract all weapon states from a payload.

        Args:
            payload: The GSI payload
            timestamp: Timestamp to use for this state

        Returns:
            Dictionary of weapon states, keyed by slot
        """
        weapons = {}

        if 'player' not in payload or 'weapons' not in payload['player']:
            return weapons

        player_steam_id = payload.get('player', {}).get('steamid')
        weapons_data = payload['player'].get('weapons', {})

        # process each weapon
        for slot, weapon_data in weapons_data.items():
            # validate weapon data
            if not isinstance(weapon_data, dict) or 'name' not in weapon_data:
                logger.warning(f"Skipping invalid weapon data for slot {slot}")
                continue

            # use existing extract_weapon_state method
            weapon = self.extract_weapon_state(weapon_data, timestamp)
            weapon.steam_id = player_steam_id
            weapons[slot] = weapon

        return weapons

    def extract_player_state(self, payload: Dict, timestamp: int) -> Optional[PlayerState]:
        """
        Extract player state from a GSI payload.

        Args:
            payload: The GSI payload
            timestamp: Timestamp to use for this state

        Returns:
            A PlayerState object, or None if player data couldn't be extracted
        """
        if 'player' not in payload:
            return None

        player_data = payload.get('player', {})

        # early return if essential data is missing
        if 'steamid' not in player_data or 'state' not in player_data:
            return None

        # extract core player data
        steam_id = player_data.get('steamid', 'unknown')
        name = player_data.get('name', f'Player_{steam_id[-4:]}')
        team = player_data.get('team', 'SPEC')

        # extract player state data
        state_data = player_data.get('state', {})
        health = state_data.get('health', 0)
        armor = state_data.get('armor', 0)
        money = state_data.get('money', 0)
        equip_value = state_data.get('equip_value', 0)
        round_kills = state_data.get('round_kills', 0)

        # extract match statistics
        stats_data = player_data.get('match_stats', {})
        match_kills = stats_data.get('kills', 0)
        match_deaths = stats_data.get('deaths', 0)
        match_assists = stats_data.get('assists', 0)
        match_mvps = stats_data.get('mvps', 0)
        match_score = stats_data.get('score', 0)

        # create the playerstate with all extracted data
        return PlayerState(
            steam_id=steam_id,
            name=name,
            team=team,
            health=health,
            armor=armor,
            money=money,
            equip_value=equip_value,
            round_kills=round_kills,
            match_kills=match_kills,
            match_deaths=match_deaths,
            match_assists=match_assists,
            match_mvps=match_mvps,
            match_score=match_score,
            state_timestamp=timestamp
        )

    def _detect_state_changes(self, payload: Dict, new_match: Optional[MatchState],
                            new_player: Optional[PlayerState], new_round: Optional[RoundState],
                            new_weapons: Dict[str, WeaponState]) -> Dict:
        """
        Detect changes between previous and new states.
        
        This method analyzes differences between states to identify meaningful changes
        that should trigger analytics or database updates.
        return changes
        
        Args:
            payload: The raw GSI payload
            new_match: The newly extracted match state
            new_player: The newly extracted player state
            new_round: The newly extracted round state
            
        Returns:
            Dictionary of detected changes for analytics
        """
        # track changes to report
        changes = {
            'match': {},
            'round': {},
            'player': {},
            'weapons': {},
            'significant_events': []
        }
        
        # check for match state changes
        if new_match and self.current_match:
            # compare relevant fields
            for field in ['phase', 'round', 'team_ct_score', 'team_t_score']:
                old_value = getattr(self.current_match, field)
                new_value = getattr(new_match, field)
                if old_value != new_value:
                    changes['match'][field] = {'old': old_value, 'new': new_value}
                    
                    # detect significant events
                    if field == 'round' and new_value > old_value:
                        changes['significant_events'].append({
                            'type': 'round_change',
                            'old_round': old_value,
                            'new_round': new_value
                        })
                    elif field == 'phase' and new_value == 'gameover':
                        changes['significant_events'].append({
                            'type': 'match_end',
                            'final_score_ct': new_match.team_ct_score,
                            'final_score_t': new_match.team_t_score
                        })
        
        # check for round state changes
        if new_round and self.current_round:
            # compare relevant fields
            for field in ['phase', 'win_team', 'bomb_state']:
                old_value = getattr(self.current_round, field, None)
                new_value = getattr(new_round, field, None)
                if old_value != new_value:
                    changes['round'][field] = {'old': old_value, 'new': new_value}
                    
                    # detect significant events
                    if field == 'phase' and old_value != 'over' and new_value == 'over':
                        changes['significant_events'].append({
                            'type': 'round_over',
                            'round_number': new_round.round_number,
                            'winner': new_round.win_team,
                            'condition': new_round.win_condition
                        })
                    elif field == 'bomb_state' and new_value == 'planted':
                        changes['significant_events'].append({
                            'type': 'bomb_planted',
                            'round_number': new_round.round_number
                        })
        
        # check for player state changes
        if new_player and new_player.steam_id in self.player_states:
            prev = self.player_states[new_player.steam_id]
            
            # track non-weapon changes
            for field in ['health', 'armor', 'money', 'equip_value', 'round_kills',
                         'match_kills', 'match_deaths', 'match_assists', 'match_mvps', 'match_score']:
                old_value = getattr(prev, field)
                new_value = getattr(new_player, field)
                if old_value != new_value:
                    changes['player'][field] = {'old': old_value, 'new': new_value}
                    
                    # detect significant events (kills, etc.)
                    if field == 'round_kills' and new_value > old_value:
                        # find currently active weapon
                        active_weapon = None
                        for slot, weapon in new_weapons.items():
                            if weapon.state == 'active':
                                active_weapon = weapon
                                break
                        
                        kill_delta = new_value - old_value
                        changes['significant_events'].append({
                            'type': 'player_kill',
                            'player_id': new_player.steam_id,
                            'kill_count': kill_delta,
                            'weapon': active_weapon.name if active_weapon else None,
                            'timestamp': new_player.state_timestamp
                        })
        
        # check for weapon changes separately
        for slot, new_weapon in new_weapons.items():
            if slot in self.weapon_states:
                old_weapon = self.weapon_states[slot]
                weapon_changes = {}
                
                for field in ['state', 'ammo_clip', 'ammo_reserve']:
                    old_value = getattr(old_weapon, field, None)
                    new_value = getattr(new_weapon, field, None)
                    if old_value != new_value:
                        weapon_changes[field] = {'old': old_value, 'new': new_value}
                
                if weapon_changes:
                    changes['weapons'][new_weapon.name] = weapon_changes
                    
                    # detect weapon activation for analytics
                    if 'state' in weapon_changes and weapon_changes['state']['new'] == 'active':
                        changes['significant_events'].append({
                            'type': 'weapon_activated',
                            'player_id': new_weapon.steam_id,
                            'weapon': new_weapon.name,
                            'timestamp': new_weapon.state_timestamp
                        })
            else:
                # new weapon
                changes['weapons'][new_weapon.name] = {'state': 'added'}
        
        # check for removed weapons
        for slot, old_weapon in self.weapon_states.items():
            if slot not in new_weapons:
                changes['weapons'][old_weapon.name] = {'state': 'removed'}
        
        return changes        

    def _update_internal_state(self, match_state: Optional[MatchState], 
                              player_state: Optional[PlayerState],
                              round_state: Optional[RoundState],
                              weapon_states: Optional[Dict[str, WeaponState]]) -> None:
        """
        Update internal state with newly extracted components.
        
        This method maintains the internal state that's used for detecting
        changes and tracking historical data.
        
        Args:
            match_state: New match state to store
            player_state: New player state to store
            round_state: New round state to store
        """
        # update match state
        if match_state:
            self.current_match = match_state
            
        # update player state
        if player_state:
            self.player_states[player_state.steam_id] = player_state

        # update weapon state
        if weapon_states:
            self.weapon_states = weapon_states
            
        # update round state and history
        if round_state:
            old_phase = None if not self.current_round else self.current_round.phase
            new_phase = round_state.phase

            # old round number is this incoming round_state minus one
            old_round_number = round_state.round_number - 1
            
            # detect round completion (phase transition to 'over')
            if old_phase != 'over' and new_phase == 'over' and round_state.win_team:
                if round_state.round_number not in self.processed_rounds:
                    self.processed_rounds.add(old_round_number)
                    logger.info(f"Round {old_round_number} completed. Winner: {round_state.win_team}")
            
            # if we have a current_round state, it is now previous_round_state
            if self.current_round:
                self.previous_round_state = self.current_round
                self.previous_round_state.round_number = old_round_number
                # if new round state has round conclusion metadata, utilize it
                if round_state.win_team and round_state.win_condition:
                    self.previous_round_state.win_team = round_state.win_team
                    self.previous_round_state.win_condition = round_state.win_condition

            # update current internal round state with new state
            self.current_round = round_state
            
            # store previous round state in history if it's a complete round state
            if round_state.phase == 'over' and round_state.win_team:
                self.round_history[old_round_number] = self.previous_round_state

    def get_round_win_condition(self, round_number: int) -> Optional[str]:
        """
        Get the win condition for a specific round.
        
        Args:
            round_number: The round number to check
            
        Returns:
            Win condition string or None if not available
        """
        if round_number in self.round_history:
            return self.round_history[round_number].win_condition
        return None
    
    def get_round_winner(self, round_number: int) -> Optional[str]:
        """
        Get the winning team for a specific round.
        
        Args:
            round_number: The round number to check
            
        Returns:
            Winning team ('CT', 'T') or None if not available
        """
        if round_number in self.round_history:
            return self.round_history[round_number].win_team
        return None
    
    def should_persist_round(self, round_number: int) -> bool:
        """
        Check if a round should be persisted to the database.
        
        Args:
            round_number: The round number to check
            
        Returns:
            True if the round should be persisted, False otherwise
        """
        # a round should be persisted if:
        # 1. it's in the round history (completed)
        # 2. it hasn't been marked as processed yet
        in_history = round_number in self.round_history
        not_processed = round_number not in self.processed_rounds
        
        if in_history and not_processed:
            # mark as processed to avoid duplicate persistence
            self.processed_rounds.add(round_number)
            return True
        
        return False

    def get_active_weapon(self) -> Optional[WeaponState]:
        """
        Get the currently active weapon for a player.
            
        Returns:
            The active weapon or None if no active weapon found
        """
        for weapon in self.weapon_states.values():
            if weapon.state == 'active':
                return weapon
        return None
