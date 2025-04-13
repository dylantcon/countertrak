import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime

@dataclass
class MatchState:
    match_id: str  # Generated UUID
    mode: str
    map_name: str
    phase: str
    round: int
    team_ct_score: int
    team_t_score: int
    timestamp: int

@dataclass
class WeaponState:
    name: str
    type: str
    state: str
    ammo_clip: Optional[int] = None
    ammo_clip_max: Optional[int] = None
    ammo_reserve: Optional[int] = None
    paintkit: str = "default"

@dataclass
class PlayerState:
    steam_id: str
    name: str
    team: str
    health: int
    armor: int
    money: int
    equip_value: int
    round_kills: int
    match_kills: int
    match_deaths: int
    match_assists: int
    match_mvps: int
    match_score: int
    weapons: Dict[str, WeaponState] = field(default_factory=dict)

class PayloadExtractor:
    """
    Extracts relevant data from CS2 GSI payloads.
    Modified to work with the async architecture.
    """
    
    def __init__(self):
        self.current_match: Optional[MatchState] = None
        self.player_states: Dict[str, PlayerState] = {}
    
    def extract_match_state(self, payload: Dict) -> Optional[MatchState]:
        """
        Extract match state from a GSI payload.
        
        Args:
            payload: The GSI payload
            
        Returns:
            A MatchState object, or None if match data couldn't be extracted
        """
        if 'map' not in payload or 'player' not in payload:
            return None
        
        map_data = payload['map']
        player_data = payload['player']
        
        # Create a stable match ID that won't change during the match
        map_name = map_data.get('name', 'unknown_map')
        game_mode = map_data.get('mode', 'casual')  # Default to casual if not specified
        steam_id = player_data.get('steamid', 'unknown_player')
        
        match_id = f"{map_name}_{game_mode}_{steam_id}"
        
        return MatchState(
            match_id=match_id,
            mode=map_data['mode'],
            map_name=map_data['name'],
            phase=map_data['phase'],
            round=map_data['round'],
            team_ct_score=map_data['team_ct']['score'],
            team_t_score=map_data['team_t']['score'],
            timestamp=payload['provider']['timestamp']
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
            name=weapon_data["name"],
            type=weapon_data.get("type", "Other"),  # other is needed as default (zeus x11)
            state=weapon_data["state"],
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
        if 'player' not in payload or 'state' not in payload['player']:
            return None
        
        p = payload['player']
        state = p['state']
        stats = p.get('match_stats', {})
        weapons = {}
        
        if 'weapons' in p:
            for key, data in p['weapons'].items():
                weapons[key] = self.extract_weapon_state(data)
        
        return PlayerState(
            steam_id=p['steamid'],
            name=p['name'],
            team=p.get('team', 'SPEC'),
            health=state.get('health', 0),
            armor=state.get('armor', 0),
            money=state.get('money', 0),
            equip_value=state.get('equip_value', 0),
            round_kills=state.get('round_kills', 0),
            match_kills=stats.get('kills', 0),
            match_deaths=stats.get('deaths', 0),
            match_assists=stats.get('assists', 0),
            match_mvps=stats.get('mvps', 0),
            match_score=stats.get('score', 0),
            weapons=weapons
        )
    
    def process_payload(self, payload: Dict) -> None:
        """
        Process a GSI payload and update internal state.
        
        Args:
            payload: The GSI payload
        """
        match_state = self.extract_match_state(payload)
        if match_state:
            self.current_match = match_state
        
        player_state = self.extract_player_state(payload)
        if player_state:
            self.player_states[player_state.steam_id] = player_state
    
    def monitor_state_changes(self, payload: Dict) -> None:
        """
        Monitor and log state changes between payloads.
        
        Args:
            payload: The GSI payload
        """
        # Process new state first
        new_match = self.extract_match_state(payload)
        new_player = self.extract_player_state(payload)
        
        # Then check for changes against newly updated state
        if new_player and new_player.steam_id in self.player_states:
            prev = self.player_states[new_player.steam_id]
            
            # track non-weapon changes
            basic_changes = {
                k: v for k, v in vars(new_player).items()
                if k != 'weapons' and getattr(prev, k) != v
            }
            if basic_changes:
                logging.info(f"{new_player.name} ({new_player.steam_id}) delta: {basic_changes}")
            
            for weapon_slot, new_weapon in new_player.weapons.items():
                if weapon_slot in prev.weapons:
                    old_weapon = prev.weapons[weapon_slot]
                    weapon_changes = {
                        k: getattr(new_weapon, k)
                        for k in vars(new_weapon).keys()
                        if getattr(old_weapon, k) != getattr(new_weapon, k)
                    }
                    if weapon_changes:
                        logging.info(f"{new_weapon.name} in slot {weapon_slot} delta: {weapon_changes}")
        
        if new_match:
            self.current_match = new_match
        if new_player:
            self.player_states[new_player.steam_id] = new_player
