from dataclasses import dataclass, field
from typing import Dict, Optional, List, Set
from datetime import datetime

# utilize our custom logger service
from gsi.logging_service import payload_logger as logger

# import utility functions
from gsi.utils import extract_base_match_id

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

@dataclass
class PlayerState:
    """
    Represents the state of a player.
    Maps to both 'stats_playerroundstate' and 'stats_playermatchstat' tables.
    """
    steam_id: str        # player's steam id
    name: str            # player's name
    team: str            # player's team (ct, t, spec)
    health: int          # current health
    armor: int           # current armor
    money: int           # current money
    equip_value: int     # equipment value
    round_kills: int     # kills in current round
    match_kills: int     # total kills in match
    match_deaths: int    # total deaths in match
    match_assists: int   # total assists in match
    match_mvps: int      # total mvps in match
    match_score: int     # total score in match
    weapons: Dict[str, WeaponState] = field(default_factory=dict)  # current weapons

class PayloadExtractor:
    """
    Extracts and tracks data from CS2 GSI payloads.
    Maintains state between updates and provides structured access to game data.
    """
    
    def __init__(self):
        # current state tracking
        self.current_match: Optional[MatchState] = None
        self.player_states: Dict[str, PlayerState] = {}
        self.current_round: Optional[RoundState] = None
        
        # historical data tracking
        self.round_history: Dict[int, RoundState] = {}  # map round_number to roundstate
        self.processed_rounds: Set[int] = set()         # track which rounds have been processed

    def extract_match_state(self, payload: Dict) -> Optional[MatchState]:
        """
        Extract match state from a GSI payload.
        
        Args:
            payload: The GSI payload
            
        Returns:
            A MatchState object, or None if match data couldn't be extracted
        """
        if 'map' not in payload or 'provider' not in payload:
            return None
            
        map_data = payload['map']
        provider_data = payload['provider']

        # use centralized utility function to get base_match_id
        #  (match_processor will append uuid)
        base_match_id = extract_base_match_id(payload)
        if not base_match_id:
            return None

        # extract remaining match data
        timestamp = provider_data.get('timestamp', int(datetime.now().timestamp()))
        
        # return full match state
        return MatchState(
            match_id=base_match_id,
            mode=map_data.get('mode', 'casual'),
            map_name=map_data.get('name', 'unknown_map'),
            phase=map_data.get('phase', 'unknown'),
            round=map_data.get('round', 0),
            team_ct_score=map_data.get('team_ct', {}).get('score', 0),
            team_t_score=map_data.get('team_t', {}).get('score', 0),
            timestamp=timestamp
        )

    def extract_round_state(self, payload: Dict) -> Optional[RoundState]:
        """
        Extract round state information from a GSI payload.
        
        Args:
            payload: The GSI payload
            
        Returns:
            A RoundState object, or None if round data couldn't be extracted
        """
        if 'round' not in payload or 'map' not in payload:
            return None
            
        round_data = payload.get('round', {})
        map_data = payload.get('map', {})
        
        # get current round number from map data
        round_number = map_data.get('round', 0)
        
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
            win_condition=win_condition
        )

    def extract_weapon_state(self, weapon_data: Dict) -> WeaponState:
        """
        Extract weapon state from weapon data.
        
        Args:
            weapon_data: Weapon data from the GSI payload
            
        Returns:
            A WeaponState object
        """
        return WeaponState(
            name=weapon_data.get("name", "unknown_weapon"),
            # use the type directly from the payload
            type=weapon_data.get("type", "Other"),
            state=weapon_data.get("state", "unknown"),
            ammo_clip=weapon_data.get("ammo_clip"),
            ammo_clip_max=weapon_data.get("ammo_clip_max"),
            ammo_reserve=weapon_data.get("ammo_reserve"),
            paintkit=weapon_data.get("paintkit", "default")
        )

    def extract_player_state(self, payload: Dict) -> Optional[PlayerState]:
        """
        Extract player state from a GSI payload.
        
        Args:
            payload: The GSI payload
            
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
        
        # extract weapons
        weapons = {}
        if 'weapons' in player_data:
            for slot, weapon_data in player_data.get('weapons', {}).items():
                weapons[slot] = self.extract_weapon_state(weapon_data)
        
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
            weapons=weapons
        )

    def process_payload(self, payload: Dict) -> None:
        """
        Process a GSI payload and update internal state.
        
        Args:
            payload: The GSI payload
        """
        # extract all state components
        match_state = self.extract_match_state(payload)
        player_state = self.extract_player_state(payload)
        round_state = self.extract_round_state(payload)
        
        # update match state
        if match_state:
            self.current_match = match_state
            
        # update player state
        if player_state:
            self.player_states[player_state.steam_id] = player_state
            
        # update round state
        if round_state:
            # track round transitions (for database persistence triggers)
            old_phase = None if not self.current_round else self.current_round.phase
            new_phase = round_state.phase
            
            # detect round completion (phase transition to 'over')
            if old_phase != 'over' and new_phase == 'over' and round_state.win_team:
                # add to processed rounds set when a round completes
                if round_state.round_number not in self.processed_rounds:
                    self.processed_rounds.add(round_state.round_number)
                    logger.info(f"Round {round_state.round_number} completed. Winner: {round_state.win_team}")
            
            # update current round state
            self.current_round = round_state
            
            # store in history if it's a complete round state
            if round_state.phase == 'over' and round_state.win_team:
                self.round_history[round_state.round_number] = round_state

    def monitor_state_changes(self, payload: Dict) -> Dict:
        """
        Process a payload and monitor changes between the previous and new states.
        
        Args:
            payload: The GSI payload
            
        Returns:
            Dictionary of detected changes for logger/analysis
        """
        # track changes to report
        changes = {
            'match': {},
            'round': {},
            'player': {},
            'weapons': {}
        }
        
        # process new states
        new_match = self.extract_match_state(payload)
        new_player = self.extract_player_state(payload)
        new_round = self.extract_round_state(payload)
        
        # check for match state changes
        if new_match and self.current_match:
            # compare relevant fields
            for field in ['phase', 'round', 'team_ct_score', 'team_t_score']:
                old_value = getattr(self.current_match, field)
                new_value = getattr(new_match, field)
                if old_value != new_value:
                    changes['match'][field] = {'old': old_value, 'new': new_value}
        
        # check for round state changes
        if new_round and self.current_round:
            # compare relevant fields
            for field in ['phase', 'win_team', 'bomb_state']:
                old_value = getattr(self.current_round, field)
                new_value = getattr(new_round, field)
                if old_value != new_value:
                    changes['round'][field] = {'old': old_value, 'new': new_value}
        
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
            
            # track weapon changes
            for weapon_slot, new_weapon in new_player.weapons.items():
                if weapon_slot in prev.weapons:
                    old_weapon = prev.weapons[weapon_slot]
                    weapon_changes = {}
                    
                    for field in ['state', 'ammo_clip', 'ammo_reserve']:
                        old_value = getattr(old_weapon, field)
                        new_value = getattr(new_weapon, field)
                        if old_value != new_value:
                            weapon_changes[field] = {'old': old_value, 'new': new_value}
                    
                    if weapon_changes:
                        changes['weapons'][new_weapon.name] = weapon_changes
                else:
                    # new weapon equipped
                    changes['weapons'][new_weapon.name] = {'state': 'added'}
            
            # check for removed weapons
            for weapon_slot, old_weapon in prev.weapons.items():
                if weapon_slot not in new_player.weapons:
                    changes['weapons'][old_weapon.name] = {'state': 'removed'}
        
        # update current states with new data
        self.process_payload(payload)
        
        # return detected changes
        return changes
    
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
