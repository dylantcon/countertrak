"""
CounterTrak Match Processor

Processes game state data for an individual CS2 match.
Maintains state between updates and handles temporal sequence analysis.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Set

# Import PayloadExtractor to leverage original proof-of-concept
from payloadextractor import PayloadExtractor, MatchState, PlayerState

class MatchProcessor:
    """
    Processes and maintains state for a single CS2 match.
    """
    
    def __init__(self, match_id: str):
        """
        Initialize a new match processor for a specific match.
        
        Args:
            match_id: The match identifier
        """
        self.match_id = match_id
        self.extractor = PayloadExtractor()
        
        # Match metadata
        self.match_state: Optional[MatchState] = None
        self.player_states: Dict[str, PlayerState] = {}
        
        # Round tracking
        self.current_round = 0
        self.round_start_time: Optional[float] = None
        self.rounds_processed: Set[int] = set()
        
        # Activity tracking
        self.last_update_time = time.time()
        self.is_completed = False
        
        logging.info(f"Match processor initialized for match {match_id}")
    
    async def process_payload(self, payload: Dict) -> None:
        """
        Process a GSI payload for this match.
        
        This method:
        1. Updates the match state
        2. Updates player states
        3. Tracks round transitions
        4. Detects match completion
        
        Args:
            payload: The GSI payload from CS2
        """
        try:
            # Update the last activity timestamp
            self.last_update_time = time.time()
            
            # Log the first payload for this match when we first create it
            if not self.match_state:
                logging.info(f"Processing first payload for match {self.match_id}")
                if 'player' in payload:
                    player_name = payload.get('player', {}).get('name', 'unknown')
                    steam_id = payload.get('player', {}).get('steamid', 'unknown')
                    logging.info(f"Match {self.match_id} associated with player {player_name} ({steam_id})")
            
            # Extract match state
            new_match = self.extractor.extract_match_state(payload)
            if new_match:
                # If this is a new round, process the round transition
                if self.match_state and new_match.round != self.match_state.round:
                    logging.info(f"Match {self.match_id}: Round change from {self.match_state.round} to {new_match.round}")
                    await self._process_round_transition(
                        old_round=self.match_state.round,
                        new_round=new_match.round,
                        phase=new_match.phase
                    )
                
                # Update the match state
                self.match_state = new_match
                self.current_round = new_match.round
                
                # Check if the match is completed
                if new_match.phase == "gameover":
                    logging.info(f"Match {self.match_id}: Game over detected")
                    await self._handle_match_completion()
            
            # Extract player state
            new_player = self.extractor.extract_player_state(payload)
            if new_player:
                # If this is a new player or the player's state has changed
                await self._update_player_state(new_player)
            
            # Process state changes
            await self._process_state_changes(payload)
            
        except Exception as e:
            logging.error(f"Error processing payload in match {self.match_id}: {str(e)}")
    
    async def _process_round_transition(self, old_round: int, new_round: int, phase: str) -> None:
        """
        Process a transition between rounds.
        
        Args:
            old_round: The previous round number
            new_round: The new round number
            phase: The current match phase
        """
        # Mark the old round as processed if we haven't already
        if old_round not in self.rounds_processed:
            self.rounds_processed.add(old_round)
            logging.info(f"Match {self.match_id}: Completed round {old_round}")
            
            # TODO: Here, we need a way to persist the round data to the database
            # For now, we'll just log it
            await self._save_round_data(old_round)
        
        # If we're starting a new round, update tracking
        if phase == "freezetime" and new_round > old_round:
            self.round_start_time = time.time()
            logging.info(f"Match {self.match_id}: Starting round {new_round}")
    
    async def _update_player_state(self, player_state: PlayerState) -> None:
        """
        Update a player's state and track changes.
        
        Args:
            player_state: The new player state
        """
        steam_id = player_state.steam_id
        
        # Check if we've seen this player before
        if steam_id in self.player_states:
            old_state = self.player_states[steam_id]
            
            # Track changes in player state (similar to monitor_state_changes)
            basic_changes = {
                k: v for k, v in vars(player_state).items()
                if k != 'weapons' and getattr(old_state, k) != v
            }
            
            if basic_changes:
                # TODO: Here we would track significant state changes
                # For performance metrics analysis
                pass
            
            # Track weapon changes
            for weapon_slot, new_weapon in player_state.weapons.items():
                if weapon_slot in old_state.weapons:
                    old_weapon = old_state.weapons[weapon_slot]
                    weapon_changes = {
                        k: getattr(new_weapon, k)
                        for k in vars(new_weapon).keys()
                        if getattr(old_weapon, k) != getattr(new_weapon, k)
                    }
                    
                    if weapon_changes:
                        # Especially important to track state changes
                        # (active/holstered) for weapon analytics
                        if 'state' in weapon_changes and weapon_changes['state'] == 'active':
                            logging.debug(f"Player {steam_id} activated {new_weapon.name}")
                        elif 'state' in weapon_changes and weapon_changes['state'] == 'holstered':
                            logging.debug(f"Player {steam_id} holstered {new_weapon.name}")
        
        # Update the player's state
        self.player_states[steam_id] = player_state
    
    async def _process_state_changes(self, payload: Dict) -> None:
        """
        Process significant state changes for analytics.
        
        This method identifies important events like:
        - Weapon switches
        - Kills/deaths
        - Round victories
        - Economic decisions
        
        Args:
            payload: The GSI payload
        """
        # Use existing monitor_state_changes method as a starting point
        # This will log changes but we'll need to enhance it for analytics
        self.extractor.monitor_state_changes(payload)
        
        # TODO: Additional state change processing for analytics
        # This will be filled in with our specific analytics logic
    
    async def _save_round_data(self, round_number: int) -> None:
        """
        Save the data for a completed round.
        
        Args:
            round_number: The round number to save
        """
        # For now, just log that we would save the data
        # In the future, this will persist to PostgreSQL
        logging.info(f"Match {self.match_id}: Would save data for round {round_number}")
        
        # Log player stats for this round
        for steam_id, player in self.player_states.items():
            logging.info(
                f"Round {round_number} stats for {player.name}: "
                f"kills={player.round_kills}, "
                f"damage={player.round_damage}"
            )
    
    async def _handle_match_completion(self) -> None:
        """
        Handle the completion of a match.
        """
        if not self.is_completed:
            self.is_completed = True
            logging.info(f"Match {self.match_id} completed")
            
            # Save final match stats
            if self.match_state:
                ct_score = self.match_state.team_ct_score
                t_score = self.match_state.team_t_score
                
                logging.info(
                    f"Final score - CT: {ct_score}, T: {t_score}, "
                    f"Total rounds: {len(self.rounds_processed)}"
                )
                
                # TODO: Persist final match data to database
    
    def is_match_completed(self) -> bool:
        """
        Check if the match is completed or has been inactive for too long.
        
        A match is considered completed if:
        1. It's explicitly in the 'gameover' phase, or
        2. It hasn't received updates in the last 10 minutes
        
        Returns:
            True if the match is completed, False otherwise
        """
        # Check explicit completion
        if self.is_completed:
            return True
        
        # Check for inactivity
        inactive_seconds = time.time() - self.last_update_time
        if inactive_seconds > 600:  # 10 minutes
            logging.info(f"Match {self.match_id} considered completed due to inactivity")
            return True
        
        return False
    
    # Accessor methods for match statistics
    
    def get_map_name(self) -> str:
        """Get the map name for this match."""
        return self.match_state.map_name if self.match_state else "unknown"
    
    def get_game_mode(self) -> str:
        """Get the game mode for this match."""
        return self.match_state.mode if self.match_state else "unknown"
    
    def get_match_phase(self) -> str:
        """Get the current match phase."""
        return self.match_state.phase if self.match_state else "unknown"
    
    def get_current_round(self) -> int:
        """Get the current round number."""
        return self.current_round
    
    def get_ct_score(self) -> int:
        """Get the CT team's score."""
        return self.match_state.team_ct_score if self.match_state else 0
    
    def get_t_score(self) -> int:
        """Get the T team's score."""
        return self.match_state.team_t_score if self.match_state else 0
    
    def get_player_count(self) -> int:
        """Get the number of players in this match."""
        return len(self.player_states)
